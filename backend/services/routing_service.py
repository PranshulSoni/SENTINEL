import asyncio
import heapq
import json
import logging
import math
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

try:
    import httpx
except Exception:  # pragma: no cover - dependency may be unavailable in lightweight environments.
    httpx = None

from data.road_segments import DEFAULT_ROAD_SEGMENTS


logger = logging.getLogger(__name__)


@dataclass
class _Edge:
    to_node: str
    length_km: float
    travel_minutes: float
    segment_name: str
    midpoint: tuple[float, float]
    is_blocked: bool = False


class RoutingService:
    """
    ORS-primary routing with local A* scoring and local A* fallback.
    """

    SEVERITY_RADIUS_M = {
        "minor": 220.0,
        "moderate": 330.0,
        "major": 450.0,
        "critical": 600.0,
    }

    SEVERITY_MAX_POINT_DIST_M = {
        "minor": 520.0,
        "moderate": 760.0,
        "major": 980.0,
        "critical": 1280.0,
    }

    BBOX_SPAN_GUARD = {
        "nyc": (0.018, 0.015),
        "chandigarh": (0.016, 0.014),
    }

    ABS_ALT_MAX_KM = {
        "nyc": {"minor": 2.2, "moderate": 3.2, "major": 4.4, "critical": 5.4},
        "chandigarh": {"minor": 1.6, "moderate": 2.8, "major": 4.2, "critical": 5.0},
    }

    MAX_DETOUR_RATIO = 1.45
    MAX_DETOUR_RATIO_BY_SEVERITY = {
        "minor": 1.45,
        "moderate": 1.50,
        "major": 1.65,
        "critical": 1.80,
    }
    ALT_AVOID_RADIUS_MULT = {
        "minor": 0.60,
        "moderate": 0.52,
        "major": 0.45,
        "critical": 0.40,
    }
    MIN_STREET_MATCH_OVERLAP = 0.42

    ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"

    def __init__(self, ors_api_key: str = "", mapbox_token: str = ""):
        # mapbox_token retained for compatibility with older wiring.
        self.mapbox_token = mapbox_token
        self.ors_api_key = ors_api_key or os.getenv("ORS_API_KEY", "")
        self._ors_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._ors_cache_ttl_sec = 60.0
        self._http_timeout = 12.0

    async def compute_incident_route_pair(
        self,
        incident_lng: float,
        incident_lat: float,
        city: str = "nyc",
        on_street: str = "",
        extra_avoid_polygons: list | None = None,
        severity: str = "moderate",
        feed_segments: Optional[list[dict]] = None,
    ) -> dict:
        severity = self._normalize_severity(severity)
        feed_segments = feed_segments or []

        origin, destination = self._build_anchors(
            incident_lng=incident_lng,
            incident_lat=incident_lat,
            on_street=on_street,
            severity=severity,
            city=city,
            feed_segments=feed_segments,
        )
        vias = self._build_candidate_vias(
            incident_lng=incident_lng,
            incident_lat=incident_lat,
            on_street=on_street,
            severity=severity,
            city=city,
            feed_segments=feed_segments,
        )

        incident_polygon = self._incident_avoid_polygon(
            incident_lng=incident_lng,
            incident_lat=incident_lat,
            severity=severity,
            radius_multiplier=self.ALT_AVOID_RADIUS_MULT.get(severity, 0.5),
        )
        avoid_polygons = [incident_polygon]
        for poly in (extra_avoid_polygons or []):
            norm = self._normalize_polygon(poly)
            if norm:
                avoid_polygons.append(norm)

        local_graph = self._build_local_graph(city=city, feed_segments=feed_segments)
        straight_km = self._haversine_m((origin[0], origin[1]), (destination[0], destination[1])) / 1000.0
        blocked_baseline_km = max(straight_km, 0.2)
        expected_alt_minutes = self._expected_alternate_minutes(
            graph=local_graph,
            origin=origin,
            destination=destination,
            incident=(incident_lng, incident_lat),
            severity=severity,
            avoid_polygons=avoid_polygons,
        )

        blocked_route: Optional[dict[str, Any]] = None
        alt_candidates: list[dict[str, Any]] = []
        ors_requests = 0
        ors_success = 0
        blocked_from_ors = False
        candidate_rejections: dict[str, int] = {
            "ors_failed": 0,
            "invalid_geometry": 0,
            "locality": 0,
            "detour": 0,
            "via_blocked_zone": 0,
        }
        degradation_reason: Optional[str] = None

        if self.ors_api_key and httpx is None:
            degradation_reason = "ors_transport_unavailable"

        if self.ors_api_key and httpx is not None:
            blocked_ors = await self._ors_route(
                coordinates=[origin, [incident_lng, incident_lat], destination],
                avoid_polygons=None,
            )
            ors_requests += 1
            if blocked_ors and self._is_renderable(blocked_ors["geometry"]["coordinates"]):
                blocked_route = blocked_ors
                blocked_from_ors = True
                ors_success += 1
                blocked_baseline_km = max(float(blocked_ors.get("total_length_km", blocked_baseline_km) or blocked_baseline_km), 0.2)
            else:
                candidate_rejections["ors_failed"] += 1

            # Limit candidate ORS calls per incident to avoid rate-limit spirals.
            for via in vias[:4]:
                if self._point_in_any_polygon((float(via[0]), float(via[1])), avoid_polygons):
                    candidate_rejections["via_blocked_zone"] += 1
                    continue
                candidate = await self._ors_route(
                    coordinates=[origin, via, destination],
                    avoid_polygons=avoid_polygons,
                )
                ors_requests += 1
                if not candidate:
                    candidate_rejections["ors_failed"] += 1
                    continue
                ors_success += 1
                coords = candidate["geometry"]["coordinates"]
                if not self._is_renderable(coords):
                    candidate_rejections["invalid_geometry"] += 1
                    continue
                if not self._passes_locality_guard(
                    coords=coords,
                    incident_lng=incident_lng,
                    incident_lat=incident_lat,
                    city=city,
                    severity=severity,
                ):
                    candidate_rejections["locality"] += 1
                    continue
                candidate_km = float(candidate.get("total_length_km", 0) or 0)
                if not self._passes_detour_guard(
                    alt_km=max(candidate_km, self._polyline_km(coords)),
                    blocked_km=blocked_baseline_km,
                    city=city,
                    severity=severity,
                ):
                    candidate_rejections["detour"] += 1
                    continue
                score, locality, loop_penalty, detour_penalty = self._score_alternate_candidate(
                    route=candidate,
                    incident=(incident_lng, incident_lat),
                    severity=severity,
                    feed_segments=feed_segments,
                    expected_minutes=expected_alt_minutes,
                    city=city,
                    blocked_km=blocked_baseline_km,
                )
                candidate["meta_score"] = score
                candidate["locality_score"] = locality
                candidate["loop_penalty"] = loop_penalty
                candidate["detour_penalty"] = detour_penalty
                alt_candidates.append(candidate)

        fallback_used = False
        astar_score = 0.0
        fallback_alt_locality = 0.0

        if not blocked_route:
            fallback_used = True
            if self.ors_api_key and not degradation_reason:
                degradation_reason = "ors_unavailable"
            blocked_route = self._fallback_blocked_route(
                graph=local_graph,
                origin=origin,
                destination=destination,
                incident=(incident_lng, incident_lat),
                on_street=on_street,
            )

        blocked_coords = self._ensure_renderable(blocked_route["geometry"]["coordinates"])
        blocked_km = self._polyline_km(blocked_coords)
        blocked_minutes = blocked_route.get("estimated_minutes") or self._estimate_minutes(blocked_km, 16.0)
        blocked_names = blocked_route.get("street_names") or ([on_street] if on_street else [])

        alternate_route: dict[str, Any]
        valid_alternate = False

        if alt_candidates:
            best_alt = min(alt_candidates, key=lambda c: c["meta_score"])
            alternate_route = best_alt
            astar_score = float(best_alt.get("meta_score", 0.0))
            valid_alternate = True
        else:
            fallback_used = True
            if self.ors_api_key and not degradation_reason:
                degradation_reason = "no_valid_ors_alternate"
            alternate_route, astar_score = self._fallback_alternate_route(
                graph=local_graph,
                origin=origin,
                destination=destination,
                incident=(incident_lng, incident_lat),
                severity=severity,
                on_street=on_street,
                avoid_polygons=avoid_polygons,
                feed_segments=feed_segments,
                expected_minutes=expected_alt_minutes,
                city=city,
                blocked_km=max(blocked_km, blocked_baseline_km),
            )
            fallback_coords = alternate_route.get("geometry", {}).get("coordinates", [])
            if self._is_renderable(fallback_coords):
                locality_ok = self._passes_locality_guard(
                    coords=fallback_coords,
                    incident_lng=incident_lng,
                    incident_lat=incident_lat,
                    city=city,
                    severity=severity,
                )
                detour_ok = self._passes_detour_guard(
                    alt_km=max(float(alternate_route.get("total_length_km", 0) or 0), self._polyline_km(fallback_coords)),
                    blocked_km=max(blocked_km, blocked_baseline_km),
                    city=city,
                    severity=severity,
                )
            else:
                locality_ok = False
                detour_ok = False

            if locality_ok and detour_ok:
                fallback_alt_locality = float(alternate_route.get("locality_score", 0) or 0)
                valid_alternate = True
            else:
                if not self._is_renderable(fallback_coords):
                    candidate_rejections["invalid_geometry"] += 1
                    degradation_reason = degradation_reason or "invalid_fallback_geometry"
                if not locality_ok:
                    candidate_rejections["locality"] += 1
                    degradation_reason = degradation_reason or "no_local_alternate"
                if not detour_ok:
                    candidate_rejections["detour"] += 1
                    degradation_reason = degradation_reason or "detour_guard_rejection"
                valid_alternate = False

        if valid_alternate:
            alt_coords = self._ensure_renderable(alternate_route["geometry"]["coordinates"])
            alt_km = self._polyline_km(alt_coords)
            alt_minutes = alternate_route.get("estimated_minutes") or self._estimate_minutes(alt_km, 24.0)
            alt_names = alternate_route.get("street_names") or ([on_street] if on_street else [])
            local_score = alternate_route.get("locality_score")
            if local_score is None:
                local_score = fallback_alt_locality or self._locality_score(alt_coords, (incident_lng, incident_lat), severity)
            safe_label = "SAFE ROUTE (LOCAL ESTIMATE)" if fallback_used else "SAFE ROUTE"
        else:
            alt_coords = []
            alt_km = 0.0
            alt_minutes = 0.0
            alt_names = []
            local_score = 0.0
            safe_label = "SAFE ROUTE (LOCAL ESTIMATE)"

        if valid_alternate and not fallback_used and blocked_from_ors:
            routing_engine = "ors+astar"
            routing_source = "ors_primary_v2"
        elif valid_alternate:
            routing_engine = "local_astar"
            routing_source = "local_astar_v2"
        else:
            routing_engine = "degraded"
            routing_source = "degraded_v2"
            degradation_reason = degradation_reason or "no_safe_alternate"

        result = {
            "version": "v2",
            "city": city,
            "origin": origin,
            "destination": destination,
            "blocked": {
                "geometry": {"type": "LineString", "coordinates": blocked_coords},
                "total_length_km": round(blocked_km, 3),
                "estimated_minutes": round(float(blocked_minutes), 2),
                "street_names": blocked_names,
                "label": "BLOCKED ROAD",
            },
            "alternate": {
                "geometry": {"type": "LineString", "coordinates": alt_coords},
                "total_length_km": round(alt_km, 3),
                "estimated_minutes": round(float(alt_minutes), 2),
                "estimated_extra_minutes": round(max(float(alt_minutes) - float(blocked_minutes), 0.0), 2),
                "avg_speed_kmh": round((alt_km / (max(float(alt_minutes), 0.1) / 60.0)), 2) if valid_alternate else 0.0,
                "street_names": alt_names,
                "locality_score": round(float(local_score), 2),
                "label": safe_label,
                "is_optimal": (not fallback_used) and valid_alternate,
            },
            "meta": {
                "routing_engine": routing_engine,
                "fallback_used": fallback_used,
                "ors_requests": int(ors_requests),
                "ors_success": int(ors_success),
                "ors_calls": int(ors_requests),  # compatibility alias
                "astar_score": round(float(astar_score), 2),
                "degradation_reason": degradation_reason,
                "candidate_rejections": candidate_rejections,
            },
            "routing_source": routing_source,
        }

        logger.info(
            "Route pair built (%s) city=%s blocked=%.3fkm alt=%.3fkm fallback=%s ors_req=%s ors_ok=%s reason=%s",
            routing_engine,
            city,
            blocked_km,
            alt_km,
            fallback_used,
            ors_requests,
            ors_success,
            degradation_reason,
        )
        return result

    async def compute_congestion_route_pair(
        self,
        congested_segments: list[dict],
        city: str = "nyc",
        feed_segments: Optional[list[dict]] = None,
    ) -> dict:
        feed_segments = feed_segments or []
        if not congested_segments:
            return await self.compute_incident_route_pair(
                incident_lng=0.0,
                incident_lat=0.0,
                city=city,
                on_street="",
                severity="moderate",
                feed_segments=feed_segments,
            )

        lats = [float(s.get("lat", 0)) for s in congested_segments if s.get("lat") is not None]
        lngs = [float(s.get("lng", 0)) for s in congested_segments if s.get("lng") is not None]
        if not lats or not lngs:
            return await self.compute_incident_route_pair(
                incident_lng=0.0,
                incident_lat=0.0,
                city=city,
                on_street="",
                severity="moderate",
                feed_segments=feed_segments,
            )

        center_lat = sum(lats) / len(lats)
        center_lng = sum(lngs) / len(lngs)
        primary_street = str(congested_segments[0].get("link_name", ""))

        avg_speed = 0.0
        speed_vals = [float(s.get("speed", 0)) for s in congested_segments if s.get("speed") is not None]
        if speed_vals:
            avg_speed = sum(speed_vals) / len(speed_vals)
        severity = "major" if avg_speed <= 6 else "moderate"

        min_lng, max_lng = min(lngs), max(lngs)
        min_lat, max_lat = min(lats), max(lats)
        pad_lng = self._meters_to_lng_deg(140.0, center_lat)
        pad_lat = self._meters_to_lat_deg(140.0)
        bbox_poly = [
            [min_lng - pad_lng, min_lat - pad_lat],
            [max_lng + pad_lng, min_lat - pad_lat],
            [max_lng + pad_lng, max_lat + pad_lat],
            [min_lng - pad_lng, max_lat + pad_lat],
            [min_lng - pad_lng, min_lat - pad_lat],
        ]

        pair = await self.compute_incident_route_pair(
            incident_lng=center_lng,
            incident_lat=center_lat,
            city=city,
            on_street=primary_street,
            extra_avoid_polygons=[bbox_poly],
            severity=severity,
            feed_segments=(feed_segments or congested_segments),
        )

        corridor = self._segments_corridor_geometry(congested_segments)
        if len(corridor) >= 2:
            pair["blocked"]["geometry"]["coordinates"] = self._ensure_renderable(corridor)
            pair["blocked"]["total_length_km"] = round(self._polyline_km(pair["blocked"]["geometry"]["coordinates"]), 3)
            pair["blocked"]["estimated_minutes"] = round(
                self._estimate_minutes(pair["blocked"]["total_length_km"], 10.0),
                2,
            )

        return pair

    async def compute_consolidated_routes(
        self,
        incidents: list[dict],
        city: str = "nyc",
        proximity_threshold: float = 0.005,
    ) -> list[dict]:
        if not incidents:
            return []
        grouped: list[dict] = []
        for inc in incidents:
            loc = inc.get("location", {})
            coords = loc.get("coordinates", [0, 0]) if isinstance(loc, dict) else [0, 0]
            if len(coords) < 2:
                continue
            pair = await self.compute_incident_route_pair(
                incident_lng=float(coords[0]),
                incident_lat=float(coords[1]),
                city=city,
                on_street=inc.get("on_street", ""),
                severity=inc.get("severity", "moderate"),
            )
            pair["incident_ids"] = [inc.get("id") or str(inc.get("_id"))]
            pair["is_consolidated"] = False
            grouped.append(pair)
        return grouped

    async def compute_diversions_for_incident(
        self,
        incident_location: tuple[float, float],
        city: str = "nyc",
    ) -> list[dict]:
        lng, lat = incident_location
        pair = await self.compute_incident_route_pair(
            incident_lng=lng,
            incident_lat=lat,
            city=city,
            on_street="",
            severity="moderate",
        )
        return [
            {
                "priority": 1,
                "name": "Diversion A",
                "segment_names": pair["alternate"].get("street_names", []),
                "geometry": pair["alternate"]["geometry"],
                "total_length_km": pair["alternate"]["total_length_km"],
                "estimated_extra_minutes": pair["alternate"]["estimated_extra_minutes"],
            }
        ]

    def clear_cache(self):
        self._ors_cache.clear()

    # ---------------------------------------------------------------------
    # 1) Anchor builder
    # ---------------------------------------------------------------------

    def _normalize_severity(self, severity: str) -> str:
        sev = (severity or "").lower().strip()
        if sev in self.SEVERITY_RADIUS_M:
            return sev
        return "moderate"

    @staticmethod
    def _meters_to_lat_deg(meters: float) -> float:
        return meters / 111_320.0

    @staticmethod
    def _meters_to_lng_deg(meters: float, lat: float) -> float:
        return meters / (111_320.0 * max(math.cos(math.radians(lat)), 0.2))

    @staticmethod
    def _is_ns_street(on_street: str) -> bool:
        street = (on_street or "").lower()
        return any(
            kw in street
            for kw in [
                "ave",
                "avenue",
                "broadway",
                "blvd",
                "boulevard",
                "marg",
                "path",
                "road",
                " rd",
            ]
        )

    def _build_anchors(
        self,
        incident_lng: float,
        incident_lat: float,
        on_street: str,
        severity: str,
        city: str = "nyc",
        feed_segments: Optional[list[dict]] = None,
    ) -> tuple[list[float], list[float]]:
        vec = self._street_direction_vector(
            city=city,
            on_street=on_street,
            incident_lng=incident_lng,
            incident_lat=incident_lat,
            feed_segments=feed_segments or [],
        )
        radius_m = self.SEVERITY_RADIUS_M.get(severity, self.SEVERITY_RADIUS_M["moderate"])
        axis_m = radius_m * 1.25
        if vec is not None:
            vx, vy = vec
            origin = self._offset_point_m(incident_lng, incident_lat, -vx * axis_m, -vy * axis_m)
            destination = self._offset_point_m(incident_lng, incident_lat, vx * axis_m, vy * axis_m)
        elif self._is_ns_street(on_street):
            d_lat = self._meters_to_lat_deg(radius_m * 1.35)
            origin = [round(incident_lng, 6), round(incident_lat - d_lat, 6)]
            destination = [round(incident_lng, 6), round(incident_lat + d_lat, 6)]
        else:
            d_lng = self._meters_to_lng_deg(radius_m * 1.35, incident_lat)
            origin = [round(incident_lng - d_lng, 6), round(incident_lat, 6)]
            destination = [round(incident_lng + d_lng, 6), round(incident_lat, 6)]
        return origin, destination

    def _build_candidate_vias(
        self,
        incident_lng: float,
        incident_lat: float,
        on_street: str,
        severity: str,
        city: str = "nyc",
        feed_segments: Optional[list[dict]] = None,
    ) -> list[list[float]]:
        radius_m = self.SEVERITY_RADIUS_M.get(severity, self.SEVERITY_RADIUS_M["moderate"])
        # Keep vias outside the incident avoid polygon to avoid impossible ORS legs.
        lateral_m = radius_m * 1.35
        axial_m = radius_m * 0.95
        vec = self._street_direction_vector(
            city=city,
            on_street=on_street,
            incident_lng=incident_lng,
            incident_lat=incident_lat,
            feed_segments=feed_segments or [],
        )

        if vec is not None:
            vx, vy = vec
            px, py = -vy, vx  # perpendicular vector.
            return [
                self._offset_point_m(incident_lng, incident_lat, px * lateral_m, py * lateral_m),
                self._offset_point_m(incident_lng, incident_lat, -px * lateral_m, -py * lateral_m),
                self._offset_point_m(
                    incident_lng,
                    incident_lat,
                    (px * lateral_m) + (vx * axial_m),
                    (py * lateral_m) + (vy * axial_m),
                ),
                self._offset_point_m(
                    incident_lng,
                    incident_lat,
                    (-px * lateral_m) + (vx * axial_m),
                    (-py * lateral_m) + (vy * axial_m),
                ),
                self._offset_point_m(
                    incident_lng,
                    incident_lat,
                    (px * lateral_m) - (vx * axial_m),
                    (py * lateral_m) - (vy * axial_m),
                ),
                self._offset_point_m(
                    incident_lng,
                    incident_lat,
                    (-px * lateral_m) - (vx * axial_m),
                    (-py * lateral_m) - (vy * axial_m),
                ),
            ]

        d_lat_lat = self._meters_to_lat_deg(lateral_m)
        d_lng_lat = self._meters_to_lng_deg(lateral_m, incident_lat)
        d_lat_axial = self._meters_to_lat_deg(axial_m)
        d_lng_axial = self._meters_to_lng_deg(axial_m, incident_lat)

        if self._is_ns_street(on_street):
            return [
                [round(incident_lng + d_lng_lat, 6), round(incident_lat, 6)],
                [round(incident_lng - d_lng_lat, 6), round(incident_lat, 6)],
                [round(incident_lng + d_lng_lat * 0.82, 6), round(incident_lat + d_lat_axial, 6)],
                [round(incident_lng - d_lng_lat * 0.82, 6), round(incident_lat + d_lat_axial, 6)],
                [round(incident_lng, 6), round(incident_lat + d_lat_lat, 6)],
                [round(incident_lng, 6), round(incident_lat - d_lat_lat, 6)],
            ]
        return [
            [round(incident_lng, 6), round(incident_lat + d_lat_lat, 6)],
            [round(incident_lng, 6), round(incident_lat - d_lat_lat, 6)],
            [round(incident_lng + d_lng_axial, 6), round(incident_lat + d_lat_lat * 0.82, 6)],
            [round(incident_lng + d_lng_axial, 6), round(incident_lat - d_lat_lat * 0.82, 6)],
            [round(incident_lng + d_lng_lat, 6), round(incident_lat, 6)],
            [round(incident_lng - d_lng_lat, 6), round(incident_lat, 6)],
        ]

    def _incident_avoid_polygon(
        self,
        incident_lng: float,
        incident_lat: float,
        severity: str,
        radius_multiplier: float = 1.0,
    ) -> list[list[float]]:
        radius_m = self.SEVERITY_RADIUS_M.get(severity, self.SEVERITY_RADIUS_M["moderate"]) * max(radius_multiplier, 0.1)
        dx = self._meters_to_lng_deg(radius_m, incident_lat)
        dy = self._meters_to_lat_deg(radius_m)
        return [
            [incident_lng - dx, incident_lat - dy],
            [incident_lng + dx, incident_lat - dy],
            [incident_lng + dx, incident_lat + dy],
            [incident_lng - dx, incident_lat + dy],
            [incident_lng - dx, incident_lat - dy],
        ]

    def _offset_point_m(self, lng: float, lat: float, dx_m: float, dy_m: float) -> list[float]:
        d_lng = self._meters_to_lng_deg(dx_m, lat)
        d_lat = self._meters_to_lat_deg(dy_m)
        return [round(lng + d_lng, 6), round(lat + d_lat, 6)]

    def _street_direction_vector(
        self,
        city: str,
        on_street: str,
        incident_lng: float,
        incident_lat: float,
        feed_segments: list[dict],
    ) -> Optional[tuple[float, float]]:
        street_tokens = self._tokens(on_street)
        if not street_tokens:
            return None

        candidates: list[tuple[float, tuple[float, float]]] = []

        # 1) Seeded road segments (preferred for stable direction).
        for seg in DEFAULT_ROAD_SEGMENTS.get(city, []):
            name = str(seg.get("name", ""))
            overlap = self._token_overlap(street_tokens, self._tokens(name))
            if overlap < self.MIN_STREET_MATCH_OVERLAP:
                continue
            s = seg.get("start_coords")
            e = seg.get("end_coords")
            if not s or not e or len(s) < 2 or len(e) < 2:
                continue
            start = (float(s[0]), float(s[1]))
            end = (float(e[0]), float(e[1]))
            vec = self._segment_unit_vector(start, end)
            if vec is None:
                continue
            mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
            dist = self._haversine_m(mid, (incident_lng, incident_lat))
            candidates.append((dist * (1.0 / max(overlap, 0.1)), vec))

        # 2) Feed points grouped by matching road names.
        feed_points: list[tuple[float, float]] = []
        for seg in feed_segments:
            name = str(seg.get("link_name", ""))
            overlap = self._token_overlap(street_tokens, self._tokens(name))
            if overlap < self.MIN_STREET_MATCH_OVERLAP:
                continue
            lat = seg.get("lat")
            lng = seg.get("lng")
            if lat is None or lng is None:
                continue
            point = (float(lng), float(lat))
            if self._haversine_m(point, (incident_lng, incident_lat)) > 1800:
                continue
            feed_points.append(point)

        if len(feed_points) >= 2:
            far_pair = None
            far_dist = 0.0
            for i in range(len(feed_points)):
                for j in range(i + 1, len(feed_points)):
                    d = self._haversine_m(feed_points[i], feed_points[j])
                    if d > far_dist:
                        far_dist = d
                        far_pair = (feed_points[i], feed_points[j])
            if far_pair and far_dist > 120:
                vec = self._segment_unit_vector(far_pair[0], far_pair[1])
                if vec is not None:
                    mid = ((far_pair[0][0] + far_pair[1][0]) / 2.0, (far_pair[0][1] + far_pair[1][1]) / 2.0)
                    dist = self._haversine_m(mid, (incident_lng, incident_lat))
                    candidates.append((dist * 0.92, vec))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    def _segment_unit_vector(self, start: tuple[float, float], end: tuple[float, float]) -> Optional[tuple[float, float]]:
        mean_lat = (start[1] + end[1]) / 2.0
        dx_m = (end[0] - start[0]) * 111_320.0 * max(math.cos(math.radians(mean_lat)), 0.2)
        dy_m = (end[1] - start[1]) * 111_320.0
        norm = math.sqrt((dx_m * dx_m) + (dy_m * dy_m))
        if norm <= 1e-6:
            return None
        return dx_m / norm, dy_m / norm

    # ---------------------------------------------------------------------
    # 2) ORS client
    # ---------------------------------------------------------------------

    async def _ors_route(
        self,
        coordinates: list[list[float]],
        avoid_polygons: Optional[list[list[list[float]]]],
    ) -> Optional[dict[str, Any]]:
        if not self.ors_api_key or httpx is None:
            return None

        body: dict[str, Any] = {
            "coordinates": coordinates,
            "instructions": True,
            "extra_info": ["roadaccessrestrictions"],
            "options": {"avoid_features": ["tollways"]},
        }
        # Allow snap-to-road tolerance for synthetic anchors/vias.
        body["radiuses"] = [260.0 for _ in coordinates]

        if avoid_polygons:
            parsed_polys = []
            for poly in avoid_polygons:
                norm = self._normalize_polygon(poly)
                if norm:
                    parsed_polys.append(norm)
            if parsed_polys:
                if len(parsed_polys) == 1:
                    body["options"]["avoid_polygons"] = {
                        "type": "Polygon",
                        "coordinates": [parsed_polys[0]],
                    }
                else:
                    body["options"]["avoid_polygons"] = {
                        "type": "MultiPolygon",
                        "coordinates": [[poly] for poly in parsed_polys],
                    }

        cache_key = self._ors_cache_key(body)
        cached = self._ors_cache.get(cache_key)
        now = time.time()
        if cached and (now - cached[0] <= self._ors_cache_ttl_sec):
            return cached[1]

        last_err = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                    resp = await client.post(
                        self.ORS_URL,
                        headers={
                            "Authorization": self.ors_api_key,
                            "Content-Type": "application/json",
                        },
                        json=body,
                    )
                    if not resp.is_success:
                        status = resp.status_code
                        text = resp.text[:300]
                        # Do not repeatedly retry non-recoverable failures.
                        if status in (400, 404, 422):
                            last_err = RuntimeError(f"ORS HTTP {status}: {text}")
                            break
                        # Retry rate-limit once, then stop.
                        if status == 429 and attempt >= 1:
                            last_err = RuntimeError(f"ORS HTTP {status}: {text}")
                            break
                        raise RuntimeError(f"ORS HTTP {status}: {text}")
                    parsed = self._parse_ors_response(resp.json())
                    if parsed and self._is_renderable(parsed["geometry"]["coordinates"]):
                        self._ors_cache[cache_key] = (now, parsed)
                        return parsed
            except Exception as e:
                last_err = e
                await asyncio.sleep(0.25 * (attempt + 1))
        logger.warning("ORS route failed after retries: %s", last_err)
        return None

    @staticmethod
    def _ors_cache_key(body: dict[str, Any]) -> str:
        return json.dumps(body, sort_keys=True, separators=(",", ":"))

    def _parse_ors_response(self, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        try:
            features = data.get("features") or []
            if not features:
                return None
            feature = features[0]
            geometry = feature.get("geometry") or {}
            coords = geometry.get("coordinates") or []
            if not coords:
                return None

            props = feature.get("properties") or {}
            summary = props.get("summary") or {}
            distance_m = float(summary.get("distance", 0) or 0)
            duration_s = float(summary.get("duration", 0) or 0)
            if distance_m <= 0:
                distance_m = self._polyline_km(coords) * 1000.0

            street_names = []
            segments = props.get("segments") or []
            for seg in segments:
                for step in seg.get("steps", []) or []:
                    name = (step.get("name") or "").strip()
                    if name and name not in street_names:
                        street_names.append(name)

            estimated_minutes = round(duration_s / 60.0, 2) if duration_s > 0 else self._estimate_minutes(
                distance_m / 1000.0,
                24.0,
            )
            return {
                "geometry": {"type": "LineString", "coordinates": coords},
                "total_length_km": round(distance_m / 1000.0, 3),
                "estimated_minutes": round(estimated_minutes, 2),
                "street_names": street_names,
            }
        except Exception:
            return None

    # ---------------------------------------------------------------------
    # 3) Candidate generation + locality guard
    # ---------------------------------------------------------------------

    def _passes_locality_guard(
        self,
        coords: list[list[float]],
        incident_lng: float,
        incident_lat: float,
        city: str,
        severity: str,
    ) -> bool:
        if not coords:
            return False
        max_allow_m = self.SEVERITY_MAX_POINT_DIST_M.get(severity, 900.0)
        for p in coords:
            d = self._haversine_m((p[0], p[1]), (incident_lng, incident_lat))
            if d > max_allow_m:
                return False
        lng_span, lat_span = self._bbox_span(coords)
        span_limit = self.BBOX_SPAN_GUARD.get(city, self.BBOX_SPAN_GUARD["nyc"])
        if lng_span > span_limit[0] or lat_span > span_limit[1]:
            return False
        return True

    # ---------------------------------------------------------------------
    # 4) A* scorer
    # ---------------------------------------------------------------------

    def _score_alternate_candidate(
        self,
        route: dict[str, Any],
        incident: tuple[float, float],
        severity: str,
        feed_segments: list[dict],
        expected_minutes: float,
        city: str,
        blocked_km: float,
    ) -> tuple[float, float, float, float]:
        coords = route.get("geometry", {}).get("coordinates", [])
        locality = self._locality_score(coords, incident, severity)
        congestion_pen = self._route_congestion_penalty(coords, feed_segments)
        duration = float(route.get("estimated_minutes", 0) or 0)
        loop_penalty = self._loop_turnback_penalty(coords)
        route_km = float(route.get("total_length_km", 0) or self._polyline_km(coords))
        detour_penalty = self._detour_ratio_penalty(
            alt_km=route_km,
            blocked_km=blocked_km,
            city=city,
            severity=severity,
        )
        divergence = abs(duration - expected_minutes) * 0.35
        total_score = duration + congestion_pen + (locality * 0.24) + divergence + loop_penalty + detour_penalty
        return total_score, locality, loop_penalty, detour_penalty

    def _passes_detour_guard(self, alt_km: float, blocked_km: float, city: str, severity: str) -> bool:
        abs_cap = self.ABS_ALT_MAX_KM.get(city, self.ABS_ALT_MAX_KM["nyc"]).get(severity, 3.0)
        if alt_km > abs_cap:
            return False
        base = max(blocked_km, 0.2)
        max_ratio = self.MAX_DETOUR_RATIO_BY_SEVERITY.get(severity, self.MAX_DETOUR_RATIO)
        return (alt_km / base) <= max_ratio

    def _detour_ratio_penalty(self, alt_km: float, blocked_km: float, city: str, severity: str) -> float:
        base = max(blocked_km, 0.2)
        ratio = alt_km / base
        penalty = 0.0
        soft_ratio = max(1.2, self.MAX_DETOUR_RATIO_BY_SEVERITY.get(severity, self.MAX_DETOUR_RATIO) - 0.28)
        if ratio > soft_ratio:
            penalty += (ratio - soft_ratio) * 8.0
        abs_cap = self.ABS_ALT_MAX_KM.get(city, self.ABS_ALT_MAX_KM["nyc"]).get(severity, 3.0)
        if alt_km > abs_cap:
            penalty += (alt_km - abs_cap) * 7.0
        return penalty

    def _loop_turnback_penalty(self, coords: list[list[float]]) -> float:
        if len(coords) < 4:
            return 0.0
        penalty = 0.0
        # Penalize direction flips.
        headings: list[tuple[float, float]] = []
        for i in range(1, len(coords)):
            a = coords[i - 1]
            b = coords[i]
            mean_lat = (a[1] + b[1]) / 2.0
            dx = (b[0] - a[0]) * 111_320.0 * max(math.cos(math.radians(mean_lat)), 0.2)
            dy = (b[1] - a[1]) * 111_320.0
            norm = math.sqrt((dx * dx) + (dy * dy))
            if norm <= 1e-6:
                continue
            headings.append((dx / norm, dy / norm))
        for i in range(1, len(headings)):
            dot = (headings[i - 1][0] * headings[i][0]) + (headings[i - 1][1] * headings[i][1])
            if dot < -0.35:
                penalty += 2.1

        # Penalize near self-crossing revisits.
        for i in range(len(coords)):
            for j in range(i + 3, len(coords)):
                if self._haversine_m((coords[i][0], coords[i][1]), (coords[j][0], coords[j][1])) < 35.0:
                    penalty += 2.3
                    break
        return penalty

    def _expected_alternate_minutes(
        self,
        graph: dict[str, Any],
        origin: list[float],
        destination: list[float],
        incident: tuple[float, float],
        severity: str,
        avoid_polygons: list[list[list[float]]],
    ) -> float:
        start = self._nearest_graph_node(graph, origin)
        end = self._nearest_graph_node(graph, destination)
        if not start or not end:
            return 8.0
        avoid_radius_m = self.SEVERITY_RADIUS_M.get(severity, 330.0) * 0.8
        _, minutes = self._astar_path(
            graph=graph,
            start_node=start,
            end_node=end,
            incident=incident,
            avoid_radius_m=avoid_radius_m,
            avoid_polygons=avoid_polygons,
            mode="alternate",
        )
        return minutes if minutes > 0 else 8.0

    # ---------------------------------------------------------------------
    # 5) Local A* fallback
    # ---------------------------------------------------------------------

    def _fallback_blocked_route(
        self,
        graph: dict[str, Any],
        origin: list[float],
        destination: list[float],
        incident: tuple[float, float],
        on_street: str,
    ) -> dict[str, Any]:
        start = self._nearest_graph_node(graph, origin)
        end = self._nearest_graph_node(graph, destination)
        if start and end:
            path_nodes, minutes = self._astar_path(
                graph=graph,
                start_node=start,
                end_node=end,
                incident=incident,
                avoid_radius_m=0.0,
                avoid_polygons=[],
                mode="blocked",
            )
            coords = self._path_nodes_to_coords(graph, path_nodes)
            if self._is_renderable(coords):
                return {
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "estimated_minutes": round(minutes, 2),
                    "total_length_km": round(self._polyline_km(coords), 3),
                    "street_names": [on_street] if on_street else [],
                }

        coords = self._ensure_renderable([origin, [incident[0], incident[1]], destination])
        return {
            "geometry": {"type": "LineString", "coordinates": coords},
            "estimated_minutes": self._estimate_minutes(self._polyline_km(coords), 14.0),
            "total_length_km": round(self._polyline_km(coords), 3),
            "street_names": [on_street] if on_street else [],
        }

    def _fallback_alternate_route(
        self,
        graph: dict[str, Any],
        origin: list[float],
        destination: list[float],
        incident: tuple[float, float],
        severity: str,
        on_street: str,
        avoid_polygons: list[list[list[float]]],
        feed_segments: list[dict],
        expected_minutes: float,
        city: str,
        blocked_km: float,
    ) -> tuple[dict[str, Any], float]:
        start = self._nearest_graph_node(graph, origin)
        end = self._nearest_graph_node(graph, destination)
        avoid_radius_m = self.SEVERITY_RADIUS_M.get(severity, 330.0) * 0.85

        if start and end:
            attempts = [
                (avoid_radius_m, avoid_polygons),
                (max(120.0, avoid_radius_m * 0.72), avoid_polygons),
                (max(100.0, avoid_radius_m * 0.55), []),
            ]
            for cur_avoid_radius, cur_polys in attempts:
                path_nodes, minutes = self._astar_path(
                    graph=graph,
                    start_node=start,
                    end_node=end,
                    incident=incident,
                    avoid_radius_m=cur_avoid_radius,
                    avoid_polygons=cur_polys,
                    mode="alternate",
                )
                coords = self._path_nodes_to_coords(graph, path_nodes)
                if not self._is_renderable(coords):
                    continue
                route = {
                    "geometry": {"type": "LineString", "coordinates": self._ensure_renderable(coords)},
                    "estimated_minutes": round(minutes, 2),
                    "total_length_km": round(self._polyline_km(coords), 3),
                    "street_names": [on_street] if on_street else [],
                }
                score, locality, _, _ = self._score_alternate_candidate(
                    route=route,
                    incident=incident,
                    severity=severity,
                    feed_segments=feed_segments,
                    expected_minutes=expected_minutes,
                    city=city,
                    blocked_km=blocked_km,
                )
                route["locality_score"] = locality
                return route, score

        # Never return a synthetic straight-line alternate route.
        return {
            "geometry": {"type": "LineString", "coordinates": []},
            "estimated_minutes": 0.0,
            "total_length_km": 0.0,
            "street_names": [on_street] if on_street else [],
            "locality_score": 0.0,
        }, 9999.0

    # ---------------------------------------------------------------------
    # Local graph + A*
    # ---------------------------------------------------------------------

    def _build_local_graph(self, city: str, feed_segments: list[dict]) -> dict[str, Any]:
        nodes: dict[str, tuple[float, float]] = {}
        edges: dict[str, list[_Edge]] = {}

        feed_enriched = []
        for fs in feed_segments:
            name = str(fs.get("link_name", "") or "")
            feed_enriched.append(
                {
                    "tokens": self._tokens(name),
                    "status": str(fs.get("status", "OK")).upper(),
                    "speed": float(fs.get("speed", 0) or 0),
                    "lat": float(fs.get("lat", 0) or 0),
                    "lng": float(fs.get("lng", 0) or 0),
                }
            )

        for seg in DEFAULT_ROAD_SEGMENTS.get(city, []):
            s = seg.get("start_coords")
            e = seg.get("end_coords")
            if not s or not e or len(s) < 2 or len(e) < 2:
                continue
            start = (float(s[0]), float(s[1]))
            end = (float(e[0]), float(e[1]))
            sid = self._node_id(start)
            eid = self._node_id(end)
            nodes[sid] = start
            nodes[eid] = end

            seg_name = str(seg.get("name", ""))
            base_len = float(seg.get("length_km", 0) or 0)
            if base_len <= 0:
                base_len = self._haversine_m(start, end) / 1000.0

            speed_peak = float(seg.get("avg_speed_peak_kmh", 0) or 0)
            speed_off = float(seg.get("avg_speed_offpeak_kmh", 0) or 0)
            speed_kmh = max((speed_peak + speed_off) / 2.0, 8.0)
            status_mult, blocked = self._status_multiplier(seg_name, feed_enriched)
            if blocked:
                travel_min = math.inf
            else:
                travel_min = (base_len / max(speed_kmh, 1.0)) * 60.0 * status_mult
            mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)

            edges.setdefault(sid, []).append(
                _Edge(
                    to_node=eid,
                    length_km=base_len,
                    travel_minutes=travel_min,
                    segment_name=seg_name,
                    midpoint=mid,
                    is_blocked=blocked,
                )
            )
            edges.setdefault(eid, []).append(
                _Edge(
                    to_node=sid,
                    length_km=base_len,
                    travel_minutes=travel_min,
                    segment_name=seg_name,
                    midpoint=mid,
                    is_blocked=blocked,
                )
            )

        return {"nodes": nodes, "edges": edges}

    def _status_multiplier(self, road_name: str, feed_enriched: list[dict]) -> tuple[float, bool]:
        road_tokens = self._tokens(road_name)
        best_overlap = 0.0
        best = None
        for item in feed_enriched:
            overlap = self._token_overlap(road_tokens, item["tokens"])
            if overlap > best_overlap:
                best_overlap = overlap
                best = item
        if not best or best_overlap < 0.30:
            return 1.0, False

        status = best["status"]
        speed = best["speed"]
        if status == "BLOCKED":
            return 1.0, True
        if status == "SLOW":
            mult = 2.2
            if speed > 0:
                mult = max(mult, min(3.2, 24.0 / speed))
            return mult, False
        if speed > 0:
            return max(1.0, min(2.0, 20.0 / speed)), False
        return 1.0, False

    def _astar_path(
        self,
        graph: dict[str, Any],
        start_node: str,
        end_node: str,
        incident: tuple[float, float],
        avoid_radius_m: float,
        avoid_polygons: list[list[list[float]]],
        mode: str,
    ) -> tuple[list[str], float]:
        nodes = graph.get("nodes", {})
        edges = graph.get("edges", {})
        if start_node not in nodes or end_node not in nodes:
            return [], 0.0

        dist: dict[str, float] = {start_node: 0.0}
        prev: dict[str, str] = {}
        pq = [(0.0, start_node)]
        seen = set()

        while pq:
            _, cur = heapq.heappop(pq)
            if cur in seen:
                continue
            seen.add(cur)
            if cur == end_node:
                break

            for edge in edges.get(cur, []):
                if edge.is_blocked or math.isinf(edge.travel_minutes):
                    continue
                if mode == "alternate":
                    cur_coord = nodes.get(cur)
                    nxt_coord = nodes.get(edge.to_node)
                    if avoid_radius_m > 0 and self._haversine_m(edge.midpoint, incident) < avoid_radius_m:
                        continue
                    if avoid_radius_m > 0 and cur_coord and self._haversine_m(cur_coord, incident) < avoid_radius_m:
                        continue
                    if avoid_radius_m > 0 and nxt_coord and self._haversine_m(nxt_coord, incident) < avoid_radius_m:
                        continue
                    if self._point_in_any_polygon(edge.midpoint, avoid_polygons):
                        continue
                    if cur_coord and self._point_in_any_polygon(cur_coord, avoid_polygons):
                        continue
                    if nxt_coord and self._point_in_any_polygon(nxt_coord, avoid_polygons):
                        continue
                base_cost = edge.travel_minutes + self._edge_locality_penalty(edge.midpoint, incident)
                nxt = edge.to_node
                cand = dist[cur] + base_cost
                if cand < dist.get(nxt, math.inf):
                    dist[nxt] = cand
                    prev[nxt] = cur
                    heuristic = self._haversine_m(nodes[nxt], nodes[end_node]) / 1000.0 / 35.0 * 60.0
                    heapq.heappush(pq, (cand + heuristic, nxt))

        if end_node not in dist:
            return [], 0.0

        path = [end_node]
        node = end_node
        while node != start_node and node in prev:
            node = prev[node]
            path.append(node)
        path.reverse()
        return path, float(dist.get(end_node, 0.0))

    def _edge_locality_penalty(self, midpoint: tuple[float, float], incident: tuple[float, float]) -> float:
        d = self._haversine_m(midpoint, incident)
        if d > 1300:
            return 4.0
        if d > 1000:
            return 2.5
        if d > 800:
            return 1.5
        return 0.0

    def _nearest_graph_node(self, graph: dict[str, Any], point: list[float]) -> Optional[str]:
        nodes = graph.get("nodes", {})
        if not nodes:
            return None
        best_node = None
        best_dist = math.inf
        p = (point[0], point[1])
        for nid, coord in nodes.items():
            d = self._haversine_m(coord, p)
            if d < best_dist:
                best_dist = d
                best_node = nid
        return best_node

    def _path_nodes_to_coords(self, graph: dict[str, Any], path_nodes: list[str]) -> list[list[float]]:
        nodes = graph.get("nodes", {})
        coords = []
        for nid in path_nodes:
            c = nodes.get(nid)
            if not c:
                continue
            coords.append([round(c[0], 6), round(c[1], 6)])
        return coords

    # ---------------------------------------------------------------------
    # Geometry helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def _node_id(coord: tuple[float, float]) -> str:
        return f"{coord[0]:.6f},{coord[1]:.6f}"

    @staticmethod
    def _tokens(name: str) -> set[str]:
        raw = "".join(ch.lower() if ch.isalnum() else " " for ch in (name or ""))
        return {t for t in raw.split() if t}

    @staticmethod
    def _token_overlap(a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        inter = len(a.intersection(b))
        denom = max(len(a), len(b))
        return inter / max(denom, 1)

    @staticmethod
    def _is_renderable(coords: list[list[float]]) -> bool:
        return isinstance(coords, list) and len(coords) >= 2

    def _ensure_renderable(self, coords: list[list[float]]) -> list[list[float]]:
        if self._is_renderable(coords):
            return coords
        if len(coords) == 1:
            c = coords[0]
            return [c, [round(c[0] + 0.00015, 6), round(c[1] + 0.0001, 6)]]
        return [[0.0, 0.0], [0.00015, 0.0001]]

    @staticmethod
    def _bbox_span(coords: list[list[float]]) -> tuple[float, float]:
        if not coords:
            return 0.0, 0.0
        lngs = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return max(lngs) - min(lngs), max(lats) - min(lats)

    def _locality_score(
        self,
        coords: list[list[float]],
        incident: tuple[float, float],
        severity: str,
    ) -> float:
        if not coords:
            return 999.0
        max_allow_m = self.SEVERITY_MAX_POINT_DIST_M.get(severity, 900.0)
        far_penalty = 0.0
        for p in coords:
            d = self._haversine_m((p[0], p[1]), incident)
            if d > max_allow_m:
                far_penalty += 20.0
            elif d > max_allow_m * 0.8:
                far_penalty += 3.0
        lng_span, lat_span = self._bbox_span(coords)
        return far_penalty + (lng_span * 100.0) + (lat_span * 120.0)

    def _route_congestion_penalty(self, coords: list[list[float]], feed_segments: list[dict]) -> float:
        if not coords or not feed_segments:
            return 0.0
        sample_step = max(1, len(coords) // 12)
        sampled = coords[::sample_step]
        penalty = 0.0
        for p in sampled:
            nearest = None
            nearest_m = math.inf
            for seg in feed_segments:
                slat = float(seg.get("lat", 0) or 0)
                slng = float(seg.get("lng", 0) or 0)
                if not slat and not slng:
                    continue
                d = self._haversine_m((p[0], p[1]), (slng, slat))
                if d < nearest_m:
                    nearest_m = d
                    nearest = seg
            if not nearest or nearest_m > 280.0:
                continue
            status = str(nearest.get("status", "OK")).upper()
            speed = float(nearest.get("speed", 0) or 0)
            if status == "BLOCKED":
                penalty += 8.0
            elif status == "SLOW":
                penalty += 2.8
            elif speed > 0 and speed < 11:
                penalty += 1.4
        return penalty

    def _normalize_polygon(self, poly: Any) -> Optional[list[list[float]]]:
        if not isinstance(poly, list) or len(poly) < 3:
            return None
        out = []
        for p in poly:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                continue
            out.append([float(p[0]), float(p[1])])
        if len(out) < 3:
            return None
        if out[0] != out[-1]:
            out.append(out[0])
        return out

    def _point_in_any_polygon(self, point: tuple[float, float], polys: list[list[list[float]]]) -> bool:
        for poly in polys:
            if self._point_in_polygon(point, poly):
                return True
        return False

    @staticmethod
    def _point_in_polygon(point: tuple[float, float], poly: list[list[float]]) -> bool:
        if not poly or len(poly) < 4:
            return False
        x, y = point
        inside = False
        j = len(poly) - 1
        for i in range(len(poly)):
            xi, yi = poly[i][0], poly[i][1]
            xj, yj = poly[j][0], poly[j][1]
            intersects = ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (max(yj - yi, 1e-12)) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside

    def _segments_corridor_geometry(self, segments: list[dict]) -> list[list[float]]:
        pts = []
        for s in segments:
            lat = s.get("lat")
            lng = s.get("lng")
            if lat is None or lng is None:
                continue
            pts.append([float(lng), float(lat)])
        if len(pts) < 2:
            return []
        center_lng = sum(p[0] for p in pts) / len(pts)
        center_lat = sum(p[1] for p in pts) / len(pts)
        pts.sort(key=lambda p: self._haversine_m((p[0], p[1]), (center_lng, center_lat)))
        if len(pts) > 6:
            pts = pts[:6]
        lng_span, lat_span = self._bbox_span(pts)
        if lng_span >= lat_span:
            pts.sort(key=lambda p: p[0])
        else:
            pts.sort(key=lambda p: p[1])
        return pts

    # ---------------------------------------------------------------------
    # Distance/time helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
        r = 6_371_000
        lng1, lat1 = math.radians(a[0]), math.radians(a[1])
        lng2, lat2 = math.radians(b[0]), math.radians(b[1])
        dlng = lng2 - lng1
        dlat = lat2 - lat1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        return 2 * r * math.asin(math.sqrt(h))

    def _polyline_km(self, coords: list[list[float]]) -> float:
        if len(coords) < 2:
            return 0.0
        total_m = 0.0
        for i in range(1, len(coords)):
            a = (coords[i - 1][0], coords[i - 1][1])
            b = (coords[i][0], coords[i][1])
            total_m += self._haversine_m(a, b)
        return total_m / 1000.0

    @staticmethod
    def _estimate_minutes(length_km: float, speed_kmh: float = 22.0) -> float:
        if speed_kmh <= 0:
            return 0.0
        return round((length_km / speed_kmh) * 60.0, 2)
