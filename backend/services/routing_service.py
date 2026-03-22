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
        "minor": 700.0,
        "moderate": 900.0,
        "major": 1200.0,
        "critical": 1600.0,
    }

    BBOX_SPAN_GUARD = {
        "nyc": (0.030, 0.025),
        "chandigarh": (0.040, 0.030),
    }

    ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"

    def __init__(self, ors_api_key: str = "", mapbox_token: str = ""):
        # mapbox_token retained for compatibility with older wiring.
        self.mapbox_token = mapbox_token
        self.ors_api_key = ors_api_key or os.getenv("ORS_API_KEY", "")
        self._ors_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._ors_cache_ttl_sec = 60.0
        self._http_timeout = 12.0

        # ORS: alternative_routes is incompatible with >2 waypoints
        if not has_waypoint:
            body["alternative_routes"] = {"target_count": 3, "weight_factor": 2.0, "share_factor": 0.3}
        
        if avoid_polygons_list:
            body["options"]["avoid_polygons"] = {
                "type": "MultiPolygon",
                "coordinates": [[p] for p in avoid_polygons_list]
            }
        elif avoid_polygon:
            body["options"]["avoid_polygons"] = {
                "type": "MultiPolygon",
                "coordinates": [[avoid_polygon]]
            }
        elif avoid_coords:
            body["options"]["avoid_polygons"] = {
                "type": "MultiPolygon",
                "coordinates": [[self._coord_to_polygon(c, 0.0005)] for c in avoid_coords]
            }
        
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        ORS_DIRECTIONS_URL,
                        headers={
                            "Authorization": self.api_key,
                            "Content-Type": "application/json"
                        },
                        json=body
                    )
                    if not response.is_success:
                        logger.error(f"ORS HTTP {response.status_code}: {response.text}")
                    response.raise_for_status()
                    result = response.json()
                
                # Pick the best alternative if multiple returned
                result = self._pick_best_alternative(result)
                self._cache[cache_key] = result
                logger.info(f"Route computed: {origin} -> {destination}")
                return result
                
            except Exception as e:
                logger.error(f"ORS routing failed (attempt {attempt+1}): {e}")
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(1)
                    continue
                # Return None instead of straight-line mock — routes should follow roads
                logger.warning("ORS failed, returning None (no straight-line fallback)")
                return None
    
    def _is_valid_geometry(self, geometry: dict | None, min_points: int = 5) -> bool:
        """Check if geometry is valid (has enough points to be a real road route).
        
        Real road routes have many coordinates following the road curve.
        Straight-line fallbacks only have 2-3 points (origin, maybe waypoint, destination).
        """
        if not geometry:
            return False
        coords = geometry.get("coordinates", [])
        return len(coords) >= min_points
    
    def extract_route_info(self, geojson_route: dict) -> dict:
        """Extract key info from an ORS GeoJSON route response."""
        if not geojson_route or "features" not in geojson_route:
            return {}
        
        feature = geojson_route["features"][0]
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        distance_m = props.get("summary", {}).get("distance", 0)
        duration_s = props.get("summary", {}).get("duration", 0)
        distance_km = distance_m / 1000
        
        # Extract street names from steps
        street_names = []
        for segment in props.get("segments", []):
            for step in segment.get("steps", []):
                name = step.get("name", "")
                if name and name not in street_names:
                    street_names.append(name)
        
        return {
            "geometry": geometry,
            "total_distance_km": round(distance_km, 2),
            "total_duration_min": round(duration_s / 60, 1),
            "avg_speed_kmh": round(distance_km / (duration_s / 3600), 1) if duration_s > 0 else 0,
            "street_names": street_names,
        }
    
    def _pick_best_alternative(self, geojson_response: dict) -> dict:
        """From ORS response with multiple alternatives, pick the shortest-distance route.
        
        Shortest distance produces the most natural, tight detour around an incident
        instead of high-speed routes through distant residential streets.
        """
        features = geojson_response.get("features", [])
        if not features:
            return geojson_response
        
        best = None
        best_distance = float("inf")
        
        for feature in features:
            props = feature.get("properties", {})
            summary = props.get("summary", {})
            distance = summary.get("distance", 0)  # meters
            
            if distance < best_distance:
                best_distance = distance
                best = feature
        
        if best:
            logger.info(f"Picked best alternate: {best_distance:.0f}m (from {len(features)} alternatives)")
            return {"type": "FeatureCollection", "features": [best]}
        return geojson_response
    
    async def get_congestion_avoid_polygons(self, city: str) -> list[list[list[float]]]:
        """Fetch default congestion zone polygons for routing avoidance."""
        try:
            import db as database
            if database.congestion_zones is None:
                return []
            cursor = database.congestion_zones.find(
                {"city": city, "source": "default", "status": "permanent"},
                {"polygon": 1}
            )
            polygons = []
            async for doc in cursor:
                if "polygon" in doc and len(doc["polygon"]) >= 4:
                    polygons.append(doc["polygon"])
            return polygons
        except Exception:
            return []
    
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
        )
        vias = self._build_candidate_vias(
            incident_lng=incident_lng,
            incident_lat=incident_lat,
            on_street=on_street,
            severity=severity,
        )

        incident_polygon = self._incident_avoid_polygon(
            incident_lng=incident_lng,
            incident_lat=incident_lat,
            severity=severity,
        )
        avoid_polygons = [incident_polygon]
        for poly in (extra_avoid_polygons or []):
            norm = self._normalize_polygon(poly)
            if norm:
                avoid_polygons.append(norm)

        local_graph = self._build_local_graph(city=city, feed_segments=feed_segments)
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
        ors_calls = 0

        if self.ors_api_key:
            blocked_ors = await self._ors_route(
                coordinates=[origin, [incident_lng, incident_lat], destination],
                avoid_polygons=None,
            )
            ors_calls += 1
            if blocked_ors and self._is_renderable(blocked_ors["geometry"]["coordinates"]):
                blocked_route = blocked_ors

            for via in vias:
                candidate = await self._ors_route(
                    coordinates=[origin, via, destination],
                    avoid_polygons=avoid_polygons,
                )
                ors_calls += 1
                if not candidate:
                    continue
                coords = candidate["geometry"]["coordinates"]
                if not self._is_renderable(coords):
                    continue
                if not self._passes_locality_guard(
                    coords=coords,
                    incident_lng=incident_lng,
                    incident_lat=incident_lat,
                    city=city,
                    severity=severity,
                ):
                    continue
                score, locality = self._score_alternate_candidate(
                    route=candidate,
                    incident=(incident_lng, incident_lat),
                    severity=severity,
                    feed_segments=feed_segments,
                    expected_minutes=expected_alt_minutes,
                )
                candidate["meta_score"] = score
                candidate["locality_score"] = locality
                alt_candidates.append(candidate)

        fallback_used = False
        astar_score = 0.0

        if not blocked_route:
            fallback_used = True
            blocked_route = self._fallback_blocked_route(
                graph=local_graph,
                origin=origin,
                destination=destination,
                incident=(incident_lng, incident_lat),
                on_street=on_street,
            )

        if alt_candidates:
            best_alt = min(alt_candidates, key=lambda c: c["meta_score"])
            alternate_route = best_alt
            astar_score = float(best_alt.get("meta_score", 0.0))
        else:
            fallback_used = True
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
            )

        blocked_coords = self._ensure_renderable(blocked_route["geometry"]["coordinates"])
        alt_coords = self._ensure_renderable(alternate_route["geometry"]["coordinates"])

        blocked_km = self._polyline_km(blocked_coords)
        alt_km = self._polyline_km(alt_coords)
        blocked_minutes = blocked_route.get("estimated_minutes") or self._estimate_minutes(blocked_km, 16.0)
        alt_minutes = alternate_route.get("estimated_minutes") or self._estimate_minutes(alt_km, 24.0)

        blocked_names = blocked_route.get("street_names") or ([on_street] if on_street else [])
        alt_names = alternate_route.get("street_names") or ([on_street] if on_street else [])

        local_score = alternate_route.get("locality_score")
        if local_score is None:
            local_score = self._locality_score(alt_coords, (incident_lng, incident_lat), severity)

        routing_engine = "ors+astar" if self.ors_api_key else "local_astar"
        routing_source = "ors_primary_v2" if self.ors_api_key else "local_astar_v2"

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
                "avg_speed_kmh": round((alt_km / (max(float(alt_minutes), 0.1) / 60.0)), 2),
                "street_names": alt_names,
                "locality_score": round(float(local_score), 2),
                "label": "SAFE ROUTE",
                "is_optimal": True,
            },
            "meta": {
                "routing_engine": routing_engine,
                "fallback_used": fallback_used,
                "ors_calls": int(ors_calls),
                "astar_score": round(float(astar_score), 2),
            },
            "routing_source": routing_source,
        }

        logger.info(
            "Route pair built (%s) city=%s blocked=%.3fkm alt=%.3fkm fallback=%s ors_calls=%s",
            routing_engine,
            city,
            blocked_km,
            alt_km,
            fallback_used,
            ors_calls,
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
            
            group = [c1]
            used.add(c1["id"])
            
            for j, c2 in enumerate(coords):
                if c2["id"] in used:
                    continue
                # Check if within proximity threshold
                dist = ((c1["lng"] - c2["lng"])**2 + (c1["lat"] - c2["lat"])**2) ** 0.5
                if dist <= proximity_threshold:
                    group.append(c2)
                    used.add(c2["id"])
            
            groups.append(group)
        
        # Generate consolidated routes for each group
        results = []
        for group in groups:
            if len(group) == 1:
                # Single incident - use standard route pair
                inc = group[0]
                route_pair = await self.compute_incident_route_pair(
                    inc["lng"], inc["lat"], city, inc["on_street"]
                )
                route_pair["incident_ids"] = [inc["id"]]
                route_pair["is_consolidated"] = False
                results.append(route_pair)
            else:
                # Multiple incidents - compute bounding box route
                lngs = [c["lng"] for c in group]
                lats = [c["lat"] for c in group]
                
                center_lng = sum(lngs) / len(lngs)
                center_lat = sum(lats) / len(lats)
                
                # Determine primary street (most common)
                streets = [c["on_street"] for c in group if c["on_street"]]
                primary_street = streets[0] if streets else ""
                
                # Expand to cover all incidents with padding
                padding = 0.003  # ~330m extra padding
                
                route_pair = await self.compute_incident_route_pair(
                    center_lng, center_lat, city, primary_street,
                    extra_avoid_polygons=[
                        self._bounding_box_polygon(
                            min(lngs) - padding, min(lats) - padding,
                            max(lngs) + padding, max(lats) + padding,
                        )
                    ]
                )
                route_pair["incident_ids"] = [c["id"] for c in group]
                route_pair["is_consolidated"] = True
                route_pair["group_center"] = [center_lng, center_lat]
                results.append(route_pair)
                
                logger.info(f"Consolidated {len(group)} incidents into single route pair")
        
        return results

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
    ) -> tuple[list[float], list[float]]:
        radius_m = self.SEVERITY_RADIUS_M.get(severity, self.SEVERITY_RADIUS_M["moderate"])
        axis_m = radius_m * 1.65
        if self._is_ns_street(on_street):
            d_lat = self._meters_to_lat_deg(axis_m)
            origin = [round(incident_lng, 6), round(incident_lat - d_lat, 6)]
            destination = [round(incident_lng, 6), round(incident_lat + d_lat, 6)]
        else:
            d_lng = self._meters_to_lng_deg(axis_m, incident_lat)
            origin = [round(incident_lng - d_lng, 6), round(incident_lat, 6)]
            destination = [round(incident_lng + d_lng, 6), round(incident_lat, 6)]
        return origin, destination

    def _build_candidate_vias(
        self,
        incident_lng: float,
        incident_lat: float,
        on_street: str,
        severity: str,
    ) -> list[list[float]]:
        radius_m = self.SEVERITY_RADIUS_M.get(severity, self.SEVERITY_RADIUS_M["moderate"])
        lateral_m = radius_m * 1.25
        axial_m = radius_m * 0.95

        d_lat_lat = self._meters_to_lat_deg(lateral_m)
        d_lng_lat = self._meters_to_lng_deg(lateral_m, incident_lat)
        d_lat_axial = self._meters_to_lat_deg(axial_m)
        d_lng_axial = self._meters_to_lng_deg(axial_m, incident_lat)

        if self._is_ns_street(on_street):
            return [
                [round(incident_lng + d_lng_lat, 6), round(incident_lat, 6)],
                [round(incident_lng - d_lng_lat, 6), round(incident_lat, 6)],
                [round(incident_lng + d_lng_lat * 0.9, 6), round(incident_lat + d_lat_axial, 6)],
                [round(incident_lng - d_lng_lat * 0.9, 6), round(incident_lat + d_lat_axial, 6)],
                [round(incident_lng, 6), round(incident_lat + d_lat_lat, 6)],
                [round(incident_lng, 6), round(incident_lat - d_lat_lat, 6)],
            ]
        return [
            [round(incident_lng, 6), round(incident_lat + d_lat_lat, 6)],
            [round(incident_lng, 6), round(incident_lat - d_lat_lat, 6)],
            [round(incident_lng + d_lng_axial, 6), round(incident_lat + d_lat_lat * 0.9, 6)],
            [round(incident_lng + d_lng_axial, 6), round(incident_lat - d_lat_lat * 0.9, 6)],
            [round(incident_lng + d_lng_lat, 6), round(incident_lat, 6)],
            [round(incident_lng - d_lng_lat, 6), round(incident_lat, 6)],
        ]

    def _incident_avoid_polygon(
        self,
        incident_lng: float,
        incident_lat: float,
        severity: str,
    ) -> list[list[float]]:
        radius_m = self.SEVERITY_RADIUS_M.get(severity, self.SEVERITY_RADIUS_M["moderate"])
        dx = self._meters_to_lng_deg(radius_m, incident_lat)
        dy = self._meters_to_lat_deg(radius_m)
        return [
            [incident_lng - dx, incident_lat - dy],
            [incident_lng + dx, incident_lat - dy],
            [incident_lng + dx, incident_lat + dy],
            [incident_lng - dx, incident_lat + dy],
            [incident_lng - dx, incident_lat - dy],
        ]

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
                        text = resp.text[:300]
                        raise RuntimeError(f"ORS HTTP {resp.status_code}: {text}")
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
    ) -> tuple[float, float]:
        coords = route.get("geometry", {}).get("coordinates", [])
        locality = self._locality_score(coords, incident, severity)
        congestion_pen = self._route_congestion_penalty(coords, feed_segments)
        duration = float(route.get("estimated_minutes", 0) or 0)
        divergence = abs(duration - expected_minutes) * 0.35
        total_score = duration + congestion_pen + (locality * 0.22) + divergence
        return total_score, locality

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
    ) -> tuple[dict[str, Any], float]:
        start = self._nearest_graph_node(graph, origin)
        end = self._nearest_graph_node(graph, destination)
        avoid_radius_m = self.SEVERITY_RADIUS_M.get(severity, 330.0) * 0.85

        if start and end:
            path_nodes, minutes = self._astar_path(
                graph=graph,
                start_node=start,
                end_node=end,
                incident=incident,
                avoid_radius_m=avoid_radius_m,
                avoid_polygons=avoid_polygons,
                mode="alternate",
            )
            coords = self._path_nodes_to_coords(graph, path_nodes)
            if self._is_renderable(coords):
                route = {
                    "geometry": {"type": "LineString", "coordinates": self._ensure_renderable(coords)},
                    "estimated_minutes": round(minutes, 2),
                    "total_length_km": round(self._polyline_km(coords), 3),
                    "street_names": [on_street] if on_street else [],
                }
                score, locality = self._score_alternate_candidate(
                    route=route,
                    incident=incident,
                    severity=severity,
                    feed_segments=feed_segments,
                    expected_minutes=expected_minutes,
                )
                route["locality_score"] = locality
                return route, score

        via = self._build_candidate_vias(
            incident_lng=incident[0],
            incident_lat=incident[1],
            on_street=on_street,
            severity=severity,
        )[0]
        coords = self._ensure_renderable([origin, via, destination])
        route = {
            "geometry": {"type": "LineString", "coordinates": coords},
            "estimated_minutes": self._estimate_minutes(self._polyline_km(coords), 22.0),
            "total_length_km": round(self._polyline_km(coords), 3),
            "street_names": [on_street] if on_street else [],
        }
        score, locality = self._score_alternate_candidate(
            route=route,
            incident=incident,
            severity=severity,
            feed_segments=feed_segments,
            expected_minutes=expected_minutes,
        )
        route["locality_score"] = locality
        return route, score

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
                    if avoid_radius_m > 0 and self._haversine_m(edge.midpoint, incident) < avoid_radius_m:
                        continue
                    if self._point_in_any_polygon(edge.midpoint, avoid_polygons):
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
