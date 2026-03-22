import httpx
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

NYPD_COLLISIONS_URL = "https://data.cityofnewyork.us/resource/h9gi-nx95.json"


class CollisionService:
    """Queries NYPD Motor Vehicle Collisions data from NYC Open Data."""
    
    def __init__(self, app_token: str = ""):
        self.app_token = app_token
        self._cache: dict[str, list[dict]] = {}
    
    def _get_chandigarh_collisions(self, lat: float, lng: float, radius_deg: float = 0.01) -> list[dict]:
        """Load synthetic Chandigarh collision data filtered by proximity."""
        import json
        from pathlib import Path
        data_file = Path(__file__).parent.parent / "data" / "chandigarh_collisions.json"
        if not data_file.exists():
            return []
        try:
            with open(data_file, encoding="utf-8") as f:
                all_collisions = json.load(f)
            nearby = []
            for c in all_collisions:
                try:
                    c_lat = float(c.get("latitude") or 0)
                    c_lng = float(c.get("longitude") or 0)
                    if c_lat and c_lng and abs(c_lat - lat) <= radius_deg and abs(c_lng - lng) <= radius_deg:
                        nearby.append(c)
                except (ValueError, TypeError):
                    continue
            logger.info(f"Found {len(nearby)} Chandigarh collisions near ({lat}, {lng})")
            return nearby[:100]
        except Exception as e:
            logger.warning(f"Failed to load Chandigarh collisions: {e}")
            return []

    async def get_nearby_collisions(
        self, lat: float, lng: float,
        radius_deg: float = 0.005,
        days_back: int = 30,
        limit: int = 500,
        city: str = "nyc"
    ) -> list[dict]:
        """Fetch nearby collisions — NYC API for nyc, synthetic file for chandigarh."""
        if city == "chandigarh":
            return self._get_chandigarh_collisions(lat, lng, radius_deg)
        cache_key = f"{lat:.4f},{lng:.4f},{radius_deg},{days_back}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        since_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00")
        
        params = {
            "$where": (
                f"latitude between {lat - radius_deg} and {lat + radius_deg} "
                f"and longitude between {lng - radius_deg} and {lng + radius_deg} "
                f"and crash_date > '{since_date}'"
            ),
            "$limit": limit,
            "$order": "crash_date DESC",
        }
        
        if self.app_token:
            params["$$app_token"] = self.app_token
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(NYPD_COLLISIONS_URL, params=params)
                response.raise_for_status()
                collisions = response.json()
                
            self._cache[cache_key] = collisions
            logger.info(f"Fetched {len(collisions)} collisions near ({lat}, {lng})")
            return collisions
            
        except Exception as e:
            logger.error(f"Failed to fetch collisions: {e}")
            return []
    
    async def get_high_injury_crashes(
        self, street_name: str, 
        min_injured: int = 2,
        limit: int = 10
    ) -> list[dict]:
        """Fetch high-injury crashes on a specific street."""
        params = {
            "$where": (
                f"number_of_persons_injured > {min_injured} "
                f"and on_street_name='{street_name.upper()}'"
            ),
            "$limit": limit,
            "$order": "crash_date DESC",
        }
        
        if self.app_token:
            params["$$app_token"] = self.app_token
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(NYPD_COLLISIONS_URL, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch high-injury crashes: {e}")
            return []
    
    def get_collision_context_for_llm(self, collisions: list[dict]) -> str:
        """Format collision data for LLM prompt injection."""
        if not collisions:
            return "No recent collision history available for this location."
        
        total = len(collisions)
        injuries = sum(int(c.get("number_of_persons_injured", 0)) for c in collisions)
        fatalities = sum(int(c.get("number_of_persons_killed", 0)) for c in collisions)
        
        # Top contributing factors
        factors: dict[str, int] = {}
        for c in collisions:
            factor = c.get("contributing_factor_vehicle_1", "Unknown")
            factors[factor] = factors.get(factor, 0) + 1
        top_factors = sorted(factors.items(), key=lambda x: -x[1])[:3]
        
        context = (
            f"COLLISION HISTORY (last 30 days, nearby):\n"
            f"Total crashes: {total}\n"
            f"Total persons injured: {injuries}\n"
            f"Total fatalities: {fatalities}\n"
            f"Top contributing factors: {', '.join(f'{f[0]} ({f[1]})' for f in top_factors)}\n"
        )
        
        # Add most recent crashes
        for c in collisions[:3]:
            context += (
                f"  - {c.get('crash_date', 'N/A')[:10]} {c.get('crash_time', '')}: "
                f"{c.get('on_street_name', '?')} & {c.get('cross_street_name', '?')} — "
                f"{c.get('number_of_persons_injured', 0)} injured\n"
            )
        
        return context
    
    def clear_cache(self):
        """Clear the collision cache (e.g., on city switch)."""
        self._cache.clear()
