import asyncio
import httpx
import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
MAPBOX_DIRECTIONS_URL = "https://api.mapbox.com/directions/v5/mapbox/driving-traffic"


class RoutingService:
    """Computes diversion routes via OpenRouteService and Mapbox APIs."""
    
    def __init__(self, api_key: str = "", mapbox_token: str = ""):
        self.api_key = api_key  # ORS API key
        self.mapbox_token = mapbox_token  # Mapbox token
        self._cache: dict[str, dict] = {}
        self._snap_cache: dict[str, tuple[float, float]] = {}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAPBOX DIRECTIONS API - Traffic-aware optimal routing
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_mapbox_route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        waypoints: list[tuple[float, float]] | None = None,
    ) -> dict | None:
        """
        Get routes using Mapbox Directions API with traffic awareness.
        
        Uses driving-traffic profile for real-time traffic data.
        Returns up to 3 route alternatives.
        """
        if not self.mapbox_token:
            return None
        
        # Build coordinates string: origin;waypoint1;...;destination
        coords_list = [f"{origin[0]},{origin[1]}"]
        if waypoints:
            coords_list.extend([f"{wp[0]},{wp[1]}" for wp in waypoints])
        coords_list.append(f"{destination[0]},{destination[1]}")
        coords_str = ";".join(coords_list)
        
        url = f"{MAPBOX_DIRECTIONS_URL}/{coords_str}"
        params = {
            "access_token": self.mapbox_token,
            "geometries": "geojson",
            "overview": "full",
            "alternatives": "true",
            "annotations": "congestion,duration,distance,speed",
            "steps": "true",
        }
        
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.get(url, params=params)
                if response.is_success:
                    data = response.json()
                    if data.get("routes"):
                        logger.info(f"Mapbox returned {len(data['routes'])} routes")
                        return data
                else:
                    logger.warning(f"Mapbox API error: {response.status_code} - {response.text[:200]}")
        except Exception as e:
            logger.error(f"Mapbox request failed: {e}")
        
        return None
    
    def _haversine(self, coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
        """Calculate distance between two coordinates in meters."""
        R = 6371000  # Earth radius in meters
        lng1, lat1 = math.radians(coord1[0]), math.radians(coord1[1])
        lng2, lat2 = math.radians(coord2[0]), math.radians(coord2[1])
        
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def score_and_select_best_route(
        self,
        routes: list[dict],
        incident_location: tuple[float, float],
        severity: str = "moderate",
    ) -> dict:
        """
        Score routes using A* inspired heuristic and return the optimal one.
        
        Scoring factors (lower is better):
        - g(n): Actual cost = duration in traffic (minutes)
        - h(n): Heuristic = congestion penalty + incident proximity penalty
        - f(n) = g(n) + h(n)
        """
        SEVERITY_WEIGHTS = {
            "critical": 2.0,
            "major": 1.5,
            "moderate": 1.0,
            "minor": 0.5,
        }
        
        CONGESTION_PENALTIES = {
            "unknown": 0,
            "low": 0,
            "moderate": 1,
            "heavy": 3,
            "severe": 5,
        }
        
        scored_routes = []
        for route in routes:
            duration = route.get("duration", 9999)  # seconds
            distance = route.get("distance", 9999)  # meters
            
            # Calculate congestion penalty from annotations
            congestion_penalty = 0
            legs = route.get("legs", [])
            total_segments = 0
            for leg in legs:
                congestion = leg.get("annotation", {}).get("congestion", [])
                for c in congestion:
                    congestion_penalty += CONGESTION_PENALTIES.get(c, 0)
                    total_segments += 1
            
            # Normalize congestion penalty
            if total_segments > 0:
                congestion_penalty = (congestion_penalty / total_segments) * 10
            
            # Calculate minimum distance from incident
            coords = route.get("geometry", {}).get("coordinates", [])
            min_incident_dist = float('inf')
            for coord in coords:
                if len(coord) >= 2:
                    dist = self._haversine((coord[0], coord[1]), incident_location)
                    min_incident_dist = min(min_incident_dist, dist)
            
            # Proximity penalty: routes too close to incident get penalized
            # Within 200m = high penalty, 200-500m = medium, >500m = low
            proximity_penalty = 0
            if min_incident_dist < 200:
                proximity_penalty = 15 * SEVERITY_WEIGHTS.get(severity, 1.0)
            elif min_incident_dist < 500:
                proximity_penalty = 8 * SEVERITY_WEIGHTS.get(severity, 1.0)
            elif min_incident_dist < 800:
                proximity_penalty = 3 * SEVERITY_WEIGHTS.get(severity, 1.0)
            
            # A* score: f(n) = g(n) + h(n)
            g_cost = duration / 60  # Convert to minutes
            h_cost = congestion_penalty + proximity_penalty
            
            f_score = g_cost + h_cost
            
            logger.debug(f"Route score: f={f_score:.1f} (g={g_cost:.1f}min, congestion={congestion_penalty:.1f}, proximity={proximity_penalty:.1f}, dist_to_incident={min_incident_dist:.0f}m)")
            
            scored_routes.append((f_score, route, {
                "f_score": f_score,
                "duration_min": g_cost,
                "distance_km": distance / 1000,
                "congestion_penalty": congestion_penalty,
                "min_incident_dist_m": min_incident_dist,
            }))
        
        # Sort by f_score (lowest = best)
        scored_routes.sort(key=lambda x: x[0])
        
        if scored_routes:
            best = scored_routes[0]
            logger.info(f"Selected optimal route: f={best[2]['f_score']:.1f}, {best[2]['duration_min']:.1f}min, {best[2]['distance_km']:.2f}km")
            return best[1]
        
        return routes[0] if routes else {}
    
    def _get_congestion_summary(self, route: dict) -> str:
        """Get overall congestion level for a route."""
        legs = route.get("legs", [])
        congestion_counts = {"low": 0, "moderate": 0, "heavy": 0, "severe": 0}
        total = 0
        
        for leg in legs:
            for c in leg.get("annotation", {}).get("congestion", []):
                if c in congestion_counts:
                    congestion_counts[c] += 1
                total += 1
        
        if total == 0:
            return "unknown"
        
        # Determine dominant congestion level
        if congestion_counts["severe"] > total * 0.1:
            return "severe"
        elif congestion_counts["heavy"] > total * 0.2:
            return "heavy"
        elif congestion_counts["moderate"] > total * 0.3:
            return "moderate"
        return "low"
    
    def _extract_mapbox_street_names(self, route: dict) -> list[str]:
        """Extract street names from Mapbox route steps."""
        streets = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                name = step.get("name")
                if name and name not in streets:
                    streets.append(name)
        return streets[:5]  # Limit to first 5
    
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
    
    # Severity-based radius in degrees (approx meters at mid-latitudes)
    SEVERITY_RADIUS_DEG = {
        "critical": 0.0054,  # ~600m
        "major": 0.0040,     # ~450m
        "moderate": 0.0030,  # ~330m
        "minor": 0.0020,     # ~220m
    }

    def _circle_polygon(self, center_lng: float, center_lat: float, radius_deg: float, num_points: int = 16) -> dict:
        """Create a circular polygon for avoidance around an incident."""
        import math
        coords = []
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            lng = center_lng + radius_deg * math.cos(angle)
            # Adjust for latitude distortion
            lat = center_lat + radius_deg * (1.0 / math.cos(math.radians(center_lat))) * math.sin(angle)
            coords.append([lng, lat])
        coords.append(coords[0])  # Close the polygon
        return {"type": "Polygon", "coordinates": [coords]}

    async def compute_incident_route_pair(
        self,
        incident_lng: float,
        incident_lat: float,
        city: str = "nyc",
        on_street: str = "",
        extra_avoid_polygons: list | None = None,
        severity: str = "moderate",
    ) -> dict:
        """
        Compute blocked road (red) + best alternate route (green) for an incident.

        Strategy:
        1. Place origin/destination on OPPOSITE EDGES of the congestion circle
        2. RED route: shortest path THROUGH the incident (blocked road)
        3. GREEN route: path that AVOIDS the congestion radius (alternate)
        
        - Detect road orientation from street name or default to E-W for NYC
        - Use severity-based radius to size the congestion zone
        - Place origin/dest just outside the circle (~1.2x radius)
        - Snap origin/dest to nearest road to avoid API 404 errors
        """
        # Get severity-based radius
        radius = self.SEVERITY_RADIUS_DEG.get(severity, 0.0030)
        offset = radius * 1.2  # Place points just outside the circle
        
        # Detect road orientation from street name
        street_lower = on_street.lower() if on_street else ""

        if any(kw in street_lower for kw in ["ave", "avenue", "broadway", "blvd", "boulevard"]):
            # N-S oriented road — offset in latitude (along the road)
            lat_offset = offset
            lng_offset = offset * 0.1  # Tiny offset across to stay on road
            road_direction = "ns"
        else:
            # E-W oriented road (streets) or default — offset in longitude (along the road)
            lat_offset = offset * 0.1  # Tiny offset across to stay on road
            lng_offset = offset
            road_direction = "ew"

        # Place origin and destination on opposite edges of the congestion circle
        raw_origin = (round(incident_lng - lng_offset, 6), round(incident_lat - lat_offset, 6))
        raw_destination = (round(incident_lng + lng_offset, 6), round(incident_lat + lat_offset, 6))

        # Snap origin/destination to nearest roads to avoid ORS 404 errors
        origin, destination, _ = await self.snap_coordinates(raw_origin, raw_destination)
        
        logger.info(f"Route pair: origin={origin} dest={destination} road={road_direction} street='{on_street}'")

        congestion_polys = list(extra_avoid_polygons) if extra_avoid_polygons else []
        incident_location = (incident_lng, incident_lat)

        # ═══════════════════════════════════════════════════════════════════════════
        # MAPBOX ROUTING (preferred) - Traffic-aware with A* scoring
        # ═══════════════════════════════════════════════════════════════════════════
        
        if self.mapbox_token:
            logger.info("Attempting Mapbox routing with A* scoring...")
            
            # Get routes from Mapbox (includes alternatives)
            mapbox_result = await self.get_mapbox_route(origin, destination)
            
            if mapbox_result and mapbox_result.get("routes"):
                routes = mapbox_result["routes"]
                
                # Use A* scoring to select optimal route
                best_route = self.score_and_select_best_route(
                    routes, incident_location, severity
                )
                
                if best_route:
                    # Extract blocked route (first/direct route through incident area)
                    # and optimal alternate (A* selected)
                    blocked_route = routes[0]  # Direct route (potentially through incident)
                    
                    blocked_geom = blocked_route.get("geometry", {"type": "LineString", "coordinates": []})
                    alt_geom = best_route.get("geometry", {"type": "LineString", "coordinates": []})
                    
                    # Calculate route metrics
                    blocked_duration = blocked_route.get("duration", 0) / 60
                    blocked_distance = blocked_route.get("distance", 0) / 1000
                    alt_duration = best_route.get("duration", 0) / 60
                    alt_distance = best_route.get("distance", 0) / 1000
                    
                    # Extract street names from steps
                    blocked_streets = self._extract_mapbox_street_names(blocked_route)
                    alt_streets = self._extract_mapbox_street_names(best_route)
                    
                    # Get congestion summary
                    congestion_level = self._get_congestion_summary(best_route)
                    
                    logger.info(f"Mapbox optimal route: {alt_duration:.1f}min, {alt_distance:.2f}km, congestion={congestion_level}")
                    
                    return {
                        "origin": list(origin),
                        "destination": list(destination),
                        "blocked": {
                            "geometry": blocked_geom,
                            "total_length_km": blocked_distance,
                            "street_names": blocked_streets,
                            "estimated_minutes": blocked_duration,
                        },
                        "alternate": {
                            "geometry": alt_geom,
                            "total_length_km": alt_distance,
                            "estimated_extra_minutes": alt_duration,
                            "avg_speed_kmh": (alt_distance / alt_duration * 60) if alt_duration > 0 else 0,
                            "street_names": alt_streets,
                            "congestion_level": congestion_level,
                            "is_optimal": True,  # A* selected
                        },
                        "routing_source": "mapbox",
                    }
        
        # ═══════════════════════════════════════════════════════════════════════════
        # ORS FALLBACK - When Mapbox unavailable
        # ═══════════════════════════════════════════════════════════════════════════
        
        logger.info("Using ORS fallback routing...")

        # Create circular avoidance polygon around the incident using severity-based radius
        incident_circle = self._circle_polygon(incident_lng, incident_lat, radius)
        # Extract the coordinates for ORS (it expects coordinate rings, not GeoJSON)
        incident_corridor = incident_circle["coordinates"][0]

        all_avoid_polys = [incident_corridor] + congestion_polys

        # Run both ORS calls in parallel
        # RED route: shortest/direct path (through incident) - no avoidance
        blocked_task = self.get_diversion_route(origin, destination, avoid_coords=None)
        # GREEN route: avoids the congestion circle
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
                    # Use radius * 1.5 for perpendicular push (just beyond the circle)
                    wp_offset = radius * 1.5

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
                "is_optimal": True,  # ORS fallback - single route
            },
            "routing_source": "ors",
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

        offset = 0.012  # ~1.3km upstream/downstream of the congested zone

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

        # Build corridor polygon (with 0.006° padding = ~660m) - larger to ensure separation
        corridor_polygon = self._bounding_box_polygon(
            min_lng - 0.006, min_lat - 0.006,
            max_lng + 0.006, max_lat + 0.006
        )

        # Forced perpendicular waypoint to ensure ORS uses a different road
        if lat_span >= lng_span:  # N-S road → offset in longitude
            raw_waypoint = (round(center_lng + 0.010, 6), round(center_lat, 6))
        else:  # E-W road → offset in latitude
            raw_waypoint = (round(center_lng, 6), round(center_lat + 0.010, 6))
        
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

    async def compute_consolidated_routes(
        self,
        incidents: list[dict],
        city: str = "nyc",
        proximity_threshold: float = 0.005,  # ~550m - incidents within this are grouped
    ) -> list[dict]:
        """
        Consolidate nearby incidents into grouped route pairs.
        
        Returns list of consolidated route groups, each containing:
        - incident_ids: list of incident IDs in this group
        - blocked/alternate geometry covering all incidents in group
        """
        if not incidents:
            return []
        
        # Extract coordinates
        coords = []
        for inc in incidents:
            loc = inc.get("location", {})
            if isinstance(loc, dict):
                lng = loc.get("lng") or (loc.get("coordinates", [0, 0])[0])
                lat = loc.get("lat") or (loc.get("coordinates", [0, 0])[1])
            else:
                continue
            coords.append({
                "id": inc.get("id") or str(inc.get("_id")),
                "lng": lng,
                "lat": lat,
                "on_street": inc.get("on_street", ""),
            })
        
        if not coords:
            return []
        
        # Group nearby incidents using simple clustering
        groups = []
        used = set()
        
        for i, c1 in enumerate(coords):
            if c1["id"] in used:
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
                
                # Span of the group
                lng_span = max(lngs) - min(lngs)
                lat_span = max(lats) - min(lats)
                
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
    def _routes_too_similar(coords_a: list, coords_b: list, threshold: float = 0.5) -> bool:
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
