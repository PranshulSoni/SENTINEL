import logging
import math
from typing import Optional


logger = logging.getLogger(__name__)


class RoutingService:
    """
    Route planner v2.

    The v2 planner intentionally prefers local, focused geometries:
    - blocked route: direct segment through incident
    - alternate route: short detour around incident
    """

    SEVERITY_RADIUS_DEG = {
        "critical": 0.0054,  # ~600m
        "major": 0.0040,     # ~450m
        "moderate": 0.0030,  # ~330m
        "minor": 0.0020,     # ~220m
    }

    SEVERITY_DETOUR_FACTOR = {
        "critical": 1.20,
        "major": 1.05,
        "moderate": 0.90,
        "minor": 0.75,
    }

    def __init__(self, mapbox_token: str = ""):
        # Kept for backward compatibility with existing config.
        self.mapbox_token = mapbox_token

    @staticmethod
    def _is_ns_street(on_street: str) -> bool:
        street = (on_street or "").lower()
        return any(
            kw in street
            for kw in ["ave", "avenue", "broadway", "blvd", "boulevard", "marg", "path", "road", "rd"]
        )

    @staticmethod
    def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
        """Distance in meters for (lng, lat) tuples."""
        r = 6371000
        lng1, lat1 = math.radians(a[0]), math.radians(a[1])
        lng2, lat2 = math.radians(b[0]), math.radians(b[1])
        dlng = lng2 - lng1
        dlat = lat2 - lat1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        return 2 * r * math.asin(math.sqrt(h))

    def _polyline_km(self, coords: list[list[float]]) -> float:
        if len(coords) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(coords)):
            total += self._haversine_m((coords[i - 1][0], coords[i - 1][1]), (coords[i][0], coords[i][1]))
        return round(total / 1000.0, 3)

    def _estimate_minutes(self, length_km: float, speed_kmh: float = 22.0) -> float:
        if speed_kmh <= 0:
            return 0.0
        return round((length_km / speed_kmh) * 60.0, 2)

    @staticmethod
    def _bbox_span(coords: list[list[float]]) -> tuple[float, float]:
        if not coords:
            return (0.0, 0.0)
        lngs = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return (max(lngs) - min(lngs), max(lats) - min(lats))

    def _locality_score(self, coords: list[list[float]]) -> float:
        lng_span, lat_span = self._bbox_span(coords)
        # Lower is better. Penalize city-spanning candidates.
        score = 0.0
        if lng_span > 0.01 or lat_span > 0.008:
            score += 100.0
        elif lng_span > 0.007 or lat_span > 0.005:
            score += 40.0
        elif lng_span > 0.0045 or lat_span > 0.0035:
            score += 12.0
        return score

    @staticmethod
    def _polygon_center(poly: list[list[float]]) -> Optional[tuple[float, float]]:
        if not poly or len(poly) < 4:
            return None
        pts = poly[:4]
        lng = sum(p[0] for p in pts) / 4
        lat = sum(p[1] for p in pts) / 4
        return (lng, lat)

    def _avoidance_bias(
        self,
        incident_lng: float,
        incident_lat: float,
        extra_avoid_polygons: list | None = None,
    ) -> tuple[int, int]:
        """
        Decide preferred detour side from nearby avoid zones.
        Returns (ns_sign, ew_sign):
        - ns_sign: +1 north, -1 south
        - ew_sign: +1 east, -1 west
        """
        ns_sign = 1
        ew_sign = 1
        if not extra_avoid_polygons:
            return (ns_sign, ew_sign)

        north_weight = south_weight = east_weight = west_weight = 0.0
        incident = (incident_lng, incident_lat)
        for poly in extra_avoid_polygons:
            center = self._polygon_center(poly)
            if center is None:
                continue
            dist = max(self._haversine_m(center, incident), 1.0)
            w = 1.0 / dist
            if center[1] >= incident_lat:
                north_weight += w
            else:
                south_weight += w
            if center[0] >= incident_lng:
                east_weight += w
            else:
                west_weight += w

        if north_weight > south_weight:
            ns_sign = -1
        if east_weight > west_weight:
            ew_sign = -1
        return (ns_sign, ew_sign)

    def _build_local_routes(
        self,
        incident_lng: float,
        incident_lat: float,
        on_street: str,
        severity: str,
        extra_avoid_polygons: list | None = None,
    ) -> tuple[list[float], list[float], list[list[float]], list[list[float]]]:
        radius = self.SEVERITY_RADIUS_DEG.get(severity, self.SEVERITY_RADIUS_DEG["moderate"])
        axis_offset = radius * 2.05
        detour = radius * self.SEVERITY_DETOUR_FACTOR.get(severity, 0.9)

        is_ns = self._is_ns_street(on_street)
        ns_sign, ew_sign = self._avoidance_bias(incident_lng, incident_lat, extra_avoid_polygons)

        if is_ns:
            origin = [round(incident_lng, 6), round(incident_lat - axis_offset, 6)]
            destination = [round(incident_lng, 6), round(incident_lat + axis_offset, 6)]
            blocked = [
                origin,
                [round(incident_lng, 6), round(incident_lat, 6)],
                destination,
            ]

            # Two local candidates: east bypass and west bypass.
            east_x = round(incident_lng + detour, 6)
            west_x = round(incident_lng - detour, 6)
            alt_east = [
                origin,
                [east_x, origin[1]],
                [east_x, destination[1]],
                destination,
            ]
            alt_west = [
                origin,
                [west_x, origin[1]],
                [west_x, destination[1]],
                destination,
            ]
            # Bias from other avoid zones.
            preferred = alt_east if ew_sign > 0 else alt_west
            secondary = alt_west if ew_sign > 0 else alt_east
        else:
            origin = [round(incident_lng - axis_offset, 6), round(incident_lat, 6)]
            destination = [round(incident_lng + axis_offset, 6), round(incident_lat, 6)]
            blocked = [
                origin,
                [round(incident_lng, 6), round(incident_lat, 6)],
                destination,
            ]

            north_y = round(incident_lat + detour, 6)
            south_y = round(incident_lat - detour, 6)
            alt_north = [
                origin,
                [origin[0], north_y],
                [destination[0], north_y],
                destination,
            ]
            alt_south = [
                origin,
                [origin[0], south_y],
                [destination[0], south_y],
                destination,
            ]
            preferred = alt_north if ns_sign > 0 else alt_south
            secondary = alt_south if ns_sign > 0 else alt_north

        # Deterministic scoring for locality and overlap to choose best candidate.
        preferred_score = self._locality_score(preferred)
        secondary_score = self._locality_score(secondary)
        alternate = preferred if preferred_score <= secondary_score else secondary

        return origin, destination, blocked, alternate

    async def compute_incident_route_pair(
        self,
        incident_lng: float,
        incident_lat: float,
        city: str = "nyc",
        on_street: str = "",
        extra_avoid_polygons: list | None = None,
        severity: str = "moderate",
    ) -> dict:
        origin, destination, blocked_coords, alternate_coords = self._build_local_routes(
            incident_lng=incident_lng,
            incident_lat=incident_lat,
            on_street=on_street,
            severity=severity,
            extra_avoid_polygons=extra_avoid_polygons,
        )

        blocked_km = self._polyline_km(blocked_coords)
        alt_km = self._polyline_km(alternate_coords)
        blocked_minutes = self._estimate_minutes(blocked_km, speed_kmh=14.0)
        alt_minutes = self._estimate_minutes(alt_km, speed_kmh=22.0)
        locality_score = self._locality_score(alternate_coords)

        result = {
            "version": "v2",
            "city": city,
            "origin": origin,
            "destination": destination,
            "blocked": {
                "geometry": {"type": "LineString", "coordinates": blocked_coords},
                "total_length_km": blocked_km,
                "street_names": [on_street] if on_street else [],
                "estimated_minutes": blocked_minutes,
                "label": "BLOCKED ROAD",
            },
            "alternate": {
                "geometry": {"type": "LineString", "coordinates": alternate_coords},
                "total_length_km": alt_km,
                "estimated_extra_minutes": round(max(alt_minutes - blocked_minutes, 0.0), 2),
                "estimated_minutes": alt_minutes,
                "avg_speed_kmh": round((alt_km / (alt_minutes / 60.0)), 2) if alt_minutes > 0 else 0.0,
                "street_names": [on_street] if on_street else [],
                "locality_score": locality_score,
                "label": "SAFE ROUTE",
                "is_optimal": True,
            },
            "routing_source": "local_v2",
        }
        logger.info(
            "Route pair v2 computed | blocked=%.3fkm alt=%.3fkm locality=%.1f street='%s'",
            blocked_km,
            alt_km,
            locality_score,
            on_street,
        )
        return result

    async def compute_congestion_route_pair(
        self,
        congested_segments: list[dict],
        city: str = "nyc",
    ) -> dict:
        if not congested_segments:
            return await self.compute_incident_route_pair(0.0, 0.0, city=city, on_street="", severity="moderate")

        lats = [float(s.get("lat", 0)) for s in congested_segments if s.get("lat") is not None]
        lngs = [float(s.get("lng", 0)) for s in congested_segments if s.get("lng") is not None]
        if not lats or not lngs:
            return await self.compute_incident_route_pair(0.0, 0.0, city=city, on_street="", severity="moderate")

        center_lat = sum(lats) / len(lats)
        center_lng = sum(lngs) / len(lngs)
        primary_street = str(congested_segments[0].get("link_name", ""))

        return await self.compute_incident_route_pair(
            incident_lng=center_lng,
            incident_lat=center_lat,
            city=city,
            on_street=primary_street,
            severity="moderate",
        )

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
        # No in-memory cache currently used in v2 planner.
        return None
