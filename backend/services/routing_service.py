import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"


class RoutingService:
    """Computes diversion routes via OpenRouteService API."""
    
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._cache: dict[str, dict] = {}
    
    async def get_diversion_route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        avoid_coords: Optional[list[tuple[float, float]]] = None,
        waypoint: Optional[tuple[float, float]] = None,
        avoid_polygon: Optional[list] = None,
        avoid_polygons_list: Optional[list[list]] = None,
    ) -> Optional[dict]:
        """
        Compute a route from origin to destination.
        origin/destination: (longitude, latitude) tuples.
        waypoint: optional forced intermediate coordinate to push ORS onto a different road.
        avoid_polygon: pre-built closed ring polygon (takes precedence over avoid_coords).
        avoid_coords: list of (lng, lat) points to avoid via per-point square polygons.
        Returns GeoJSON FeatureCollection with route geometry and instructions.
        """
        cache_key = f"{origin}_{destination}_{bool(avoid_coords)}_{waypoint}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.api_key:
            logger.warning("ORS API key not configured, returning mock route")
            return self._mock_route(origin, destination)
        
        coords = [list(origin)]
        if waypoint:
            coords.append(list(waypoint))
        coords.append(list(destination))

        body = {
            "coordinates": coords,
            "instructions": True,
            "preference": "recommended",
            "alternative_routes": {"target_count": 3, "weight_factor": 1.6, "share_factor": 0.6},
            "options": {
                "avoid_features": ["ferries", "tollways"]
            }
        }
        
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
                "coordinates": [
                    [self._coord_to_polygon(c, 0.0005) for c in avoid_coords]
                ]
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
                return self._mock_route(origin, destination)
    
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
        """From ORS response with multiple alternatives, pick the one with highest avg speed."""
        features = geojson_response.get("features", [])
        if not features:
            return geojson_response
        
        best = None
        best_avg_speed = -1
        
        for feature in features:
            props = feature.get("properties", {})
            summary = props.get("summary", {})
            distance = summary.get("distance", 0)  # meters
            duration = summary.get("duration", 0)  # seconds
            
            if duration > 0:
                avg_speed = (distance / 1000) / (duration / 3600)  # km/h
            else:
                avg_speed = 0
            
            if avg_speed > best_avg_speed:
                best_avg_speed = avg_speed
                best = feature
        
        if best:
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
    ) -> dict:
        """
        Compute blocked road (red) + best alternate route (green) for an incident.

        Strategy:
        - Origin = ~800m upstream of incident (diagonal offset)
        - Destination = ~800m downstream of incident (diagonal offset)
        - Blocked route = ORS direct path origin→destination (the road being blocked, shown RED)
        - Alternate route = ORS path origin→destination AVOIDING incident point (shown GREEN)

        Returns: {"blocked": {...}, "alternate": {...}, "origin": [lng, lat], "destination": [lng, lat]}
        """
        # Diagonal offset ~800m works for both N-S and E-W oriented roads
        # 0.008° lat ≈ 890m, 0.009° lng ≈ 750m at NYC latitude (40.7°)
        # For Chandigarh (30.7°): 0.009° lng ≈ 865m
        lat_offset = 0.007
        lng_offset = 0.009

        origin = (round(incident_lng - lng_offset, 6), round(incident_lat - lat_offset, 6))
        destination = (round(incident_lng + lng_offset, 6), round(incident_lat + lat_offset, 6))

        logger.info(f"Computing incident route pair: origin={origin} dest={destination} incident=({incident_lng},{incident_lat})")

        # Fetch default congestion zone polygons to also avoid
        congestion_polys = await self.get_congestion_avoid_polygons(city)

        # Blocked road: direct route through the incident area (no avoidance)
        blocked_raw = await self.get_diversion_route(origin, destination, avoid_coords=None)
        blocked_info = self.extract_route_info(blocked_raw) if blocked_raw else {}

        # Single-point incident: build a 0.005° padding box around the incident
        incident_corridor = self._bounding_box_polygon(
            incident_lng - 0.003, incident_lat - 0.003,
            incident_lng + 0.003, incident_lat + 0.003,
        )

        # Forced perpendicular waypoint — offset in latitude to reach a parallel E-W street
        waypoint_lat_offset = 0.006
        waypoint = (round(incident_lng, 6), round(incident_lat + waypoint_lat_offset, 6))

        # Alternate route: try with avoidance polygon + congestion zones
        all_avoid_polys = [incident_corridor] + congestion_polys
        alt_raw = await self.get_diversion_route(
            origin, destination,
            avoid_polygons_list=all_avoid_polys,
        )

        # If alternate route is too similar to blocked route, force a waypoint
        if alt_raw and blocked_raw:
            try:
                alt_coords = alt_raw.get("features", [{}])[0].get("geometry", {}).get("coordinates", [])
                blk_coords = blocked_raw.get("features", [{}])[0].get("geometry", {}).get("coordinates", [])
                if self._routes_too_similar(blk_coords, alt_coords):
                    logger.info("Alternate too similar to blocked — adding forced waypoint")
                    alt_raw = await self.get_diversion_route(
                        origin, destination,
                        waypoint=waypoint,
                        avoid_polygons_list=all_avoid_polys,
                    )
            except Exception:
                pass  # Keep the non-waypoint alternate

        alt_info = self.extract_route_info(alt_raw) if alt_raw else {}

        return {
            "origin": list(origin),
            "destination": list(destination),
            "blocked": {
                "geometry": blocked_info.get("geometry", {"type": "LineString", "coordinates": [list(origin), [incident_lng, incident_lat], list(destination)]}),
                "total_length_km": blocked_info.get("total_distance_km", 0),
                "street_names": blocked_info.get("street_names", []),
            },
            "alternate": {
                "geometry": alt_info.get("geometry", {"type": "LineString", "coordinates": [list(origin), list(destination)]}),
                "total_length_km": alt_info.get("total_distance_km", 0),
                "estimated_extra_minutes": alt_info.get("total_duration_min", 0),
                "avg_speed_kmh": alt_info.get("avg_speed_kmh", 0),
                "street_names": alt_info.get("street_names", []),
            },
        }

    async def compute_congestion_route_pair(
        self,
        congested_segments: list[dict],
        city: str = "nyc",
    ) -> dict:
        """
        Compute blocked road (red) + best alternate route (green) for a congestion zone.
        
        Uses segment bounding box to find the true entry/exit points of the congested road,
        rather than a fixed diagonal offset from a single center point.
        
        - Entry (origin) = point just upstream of congestion zone
        - Exit (destination) = point just downstream of congestion zone
        - Red line = ORS direct route through congestion (the blocked road)
        - Green line = ORS route avoiding ALL congested segment positions
        """
        lats = [s["lat"] for s in congested_segments if s.get("lat")]
        lngs = [s["lng"] for s in congested_segments if s.get("lng")]

        if not lats or not lngs:
            logger.warning("compute_congestion_route_pair: no valid segment coords, falling back to incident pair")
            avg_lat = sum(lats) / len(lats) if lats else 0
            avg_lng = sum(lngs) / len(lngs) if lngs else 0
            return await self.compute_incident_route_pair(avg_lng, avg_lat, city)

        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)
        center_lat = (min_lat + max_lat) / 2
        center_lng = (min_lng + max_lng) / 2
        lat_span = max_lat - min_lat
        lng_span = max_lng - min_lng

        offset = 0.008  # ~900m upstream/downstream of the congested zone

        if lat_span >= lng_span:
            # N-S oriented road — offset along latitude
            origin = (round(center_lng, 6), round(min_lat - offset, 6))
            destination = (round(center_lng, 6), round(max_lat + offset, 6))
        else:
            # E-W oriented road — offset along longitude
            origin = (round(min_lng - offset, 6), round(center_lat, 6))
            destination = (round(max_lng + offset, 6), round(center_lat, 6))

        logger.info(
            f"Congestion route pair: origin={origin} dest={destination} "
            f"zone={len(congested_segments)} segments ({lat_span:.4f}°lat × {lng_span:.4f}°lng)"
        )

        # Build corridor polygon (with 0.003° padding = ~330m)
        corridor_polygon = self._bounding_box_polygon(
            min_lng - 0.002, min_lat - 0.002,
            max_lng + 0.002, max_lat + 0.002
        )

        # Forced perpendicular waypoint to ensure ORS uses a different road
        if lat_span >= lng_span:  # N-S road → offset in longitude
            waypoint = (round(center_lng + 0.007, 6), round(center_lat, 6))
        else:  # E-W road → offset in latitude
            waypoint = (round(center_lng, 6), round(center_lat + 0.007, 6))

        # Blocked (red): direct route through the congested zone
        blocked_raw = await self.get_diversion_route(origin, destination, avoid_coords=None)
        blocked_info = self.extract_route_info(blocked_raw) if blocked_raw else {}

        # Try without waypoint first
        alt_raw = await self.get_diversion_route(
            origin, destination,
            avoid_polygon=corridor_polygon,
        )

        # Add waypoint only if routes are too similar
        if alt_raw and blocked_raw:
            try:
                alt_coords = alt_raw.get("features", [{}])[0].get("geometry", {}).get("coordinates", [])
                blk_coords = blocked_raw.get("features", [{}])[0].get("geometry", {}).get("coordinates", [])
                if self._routes_too_similar(blk_coords, alt_coords):
                    logger.info("Congestion alternate too similar — adding forced waypoint")
                    alt_raw = await self.get_diversion_route(
                        origin, destination,
                        waypoint=waypoint,
                        avoid_polygon=corridor_polygon,
                    )
            except Exception:
                pass

        alt_info = self.extract_route_info(alt_raw) if alt_raw else {}

        fallback_blocked = {
            "type": "LineString",
            "coordinates": [list(origin), [center_lng, center_lat], list(destination)],
        }
        fallback_alt = {"type": "LineString", "coordinates": [list(origin), list(destination)]}

        return {
            "origin": list(origin),
            "destination": list(destination),
            "blocked": {
                "geometry": blocked_info.get("geometry", fallback_blocked),
                "total_length_km": blocked_info.get("total_distance_km", 0),
                "street_names": blocked_info.get("street_names", []),
            },
            "alternate": {
                "geometry": alt_info.get("geometry", fallback_alt),
                "total_length_km": alt_info.get("total_distance_km", 0),
                "estimated_extra_minutes": alt_info.get("total_duration_min", 0),
                "avg_speed_kmh": alt_info.get("avg_speed_kmh", 0),
                "street_names": alt_info.get("street_names", []),
            },
        }

    async def compute_diversions_for_incident(
        self, incident_location: tuple[float, float],
        city: str = "nyc"
    ) -> list[dict]:
        """
        Compute multiple diversion routes around an incident.
        Returns a list of prioritized route options.
        """
        # Define diversion endpoints based on city
        if city == "nyc":
            # NYC diversion endpoints around W 34th St area
            diversion_pairs = [
                {
                    "name": "Diversion A",
                    "origin": (-73.9980, 40.7579),   # 10th Ave & 42nd St
                    "destination": (-73.9895, 40.7498),  # 7th Ave & 33rd St
                },
                {
                    "name": "Diversion B", 
                    "origin": (-73.9939, 40.7580),   # 9th Ave & 42nd St
                    "destination": (-73.9878, 40.7484),  # Broadway & 34th St
                },
            ]
        else:
            # Chandigarh diversions around Madhya Marg
            diversion_pairs = [
                {
                    "name": "Diversion A",
                    "origin": (76.7788, 30.7412),    # Sector 17 Chowk
                    "destination": (76.7675, 30.7270),  # Tribune Chowk
                },
                {
                    "name": "Diversion B",
                    "origin": (76.7760, 30.7646),    # PGI Chowk
                    "destination": (76.7780, 30.7320),  # Sector 22 Chowk
                },
            ]
        
        results = []
        for i, pair in enumerate(diversion_pairs):
            route = await self.get_diversion_route(
                pair["origin"], pair["destination"],
                avoid_coords=[incident_location]
            )
            if route:
                info = self.extract_route_info(route)
                results.append({
                    "priority": i + 1,
                    "name": pair["name"],
                    "segment_names": info.get("street_names", []),
                    "geometry": info.get("geometry", {}),
                    "total_length_km": info.get("total_distance_km", 0),
                    "estimated_extra_minutes": info.get("total_duration_min", 0),
                })
        
        return results
    
    def _bounding_box_polygon(self, min_lng: float, min_lat: float, max_lng: float, max_lat: float) -> list:
        """Return a closed polygon ring covering the bounding box."""
        return [
            [min_lng, min_lat],
            [max_lng, min_lat],
            [max_lng, max_lat],
            [min_lng, max_lat],
            [min_lng, min_lat],  # close the ring
        ]

    @staticmethod
    def _routes_too_similar(coords_a: list, coords_b: list, threshold: float = 0.7) -> bool:
        """Check if two routes share too many coordinates (are nearly the same path).
        
        Returns True if >threshold fraction of coords_b midpoints are within 0.001° of coords_a.
        """
        if not coords_a or not coords_b:
            return True  # No data — assume similar, force waypoint
        
        # Sample every 3rd coordinate for efficiency
        sample_b = coords_b[::3] if len(coords_b) > 6 else coords_b
        if not sample_b:
            return True
        
        matches = 0
        for cb in sample_b:
            for ca in coords_a:
                if abs(cb[0] - ca[0]) < 0.001 and abs(cb[1] - ca[1]) < 0.001:
                    matches += 1
                    break
        
        similarity = matches / len(sample_b)
        logger.info(f"Route similarity: {similarity:.2f} (threshold={threshold})")
        return similarity > threshold

    def _coord_to_polygon(self, coord: tuple[float, float], radius: float = 0.0005) -> list:
        """Create a simple square polygon around a coordinate for avoidance."""
        lng, lat = coord
        return [
            [lng - radius, lat - radius],
            [lng + radius, lat - radius],
            [lng + radius, lat + radius],
            [lng - radius, lat + radius],
            [lng - radius, lat - radius],
        ]
    
    def _mock_route(self, origin: tuple, destination: tuple) -> dict:
        """Return a mock route when ORS API is unavailable."""
        return {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [list(origin), list(destination)]
                },
                "properties": {
                    "summary": {"distance": 2300, "duration": 480},
                    "segments": [{
                        "steps": [
                            {"name": "Alternate Route", "distance": 2300, "duration": 480}
                        ]
                    }]
                }
            }]
        }
    
    async def get_congestion_avoid_polygons(self, city: str) -> list[list[list[float]]]:
        """Fetch default congestion zone polygons for a city to use as ORS avoid areas."""
        if database.congestion_zones is None:
            return []
        try:
            cursor = database.congestion_zones.find(
                {"city": city, "source": "default", "status": "permanent"},
                {"polygon": 1}
            )
            polygons = []
            async for doc in cursor:
                if "polygon" in doc and len(doc["polygon"]) >= 4:
                    polygons.append(doc["polygon"])
            return polygons
        except Exception as e:
            logger.warning(f"Failed to fetch congestion zones: {e}")
            return []

    def clear_cache(self):
        self._cache.clear()
