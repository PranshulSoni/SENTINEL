import asyncio
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
        self._snap_cache: dict[str, tuple[float, float]] = {}
    
    async def snap_to_road(self, coord: tuple[float, float], radius: float = 500) -> tuple[float, float]:
        """Snap a coordinate to the nearest routable road.
        
        Uses a short routing request to let ORS find the nearest routable point.
        
        Args:
            coord: (longitude, latitude) tuple
            radius: Search radius in meters (not used, kept for API compat)
            
        Returns:
            Snapped (longitude, latitude) tuple, or original if snap fails
        """
        cache_key = f"{coord[0]:.6f},{coord[1]:.6f}"
        if cache_key in self._snap_cache:
            return self._snap_cache[cache_key]
        
        if not self.api_key:
            return coord
        
        try:
            # Use a tiny routing request - ORS snaps the coordinate to nearest road
            # Create a route from the point to a point 0.0001° away (just ~11m)
            nearby = (coord[0] + 0.0001, coord[1])
            body = {
                "coordinates": [list(coord), list(nearby)],
                "preference": "fastest",
            }
            
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    ORS_DIRECTIONS_URL,
                    headers={
                        "Authorization": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json=body
                )
                
                if response.is_success:
                    data = response.json()
                    features = data.get("features", [])
                    if features:
                        coords = features[0].get("geometry", {}).get("coordinates", [])
                        if coords and len(coords) > 0:
                            # First coordinate is where ORS snapped our origin to
                            snapped = (coords[0][0], coords[0][1])
                            self._snap_cache[cache_key] = snapped
                            if abs(snapped[0] - coord[0]) > 0.0001 or abs(snapped[1] - coord[1]) > 0.0001:
                                logger.info(f"Snapped {coord} → {snapped}")
                            return snapped
        except Exception as e:
            logger.debug(f"Snap failed for {coord}: {e}")
        
        # Return original if snap fails
        self._snap_cache[cache_key] = coord
        return coord
    
    async def snap_coordinates(
        self, 
        origin: tuple[float, float], 
        destination: tuple[float, float],
        waypoint: Optional[tuple[float, float]] = None
    ) -> tuple[tuple[float, float], tuple[float, float], Optional[tuple[float, float]]]:
        """Snap origin, destination and optional waypoint to nearest roads in parallel."""
        tasks = [self.snap_to_road(origin), self.snap_to_road(destination)]
        if waypoint:
            tasks.append(self.snap_to_road(waypoint))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        snapped_origin = results[0] if not isinstance(results[0], Exception) else origin
        snapped_dest = results[1] if not isinstance(results[1], Exception) else destination
        snapped_wp = None
        if waypoint:
            snapped_wp = results[2] if not isinstance(results[2], Exception) else waypoint
        
        return snapped_origin, snapped_dest, snapped_wp
    
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
        has_waypoint = False
        if waypoint:
            coords.append(list(waypoint))
            has_waypoint = True
        coords.append(list(destination))

        body = {
            "coordinates": coords,
            "instructions": True,
            "preference": "fastest",
            "options": {
                "avoid_features": ["ferries", "tollways"]
            }
        }

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
                logger.warning(f"ORS failed, returning None (no straight-line fallback)")
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
    ) -> dict:
        """
        Compute blocked road (red) + best alternate route (green) for an incident.

        Strategy:
        - Detect road orientation from street name or default to E-W for NYC
        - Place origin/dest along the road's axis
        - Snap origin/dest to nearest road to avoid ORS 404 errors
        - Avoidance box forces alternate onto a parallel street (1-2 blocks away)
        """
        # Detect road orientation from street name
        street_lower = on_street.lower() if on_street else ""

        if any(kw in street_lower for kw in ["ave", "avenue", "broadway", "blvd", "boulevard"]):
            # N-S oriented road — offset in latitude, tiny lng offset
            lat_offset = 0.005   # ~550m along the road
            lng_offset = 0.0005  # ~42m across (keeps it on the same road)
            road_direction = "ns"
        else:
            # E-W oriented road (streets) or default — offset in longitude
            lat_offset = 0.0005  # ~55m across
            lng_offset = 0.005   # ~420m along the road
            road_direction = "ew"

        raw_origin = (round(incident_lng - lng_offset, 6), round(incident_lat - lat_offset, 6))
        raw_destination = (round(incident_lng + lng_offset, 6), round(incident_lat + lat_offset, 6))

        # Snap origin/destination to nearest roads to avoid ORS 404 errors
        origin, destination, _ = await self.snap_coordinates(raw_origin, raw_destination)
        
        logger.info(f"Route pair: origin={origin} dest={destination} road={road_direction} street='{on_street}'")

        congestion_polys = list(extra_avoid_polygons) if extra_avoid_polygons else []

        # Larger avoidance box: ±0.003° (~330m) — ensures alternate diverges before incident
        incident_corridor = self._bounding_box_polygon(
            incident_lng - 0.003, incident_lat - 0.003,
            incident_lng + 0.003, incident_lat + 0.003,
        )

        all_avoid_polys = [incident_corridor] + congestion_polys

        # Run both ORS calls in parallel
        blocked_task = self.get_diversion_route(origin, destination, avoid_coords=None)
        alt_task = self.get_diversion_route(
            origin, destination,
            avoid_polygons_list=all_avoid_polys,
        )

        blocked_raw, alt_raw = await asyncio.gather(blocked_task, alt_task, return_exceptions=True)

        if isinstance(blocked_raw, Exception):
            logger.error(f"Blocked route failed: {blocked_raw}")
            blocked_raw = None
        if isinstance(alt_raw, Exception):
            logger.error(f"Alternate route failed: {alt_raw}")
            alt_raw = None

        blocked_info = self.extract_route_info(blocked_raw) if blocked_raw else {}

        # If alternate too similar, try perpendicular waypoints in BOTH directions
        if alt_raw and blocked_raw:
            try:
                alt_coords = alt_raw.get("features", [{}])[0].get("geometry", {}).get("coordinates", [])
                blk_coords = blocked_raw.get("features", [{}])[0].get("geometry", {}).get("coordinates", [])
                if self._routes_too_similar(blk_coords, alt_coords):
                    logger.info("Alternate too similar — trying perpendicular waypoints")
                    wp_offset = 0.005  # ~550m perpendicular push (2-3 blocks)

                    if road_direction == "ew":
                        # E-W road: push north and south
                        raw_wp_a = (round(incident_lng, 6), round(incident_lat + wp_offset, 6))
                        raw_wp_b = (round(incident_lng, 6), round(incident_lat - wp_offset, 6))
                    else:
                        # N-S road: push east and west
                        raw_wp_a = (round(incident_lng + wp_offset, 6), round(incident_lat, 6))
                        raw_wp_b = (round(incident_lng - wp_offset, 6), round(incident_lat, 6))

                    # Snap waypoints to roads
                    wp_a = await self.snap_to_road(raw_wp_a)
                    wp_b = await self.snap_to_road(raw_wp_b)

                    task_a = self.get_diversion_route(
                        origin, destination, waypoint=wp_a,
                        avoid_polygons_list=all_avoid_polys,
                    )
                    task_b = self.get_diversion_route(
                        origin, destination, waypoint=wp_b,
                        avoid_polygons_list=all_avoid_polys,
                    )
                    raw_a, raw_b = await asyncio.gather(task_a, task_b, return_exceptions=True)

                    candidates = []
                    for label, raw in [("wp_a", raw_a), ("wp_b", raw_b)]:
                        if isinstance(raw, Exception) or raw is None:
                            continue
                        info = self.extract_route_info(raw)
                        # Validate geometry is not a straight line
                        if not self._is_valid_geometry(info.get("geometry")):
                            continue
                        dist = info.get("total_distance_km", 999)
                        candidates.append((dist, raw, label))

                    if candidates:
                        candidates.sort(key=lambda x: x[0])
                        alt_raw = candidates[0][1]
                        logger.info(f"Picked {candidates[0][2]} waypoint ({candidates[0][0]:.2f} km)")
            except Exception:
                pass

        alt_info = self.extract_route_info(alt_raw) if alt_raw else {}
        blocked_geom = blocked_info.get("geometry")
        alt_geom = alt_info.get("geometry")

        # Validate geometries — reject straight-line fallbacks
        empty_linestring = {"type": "LineString", "coordinates": []}
        
        if not self._is_valid_geometry(blocked_geom):
            logger.warning("Blocked route geometry invalid, using empty")
            blocked_geom = empty_linestring
        if not self._is_valid_geometry(alt_geom):
            logger.warning("Alternate route geometry invalid, using empty")
            alt_geom = empty_linestring

        return {
            "origin": list(origin),
            "destination": list(destination),
            "blocked": {
                "geometry": blocked_geom,
                "total_length_km": blocked_info.get("total_distance_km", 0),
                "street_names": blocked_info.get("street_names", []),
            },
            "alternate": {
                "geometry": alt_geom,
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
            return await self.compute_incident_route_pair(avg_lng, avg_lat, city, on_street="")

        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)
        center_lat = (min_lat + max_lat) / 2
        center_lng = (min_lng + max_lng) / 2
        lat_span = max_lat - min_lat
        lng_span = max_lng - min_lng

        offset = 0.008  # ~900m upstream/downstream of the congested zone

        if lat_span >= lng_span:
            # N-S oriented road — offset along latitude
            raw_origin = (round(center_lng, 6), round(min_lat - offset, 6))
            raw_destination = (round(center_lng, 6), round(max_lat + offset, 6))
        else:
            # E-W oriented road — offset along longitude
            raw_origin = (round(min_lng - offset, 6), round(center_lat, 6))
            raw_destination = (round(max_lng + offset, 6), round(center_lat, 6))

        # Snap origin/destination to nearest roads
        origin, destination, _ = await self.snap_coordinates(raw_origin, raw_destination)

        logger.info(
            f"Congestion route pair: origin={origin} dest={destination} "
            f"zone={len(congested_segments)} segments ({lat_span:.4f}°lat × {lng_span:.4f}°lng)"
        )

        # Build corridor polygon (with 0.004° padding = ~440m) - larger to ensure separation
        corridor_polygon = self._bounding_box_polygon(
            min_lng - 0.004, min_lat - 0.004,
            max_lng + 0.004, max_lat + 0.004
        )

        # Forced perpendicular waypoint to ensure ORS uses a different road
        if lat_span >= lng_span:  # N-S road → offset in longitude
            raw_waypoint = (round(center_lng + 0.007, 6), round(center_lat, 6))
        else:  # E-W road → offset in latitude
            raw_waypoint = (round(center_lng, 6), round(center_lat + 0.007, 6))
        
        waypoint = await self.snap_to_road(raw_waypoint)

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
        blocked_geom = blocked_info.get("geometry")
        alt_geom = alt_info.get("geometry")

        # Validate geometries — reject straight-line fallbacks
        empty_linestring = {"type": "LineString", "coordinates": []}
        
        if not self._is_valid_geometry(blocked_geom):
            logger.warning("Congestion blocked route geometry invalid, using empty")
            blocked_geom = empty_linestring
        if not self._is_valid_geometry(alt_geom):
            logger.warning("Congestion alternate route geometry invalid, using empty")
            alt_geom = empty_linestring

        return {
            "origin": list(origin),
            "destination": list(destination),
            "blocked": {
                "geometry": blocked_geom,
                "total_length_km": blocked_info.get("total_distance_km", 0),
                "street_names": blocked_info.get("street_names", []),
            },
            "alternate": {
                "geometry": alt_geom,
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
                geometry = info.get("geometry", {})
                # Only include diversions with valid (non-straight-line) geometry
                if self._is_valid_geometry(geometry):
                    results.append({
                        "priority": i + 1,
                        "name": pair["name"],
                        "segment_names": info.get("street_names", []),
                        "geometry": geometry,
                        "total_length_km": info.get("total_distance_km", 0),
                        "estimated_extra_minutes": info.get("total_duration_min", 0),
                    })
                else:
                    logger.warning(f"Diversion {pair['name']} has invalid geometry, skipping")
        
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

    def _coord_to_polygon(self, coord: tuple[float, float], radius: float = 0.002) -> list:
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
    
    def clear_cache(self):
        self._cache.clear()
