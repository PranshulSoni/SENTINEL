import asyncio
import pandas as pd
import numpy as np
import logging
import httpx
from typing import Callable, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# NYC DOT Traffic Speeds NBE — real-time speed per road segment
NYC_SPEED_API = "https://data.cityofnewyork.us/resource/i4gi-tjb9.json"

# Filter to Manhattan borough for manageable data size
NYC_BOROUGH_FILTER = "borough='Manhattan'"


class FeedSimulator:
    """Replays traffic speed data — fetches live from NYC Open Data API,
    falls back to cached CSV, then to synthetic demo data."""
    
    def __init__(self, data_dir: str = "data", app_token: str = ""):
        self.data_dir = Path(data_dir)
        self.app_token = app_token
        self.active_city: str = "nyc"
        self.frames: list[list[dict]] = []
        self.current_frame_idx: int = 0
        self.is_running: bool = False
        self.interval: float = 5.0
        self._task: Optional[asyncio.Task] = None
        self._callbacks: list[Callable] = []
        self._current_segments: list[dict] = []
    
    def on_frame(self, callback: Callable):
        """Register callback for new frame events."""
        self._callbacks.append(callback)
    
    def get_current_segments(self) -> list[dict]:
        """Return the latest frame of segment data."""
        return self._current_segments
    
    async def load_city(self, city: str):
        """Load feed data: API → cached CSV → demo data."""
        self.active_city = city
        csv_path = self.data_dir / f"{city}_link_speed.csv"

        # 1. Try live API fetch for NYC
        if city == "nyc" and self.app_token:
            api_frames = await self._fetch_nyc_live()
            if api_frames:
                self.frames = api_frames
                self.current_frame_idx = 0
                return

        # 2. Fall back to cached CSV
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            grouped = df.groupby("DATA_AS_OF")
            self.frames = []
            for ts, group in sorted(grouped):
                frame = []
                for _, row in group.iterrows():
                    frame.append({
                        "link_id": str(row["LINK_ID"]),
                        "link_name": str(row.get("LINK_NAME", "")),
                        "speed": float(row.get("SPEED", 0)),
                        "travel_time": float(row.get("TRAVEL_TIME", 0)),
                        "status": str(row.get("STATUS", "OK")),
                        "lat": float(row.get("LATITUDE", 0)),
                        "lng": float(row.get("LONGITUDE", 0)),
                    })
                self.frames.append(frame)
            logger.info(f"Loaded {len(self.frames)} frames for {city} from {csv_path}")
        else:
            # 3. Generate synthetic demo data
            logger.warning(f"No API data or CSV for {city}, generating demo data")
            self.frames = self._generate_demo_data(city)

        self.current_frame_idx = 0

    async def _fetch_nyc_live(self) -> list[list[dict]]:
        """Fetch real-time traffic speeds from NYC DOT Traffic Speeds NBE API.
        
        API columns: id, speed, travel_time, status, data_as_of, link_id,
        link_name, link_points, encoded_poly_line, borough, owner, transcom_id.
        NOTE: No latitude/longitude columns — geometry is in link_points
        (space-separated "lat,lng" pairs).
        """
        try:
            params = {
                "$$app_token": self.app_token,
                "$where": NYC_BOROUGH_FILTER,
                "$limit": 1000,
                "$order": "data_as_of DESC",
                "$select": "speed,travel_time,link_id,link_name,data_as_of,link_points,borough",
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(NYC_SPEED_API, params=params)
                resp.raise_for_status()
                records = resp.json()

            if not records:
                logger.warning("NYC API returned 0 records")
                return []

            # Group by data_as_of timestamp to form frames
            from collections import defaultdict
            ts_groups: dict[str, list[dict]] = defaultdict(list)
            for rec in records:
                ts = rec.get("data_as_of", "")
                if ts:
                    ts_groups[ts].append(rec)

            frames = []
            for ts in sorted(ts_groups.keys()):
                frame = []
                for rec in ts_groups[ts]:
                    speed = float(rec.get("speed", 0) or 0)
                    lat, lng = self._parse_link_points(rec.get("link_points", ""))
                    if lat == 0 and lng == 0:
                        continue  # skip records with no geometry

                    frame.append({
                        "link_id": str(rec.get("link_id", "")),
                        "link_name": str(rec.get("link_name", "Unknown")),
                        "speed": round(speed, 1),
                        "travel_time": round(float(rec.get("travel_time", 0) or 0), 2),
                        "status": "BLOCKED" if speed < 2 else "SLOW" if speed < 15 else "OK",
                        "lat": lat,
                        "lng": lng,
                    })
                if frame:
                    frames.append(frame)

            logger.info(f"Fetched {len(records)} records → {len(frames)} frames from NYC DOT API")

            # Cache to CSV for offline use
            try:
                self.data_dir.mkdir(parents=True, exist_ok=True)
                csv_path = self.data_dir / "nyc_link_speed.csv"
                df = pd.DataFrame(records)
                df.to_csv(csv_path, index=False)
                logger.info(f"Cached NYC data to {csv_path}")
            except Exception as e:
                logger.warning(f"Failed to cache CSV: {e}")

            return frames

        except Exception as e:
            logger.warning(f"NYC API fetch failed: {e}, will use fallback")
            return []

    @staticmethod
    def _parse_link_points(link_points: str) -> tuple[float, float]:
        """Extract midpoint lat/lng from link_points string.
        Format: 'lat1,lng1 lat2,lng2 lat3,lng3 ...'
        Returns the midpoint of the polyline for marker placement.
        """
        if not link_points or not link_points.strip():
            return 0.0, 0.0
        try:
            pairs = link_points.strip().split()
            if not pairs:
                return 0.0, 0.0
            # Use midpoint for best marker placement
            mid_idx = len(pairs) // 2
            lat_str, lng_str = pairs[mid_idx].split(",")
            return round(float(lat_str), 6), round(float(lng_str), 6)
        except (ValueError, IndexError):
            return 0.0, 0.0
    
    def _generate_demo_data(self, city: str) -> list[list[dict]]:
        """Generate synthetic demo frames for testing when no CSV exists."""
        if city == "nyc":
            segments = [
                {"link_id": "nyc_001", "link_name": "W 34th St (7th-8th Ave)", "lat": 40.7505, "lng": -73.9904},
                {"link_id": "nyc_002", "link_name": "W 34th St (8th-9th Ave)", "lat": 40.7522, "lng": -73.9932},
                {"link_id": "nyc_003", "link_name": "7th Ave (33rd-34th St)", "lat": 40.7498, "lng": -73.9895},
                {"link_id": "nyc_004", "link_name": "8th Ave (33rd-35th St)", "lat": 40.7515, "lng": -73.9926},
                {"link_id": "nyc_005", "link_name": "9th Ave (33rd-35th St)", "lat": 40.7532, "lng": -73.9955},
                {"link_id": "nyc_006", "link_name": "Broadway & 34th St", "lat": 40.7484, "lng": -73.9878},
                {"link_id": "nyc_007", "link_name": "10th Ave (41st-43rd St)", "lat": 40.7579, "lng": -73.9980},
                {"link_id": "nyc_008", "link_name": "W 42nd St (9th-10th Ave)", "lat": 40.7580, "lng": -73.9939},
            ]
        else:
            segments = [
                {"link_id": "chd_001", "link_name": "Madhya Marg (Sec 21-22)", "lat": 30.7333, "lng": 76.7794},
                {"link_id": "chd_002", "link_name": "Madhya Marg (Sec 22-23)", "lat": 30.7340, "lng": 76.7830},
                {"link_id": "chd_003", "link_name": "Sector 17 Chowk", "lat": 30.7412, "lng": 76.7788},
                {"link_id": "chd_004", "link_name": "Tribune Chowk", "lat": 30.7270, "lng": 76.7675},
                {"link_id": "chd_005", "link_name": "PGI Chowk", "lat": 30.7646, "lng": 76.7760},
                {"link_id": "chd_006", "link_name": "Sector 22 Chowk", "lat": 30.7320, "lng": 76.7780},
            ]
        
        frames = []
        base_time = datetime(2024, 3, 15, 8, 0, 0)
        np.random.seed(42)
        
        # Generate 60 frames (5 minutes of data at 5s intervals)
        for i in range(60):
            timestamp = base_time + timedelta(seconds=i * 5)
            frame = []
            for seg in segments:
                # Normal traffic for first 20 frames, then incident on first 2 segments
                if i < 20:
                    speed = np.random.uniform(20, 35)
                    status = "OK"
                elif seg["link_id"] in [segments[0]["link_id"], segments[1]["link_id"]]:
                    # Incident zone — speed drops progressively
                    drop_factor = max(0, 1 - (i - 20) * 0.08)
                    speed = max(0, np.random.uniform(20, 35) * drop_factor)
                    status = "BLOCKED" if speed < 2 else "SLOW" if speed < 15 else "OK"
                else:
                    # Adjacent segments slow down slightly
                    speed = np.random.uniform(12, 25)
                    status = "SLOW" if speed < 15 else "OK"
                
                frame.append({
                    "link_id": seg["link_id"],
                    "link_name": seg["link_name"],
                    "speed": round(speed, 1),
                    "travel_time": round(np.random.uniform(1, 8), 2),
                    "status": status,
                    "lat": seg["lat"],
                    "lng": seg["lng"],
                })
            frames.append(frame)
        
        logger.info(f"Generated {len(frames)} demo frames for {city}")
        return frames
    
    async def start(self, interval: float = 5.0):
        """Start the feed replay loop."""
        if self.is_running:
            return
        
        self.interval = interval
        if not self.frames:
            await self.load_city(self.active_city)
        
        self.is_running = True
        self._task = asyncio.create_task(self._replay_loop())
        logger.info(f"Feed simulator started for {self.active_city} at {interval}s intervals")
    
    async def stop(self):
        """Stop the feed replay loop."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Feed simulator stopped")
    
    async def switch_city(self, city: str):
        """Switch to a different city's feed data."""
        was_running = self.is_running
        await self.stop()
        await self.load_city(city)
        if was_running:
            await self.start(self.interval)
    
    async def _replay_loop(self):
        """Main replay loop — emits one frame per interval."""
        while self.is_running:
            if self.frames:
                frame = self.frames[self.current_frame_idx % len(self.frames)]
                self._current_segments = frame
                
                # Notify all callbacks
                for callback in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(frame)
                        else:
                            callback(frame)
                    except Exception as e:
                        logger.error(f"Feed callback error: {e}")
                
                self.current_frame_idx += 1
            
            await asyncio.sleep(self.interval)
