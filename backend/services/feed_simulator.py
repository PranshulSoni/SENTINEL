import asyncio
import pandas as pd
import numpy as np
import logging
import httpx
from typing import Callable, Optional
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
        self._loop_end_callbacks: list[Callable] = []
        self._current_segments: list[dict] = []
    
    def on_frame(self, callback: Callable):
        """Register callback for new frame events."""
        self._callbacks.append(callback)
    
    def on_loop_end(self, callback: Callable):
        """Register callback fired when replay loop wraps around."""
        self._loop_end_callbacks.append(callback)
    
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

        # 1b. Try Chandigarh CSV
        if city == "chandigarh":
            csv_frames = await self._load_chandigarh_csv()
            if csv_frames:
                self.frames = csv_frames
                self.current_frame_idx = 0
                return

        # 2. Fall back to cached CSV (dedup by link_id, handle both upper/lowercase columns)
        if csv_path.exists():
            try:
                import random as _rng
                df = pd.read_csv(csv_path)
                cols = {c.lower(): c for c in df.columns}

                lid_col = cols.get("link_id", "link_id")
                ln_col = cols.get("link_name", "link_name")
                spd_col = cols.get("speed", "speed")
                tt_col = cols.get("travel_time", "travel_time")
                dao_col = cols.get("data_as_of", "data_as_of")
                lp_col = cols.get("link_points", None)
                lat_col = cols.get("latitude", None)
                lng_col = cols.get("longitude", None)

                latest_by_link: dict[str, dict] = {}
                for _, row in df.iterrows():
                    lid = str(row.get(lid_col, "") or "")
                    if not lid or lid == "nan":
                        continue
                    ts = str(row.get(dao_col, "") or "")
                    existing = latest_by_link.get(lid)
                    if not existing or ts > str(existing.get(dao_col, "")):
                        latest_by_link[lid] = row.to_dict()

                base_frame: list[dict] = []
                for rec in latest_by_link.values():
                    speed = float(rec.get(spd_col, 0) or 0)
                    lat, lng = 0.0, 0.0
                    if lp_col and rec.get(lp_col):
                        lat, lng = self._parse_link_points(str(rec.get(lp_col, "")))
                    if lat == 0 and lng == 0 and lat_col and lng_col:
                        lat = float(rec.get(lat_col, 0) or 0)
                        lng = float(rec.get(lng_col, 0) or 0)
                    if lat == 0 and lng == 0:
                        continue
                    base_frame.append({
                        "link_id": str(rec.get(lid_col, "")),
                        "link_name": str(rec.get(ln_col, "Unknown")),
                        "speed": round(speed, 1),
                        "travel_time": round(float(rec.get(tt_col, 0) or 0), 2),
                        "status": "BLOCKED" if speed < 2 else "SLOW" if speed < 15 else "OK",
                        "lat": lat,
                        "lng": lng,
                    })

                if base_frame:
                    self.frames = []
                    for _ in range(12):
                        frame = []
                        for seg in base_frame:
                            noise = _rng.uniform(-2.5, 2.5)
                            spd = max(0.0, round(seg["speed"] + noise, 1))
                            frame.append({
                                **seg,
                                "speed": spd,
                                "status": "BLOCKED" if spd < 2 else "SLOW" if spd < 15 else "OK",
                            })
                        self.frames.append(frame)
                    logger.info(f"CSV fallback: {len(base_frame)} unique segments → {len(self.frames)} frames for {city}")
                else:
                    logger.warning(f"CSV had no valid segments for {city}, generating demo data")
                    self.frames = self._generate_demo_data(city)
            except Exception as e:
                logger.warning(f"CSV fallback failed for {city}: {e}, generating demo data")
                self.frames = self._generate_demo_data(city)
        else:
            # 3. Generate synthetic demo data
            logger.warning(f"No API data or CSV for {city}, generating demo data")
            self.frames = self._generate_demo_data(city)

        self.current_frame_idx = 0

    async def _fetch_nyc_live(self) -> list[list[dict]]:
        """Fetch real-time traffic speeds from NYC DOT Traffic Speeds NBE API."""
        try:
            params = {
                "$$app_token": self.app_token,
                "$where": NYC_BOROUGH_FILTER,
                "$limit": 5000,
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

            # Take latest record per unique link_id → single rich snapshot
            latest_by_link: dict[str, dict] = {}
            for rec in records:
                link_id = rec.get("link_id", "")
                if not link_id:
                    continue
                existing = latest_by_link.get(link_id)
                if not existing or str(rec.get("data_as_of", "")) > str(existing.get("data_as_of", "")):
                    latest_by_link[link_id] = rec

            # Parse all unique segments into a base frame
            import random
            base_frame: list[dict] = []
            for rec in latest_by_link.values():
                speed = float(rec.get("speed", 0) or 0)
                lat, lng = self._parse_link_points(rec.get("link_points", ""))
                if lat == 0 and lng == 0:
                    continue
                base_frame.append({
                    "link_id": str(rec.get("link_id", "")),
                    "link_name": str(rec.get("link_name", "Unknown")),
                    "speed": round(speed, 1),
                    "travel_time": round(float(rec.get("travel_time", 0) or 0), 2),
                    "status": "BLOCKED" if speed < 2 else "SLOW" if speed < 15 else "OK",
                    "lat": lat,
                    "lng": lng,
                })

            if not base_frame:
                logger.warning("NYC API: no segments parsed from records")
                return []

            # Generate 12 replay frames with slight speed noise for realistic animation
            frames: list[list[dict]] = []
            for _ in range(12):
                frame: list[dict] = []
                for seg in base_frame:
                    noise = random.uniform(-2.5, 2.5)
                    spd = max(0.0, round(seg["speed"] + noise, 1))
                    frame.append({
                        **seg,
                        "speed": spd,
                        "status": "BLOCKED" if spd < 2 else "SLOW" if spd < 15 else "OK",
                    })
                frames.append(frame)

            logger.info(f"NYC API: {len(records)} records → {len(base_frame)} unique segments → {len(frames)} replay frames")

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

    async def _load_chandigarh_csv(self) -> list[list[dict]]:
        """Load Chandigarh feed data from CSV file (NYC-schema format)."""
        csv_path = self.data_dir / "chandigarh_link_speed.csv"
        if not csv_path.exists():
            logger.warning("chandigarh_link_speed.csv not found, will use demo data")
            return []
        try:
            import random
            df = pd.read_csv(csv_path)

            # Take latest per link_id
            latest_by_link: dict[str, dict] = {}
            for _, row in df.iterrows():
                link_id = str(row.get("link_id", "") or "")
                if not link_id or link_id == "nan":
                    continue
                ts = str(row.get("data_as_of", "") or "")
                existing = latest_by_link.get(link_id)
                if not existing or ts > str(existing.get("data_as_of", "")):
                    latest_by_link[link_id] = row.to_dict()

            base_frame: list[dict] = []
            for rec in latest_by_link.values():
                speed = float(rec.get("speed", 0) or 0)
                lat, lng = self._parse_link_points(str(rec.get("link_points", "") or ""))
                if lat == 0 and lng == 0:
                    continue
                base_frame.append({
                    "link_id": str(rec.get("link_id", "")),
                    "link_name": str(rec.get("link_name", "Unknown")),
                    "speed": round(speed, 1),
                    "travel_time": round(float(rec.get("travel_time", 0) or 0), 2),
                    "status": "BLOCKED" if speed < 2 else "SLOW" if speed < 15 else "OK",
                    "lat": lat,
                    "lng": lng,
                })

            if not base_frame:
                return []

            # Generate 12 replay frames with slight speed variation
            frames: list[list[dict]] = []
            for _ in range(12):
                frame: list[dict] = []
                for seg in base_frame:
                    noise = random.uniform(-2.0, 2.0)
                    spd = max(0.0, round(seg["speed"] + noise, 1))
                    frame.append({
                        **seg,
                        "speed": spd,
                        "status": "BLOCKED" if spd < 2 else "SLOW" if spd < 15 else "OK",
                    })
                frames.append(frame)

            logger.info(f"Chandigarh CSV: {len(base_frame)} unique segments → {len(frames)} replay frames")
            return frames

        except Exception as e:
            logger.warning(f"Failed to load Chandigarh CSV: {e}")
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
            # lat references: 14th=40.7376, 18th=40.7410, 23rd=40.7428, 28th=40.7460,
            #   34th=40.7484, 40th=40.7540, 42nd=40.7579, 45th=40.7596, 50th=40.7617,
            #   57th=40.7638, 59th=40.7647, 72nd=40.7762
            # lng references: 1st=-73.9771, 2nd=-73.9813, 3rd=-73.9818, Lex=-73.9847,
            #   Park=-73.9803, Mad=-73.9881, 5th=-73.9858, 6th=-73.9961, 7th=-73.9995,
            #   Bwy=-73.9878, 8th=-74.0009, 9th=-74.0023, 10th=-74.0020,
            #   WSH=-74.0126, FDR=-73.9739
            segments = [
                # --- 5th Ave (14th→59th) ---
                {"link_id": "NYC_5AV_14", "link_name": "5th Ave & 14th St",  "lat": 40.7376, "lng": -73.9858},
                {"link_id": "NYC_5AV_18", "link_name": "5th Ave & 18th St",  "lat": 40.7410, "lng": -73.9858},
                {"link_id": "NYC_5AV_23", "link_name": "5th Ave & 23rd St",  "lat": 40.7428, "lng": -73.9858},
                {"link_id": "NYC_5AV_28", "link_name": "5th Ave & 28th St",  "lat": 40.7460, "lng": -73.9858},
                {"link_id": "NYC_5AV_34", "link_name": "5th Ave & 34th St",  "lat": 40.7484, "lng": -73.9858},
                {"link_id": "NYC_5AV_40", "link_name": "5th Ave & 40th St",  "lat": 40.7540, "lng": -73.9858},
                {"link_id": "NYC_5AV_45", "link_name": "5th Ave & 45th St",  "lat": 40.7596, "lng": -73.9858},
                {"link_id": "NYC_5AV_50", "link_name": "5th Ave & 50th St",  "lat": 40.7617, "lng": -73.9858},
                {"link_id": "NYC_5AV_59", "link_name": "5th Ave & 59th St",  "lat": 40.7647, "lng": -73.9858},
                # --- 6th Ave (14th→59th) ---
                {"link_id": "NYC_6AV_14", "link_name": "6th Ave & 14th St",  "lat": 40.7376, "lng": -73.9961},
                {"link_id": "NYC_6AV_18", "link_name": "6th Ave & 18th St",  "lat": 40.7410, "lng": -73.9961},
                {"link_id": "NYC_6AV_23", "link_name": "6th Ave & 23rd St",  "lat": 40.7428, "lng": -73.9961},
                {"link_id": "NYC_6AV_28", "link_name": "6th Ave & 28th St",  "lat": 40.7460, "lng": -73.9961},
                {"link_id": "NYC_6AV_34", "link_name": "6th Ave & 34th St",  "lat": 40.7484, "lng": -73.9961},
                {"link_id": "NYC_6AV_40", "link_name": "6th Ave & 40th St",  "lat": 40.7540, "lng": -73.9961},
                {"link_id": "NYC_6AV_45", "link_name": "6th Ave & 45th St",  "lat": 40.7596, "lng": -73.9961},
                {"link_id": "NYC_6AV_50", "link_name": "6th Ave & 50th St",  "lat": 40.7617, "lng": -73.9961},
                {"link_id": "NYC_6AV_59", "link_name": "6th Ave & 59th St",  "lat": 40.7647, "lng": -73.9961},
                # --- 7th Ave (14th→59th) ---
                {"link_id": "NYC_7AV_14", "link_name": "7th Ave & 14th St",  "lat": 40.7376, "lng": -73.9995},
                {"link_id": "NYC_7AV_18", "link_name": "7th Ave & 18th St",  "lat": 40.7410, "lng": -73.9995},
                {"link_id": "NYC_7AV_23", "link_name": "7th Ave & 23rd St",  "lat": 40.7428, "lng": -73.9995},
                {"link_id": "NYC_7AV_28", "link_name": "7th Ave & 28th St",  "lat": 40.7460, "lng": -73.9995},
                {"link_id": "NYC_7AV_34", "link_name": "7th Ave & 34th St",  "lat": 40.7484, "lng": -73.9995},
                {"link_id": "NYC_7AV_40", "link_name": "7th Ave & 40th St",  "lat": 40.7540, "lng": -73.9995},
                {"link_id": "NYC_7AV_45", "link_name": "7th Ave & 45th St",  "lat": 40.7596, "lng": -73.9995},
                {"link_id": "NYC_7AV_50", "link_name": "7th Ave & 50th St",  "lat": 40.7617, "lng": -73.9995},
                {"link_id": "NYC_7AV_59", "link_name": "7th Ave & 59th St",  "lat": 40.7647, "lng": -73.9995},
                # --- 8th Ave / Hudson (14th→59th) ---
                {"link_id": "NYC_8AV_14", "link_name": "8th Ave & 14th St",  "lat": 40.7376, "lng": -74.0009},
                {"link_id": "NYC_8AV_18", "link_name": "8th Ave & 18th St",  "lat": 40.7410, "lng": -74.0009},
                {"link_id": "NYC_8AV_23", "link_name": "8th Ave & 23rd St",  "lat": 40.7428, "lng": -74.0009},
                {"link_id": "NYC_8AV_28", "link_name": "8th Ave & 28th St",  "lat": 40.7460, "lng": -74.0009},
                {"link_id": "NYC_8AV_34", "link_name": "8th Ave & 34th St",  "lat": 40.7484, "lng": -74.0009},
                {"link_id": "NYC_8AV_40", "link_name": "8th Ave & 40th St",  "lat": 40.7540, "lng": -74.0009},
                {"link_id": "NYC_8AV_45", "link_name": "8th Ave & 45th St",  "lat": 40.7596, "lng": -74.0009},
                {"link_id": "NYC_8AV_50", "link_name": "8th Ave & 50th St",  "lat": 40.7617, "lng": -74.0009},
                {"link_id": "NYC_8AV_59", "link_name": "8th Ave & 59th St",  "lat": 40.7647, "lng": -74.0009},
                # --- Broadway (14th→59th) ---
                {"link_id": "NYC_BWY_14", "link_name": "Broadway & 14th St", "lat": 40.7376, "lng": -73.9878},
                {"link_id": "NYC_BWY_18", "link_name": "Broadway & 18th St", "lat": 40.7410, "lng": -73.9878},
                {"link_id": "NYC_BWY_23", "link_name": "Broadway & 23rd St", "lat": 40.7428, "lng": -73.9878},
                {"link_id": "NYC_BWY_28", "link_name": "Broadway & 28th St", "lat": 40.7460, "lng": -73.9878},
                {"link_id": "NYC_BWY_34", "link_name": "Broadway & 34th St", "lat": 40.7484, "lng": -73.9878},
                {"link_id": "NYC_BWY_40", "link_name": "Broadway & 40th St", "lat": 40.7540, "lng": -73.9878},
                {"link_id": "NYC_BWY_45", "link_name": "Broadway & 45th St", "lat": 40.7596, "lng": -73.9878},
                {"link_id": "NYC_BWY_50", "link_name": "Broadway & 50th St", "lat": 40.7617, "lng": -73.9878},
                {"link_id": "NYC_BWY_59", "link_name": "Broadway & 59th St", "lat": 40.7647, "lng": -73.9878},
                # --- Madison Ave (14th→59th) ---
                {"link_id": "NYC_MAD_14", "link_name": "Madison Ave & 14th St", "lat": 40.7376, "lng": -73.9881},
                {"link_id": "NYC_MAD_18", "link_name": "Madison Ave & 18th St", "lat": 40.7410, "lng": -73.9881},
                {"link_id": "NYC_MAD_23", "link_name": "Madison Ave & 23rd St", "lat": 40.7428, "lng": -73.9881},
                {"link_id": "NYC_MAD_28", "link_name": "Madison Ave & 28th St", "lat": 40.7460, "lng": -73.9881},
                {"link_id": "NYC_MAD_34", "link_name": "Madison Ave & 34th St", "lat": 40.7484, "lng": -73.9881},
                {"link_id": "NYC_MAD_40", "link_name": "Madison Ave & 40th St", "lat": 40.7540, "lng": -73.9881},
                {"link_id": "NYC_MAD_45", "link_name": "Madison Ave & 45th St", "lat": 40.7596, "lng": -73.9881},
                {"link_id": "NYC_MAD_50", "link_name": "Madison Ave & 50th St", "lat": 40.7617, "lng": -73.9881},
                {"link_id": "NYC_MAD_59", "link_name": "Madison Ave & 59th St", "lat": 40.7647, "lng": -73.9881},
                # --- Lexington Ave (14th→59th) ---
                {"link_id": "NYC_LEX_14", "link_name": "Lexington Ave & 14th St", "lat": 40.7376, "lng": -73.9847},
                {"link_id": "NYC_LEX_18", "link_name": "Lexington Ave & 18th St", "lat": 40.7410, "lng": -73.9847},
                {"link_id": "NYC_LEX_23", "link_name": "Lexington Ave & 23rd St", "lat": 40.7428, "lng": -73.9847},
                {"link_id": "NYC_LEX_28", "link_name": "Lexington Ave & 28th St", "lat": 40.7460, "lng": -73.9847},
                {"link_id": "NYC_LEX_34", "link_name": "Lexington Ave & 34th St", "lat": 40.7484, "lng": -73.9847},
                {"link_id": "NYC_LEX_40", "link_name": "Lexington Ave & 40th St", "lat": 40.7540, "lng": -73.9847},
                {"link_id": "NYC_LEX_45", "link_name": "Lexington Ave & 45th St", "lat": 40.7596, "lng": -73.9847},
                {"link_id": "NYC_LEX_50", "link_name": "Lexington Ave & 50th St", "lat": 40.7617, "lng": -73.9847},
                {"link_id": "NYC_LEX_59", "link_name": "Lexington Ave & 59th St", "lat": 40.7647, "lng": -73.9847},
                # --- Park Ave (14th→59th) ---
                {"link_id": "NYC_PAR_14", "link_name": "Park Ave & 14th St",  "lat": 40.7376, "lng": -73.9803},
                {"link_id": "NYC_PAR_18", "link_name": "Park Ave & 18th St",  "lat": 40.7410, "lng": -73.9803},
                {"link_id": "NYC_PAR_23", "link_name": "Park Ave & 23rd St",  "lat": 40.7428, "lng": -73.9803},
                {"link_id": "NYC_PAR_28", "link_name": "Park Ave & 28th St",  "lat": 40.7460, "lng": -73.9803},
                {"link_id": "NYC_PAR_34", "link_name": "Park Ave & 34th St",  "lat": 40.7484, "lng": -73.9803},
                {"link_id": "NYC_PAR_40", "link_name": "Park Ave & 40th St",  "lat": 40.7540, "lng": -73.9803},
                {"link_id": "NYC_PAR_45", "link_name": "Park Ave & 45th St",  "lat": 40.7596, "lng": -73.9803},
                {"link_id": "NYC_PAR_50", "link_name": "Park Ave & 50th St",  "lat": 40.7617, "lng": -73.9803},
                {"link_id": "NYC_PAR_59", "link_name": "Park Ave & 59th St",  "lat": 40.7647, "lng": -73.9803},
                # --- 3rd Ave (14th→59th) ---
                {"link_id": "NYC_3AV_14", "link_name": "3rd Ave & 14th St",   "lat": 40.7376, "lng": -73.9818},
                {"link_id": "NYC_3AV_23", "link_name": "3rd Ave & 23rd St",   "lat": 40.7428, "lng": -73.9818},
                {"link_id": "NYC_3AV_34", "link_name": "3rd Ave & 34th St",   "lat": 40.7484, "lng": -73.9818},
                {"link_id": "NYC_3AV_42", "link_name": "3rd Ave & 42nd St",   "lat": 40.7579, "lng": -73.9818},
                {"link_id": "NYC_3AV_50", "link_name": "3rd Ave & 50th St",   "lat": 40.7617, "lng": -73.9818},
                {"link_id": "NYC_3AV_59", "link_name": "3rd Ave & 59th St",   "lat": 40.7647, "lng": -73.9818},
                # --- 2nd Ave (14th→59th) ---
                {"link_id": "NYC_2AV_14", "link_name": "2nd Ave & 14th St",   "lat": 40.7376, "lng": -73.9813},
                {"link_id": "NYC_2AV_23", "link_name": "2nd Ave & 23rd St",   "lat": 40.7428, "lng": -73.9813},
                {"link_id": "NYC_2AV_34", "link_name": "2nd Ave & 34th St",   "lat": 40.7484, "lng": -73.9813},
                {"link_id": "NYC_2AV_42", "link_name": "2nd Ave & 42nd St",   "lat": 40.7579, "lng": -73.9813},
                {"link_id": "NYC_2AV_50", "link_name": "2nd Ave & 50th St",   "lat": 40.7617, "lng": -73.9813},
                {"link_id": "NYC_2AV_59", "link_name": "2nd Ave & 59th St",   "lat": 40.7647, "lng": -73.9813},
                # --- 1st Ave (14th→59th) ---
                {"link_id": "NYC_1AV_14", "link_name": "1st Ave & 14th St",   "lat": 40.7376, "lng": -73.9771},
                {"link_id": "NYC_1AV_23", "link_name": "1st Ave & 23rd St",   "lat": 40.7428, "lng": -73.9771},
                {"link_id": "NYC_1AV_34", "link_name": "1st Ave & 34th St",   "lat": 40.7484, "lng": -73.9771},
                {"link_id": "NYC_1AV_42", "link_name": "1st Ave & 42nd St",   "lat": 40.7579, "lng": -73.9771},
                {"link_id": "NYC_1AV_50", "link_name": "1st Ave & 50th St",   "lat": 40.7617, "lng": -73.9771},
                {"link_id": "NYC_1AV_59", "link_name": "1st Ave & 59th St",   "lat": 40.7647, "lng": -73.9771},
                # --- West Side Highway (5 segments) ---
                {"link_id": "NYC_WSH_14", "link_name": "West Side Hwy & 14th St", "lat": 40.7376, "lng": -74.0126},
                {"link_id": "NYC_WSH_23", "link_name": "West Side Hwy & 23rd St", "lat": 40.7428, "lng": -74.0126},
                {"link_id": "NYC_WSH_34", "link_name": "West Side Hwy & 34th St", "lat": 40.7484, "lng": -74.0126},
                {"link_id": "NYC_WSH_42", "link_name": "West Side Hwy & 42nd St", "lat": 40.7579, "lng": -74.0126},
                {"link_id": "NYC_WSH_57", "link_name": "West Side Hwy & 57th St", "lat": 40.7638, "lng": -74.0126},
                # --- FDR Drive (5 segments) ---
                {"link_id": "NYC_FDR_14", "link_name": "FDR Dr & 14th St",    "lat": 40.7376, "lng": -73.9739},
                {"link_id": "NYC_FDR_23", "link_name": "FDR Dr & 23rd St",    "lat": 40.7428, "lng": -73.9739},
                {"link_id": "NYC_FDR_34", "link_name": "FDR Dr & 34th St",    "lat": 40.7484, "lng": -73.9739},
                {"link_id": "NYC_FDR_42", "link_name": "FDR Dr & 42nd St",    "lat": 40.7579, "lng": -73.9739},
                {"link_id": "NYC_FDR_57", "link_name": "FDR Dr & 57th St",    "lat": 40.7638, "lng": -73.9739},
                # --- 14th St cross (E-W, 6 segments) ---
                {"link_id": "NYC_14_1A", "link_name": "14th St & 1st Ave",    "lat": 40.7376, "lng": -73.9771},
                {"link_id": "NYC_14_3A", "link_name": "14th St & 3rd Ave",    "lat": 40.7376, "lng": -73.9818},
                {"link_id": "NYC_14_5A", "link_name": "14th St & 5th Ave",    "lat": 40.7376, "lng": -73.9858},
                {"link_id": "NYC_14_7A", "link_name": "14th St & 7th Ave",    "lat": 40.7376, "lng": -73.9995},
                {"link_id": "NYC_14_8A", "link_name": "14th St & 8th Ave",    "lat": 40.7376, "lng": -74.0009},
                {"link_id": "NYC_14_9A", "link_name": "14th St & 9th Ave",    "lat": 40.7376, "lng": -74.0023},
                # --- 23rd St cross (E-W, 6 segments) ---
                {"link_id": "NYC_23_1A", "link_name": "23rd St & 1st Ave",    "lat": 40.7428, "lng": -73.9771},
                {"link_id": "NYC_23_3A", "link_name": "23rd St & 3rd Ave",    "lat": 40.7428, "lng": -73.9818},
                {"link_id": "NYC_23_5A", "link_name": "23rd St & 5th Ave",    "lat": 40.7428, "lng": -73.9858},
                {"link_id": "NYC_23_7A", "link_name": "23rd St & 7th Ave",    "lat": 40.7428, "lng": -73.9995},
                {"link_id": "NYC_23_8A", "link_name": "23rd St & 8th Ave",    "lat": 40.7428, "lng": -74.0009},
                {"link_id": "NYC_23_9A", "link_name": "23rd St & 9th Ave",    "lat": 40.7428, "lng": -74.0023},
                # --- 34th St cross (E-W, 6 segments) ---
                {"link_id": "NYC_34_1A", "link_name": "34th St & 1st Ave",    "lat": 40.7484, "lng": -73.9771},
                {"link_id": "NYC_34_3A", "link_name": "34th St & 3rd Ave",    "lat": 40.7484, "lng": -73.9818},
                {"link_id": "NYC_34_5A", "link_name": "34th St & 5th Ave",    "lat": 40.7484, "lng": -73.9858},
                {"link_id": "NYC_34_7A", "link_name": "34th St & 7th Ave",    "lat": 40.7484, "lng": -73.9995},
                {"link_id": "NYC_34_8A", "link_name": "34th St & 8th Ave",    "lat": 40.7484, "lng": -74.0009},
                {"link_id": "NYC_34_9A", "link_name": "34th St & 9th Ave",    "lat": 40.7484, "lng": -74.0023},
                # --- 42nd St cross (E-W, 6 segments) ---
                {"link_id": "NYC_42_1A", "link_name": "42nd St & 1st Ave",    "lat": 40.7579, "lng": -73.9771},
                {"link_id": "NYC_42_3A", "link_name": "42nd St & 3rd Ave",    "lat": 40.7579, "lng": -73.9818},
                {"link_id": "NYC_42_5A", "link_name": "42nd St & 5th Ave",    "lat": 40.7579, "lng": -73.9858},
                {"link_id": "NYC_42_7A", "link_name": "42nd St & 7th Ave",    "lat": 40.7579, "lng": -73.9995},
                {"link_id": "NYC_42_8A", "link_name": "42nd St & 8th Ave",    "lat": 40.7579, "lng": -74.0009},
                {"link_id": "NYC_42_9A", "link_name": "42nd St & 9th Ave",    "lat": 40.7579, "lng": -74.0023},
                # --- 57th St cross (E-W, 6 segments) ---
                {"link_id": "NYC_57_1A", "link_name": "57th St & 1st Ave",    "lat": 40.7638, "lng": -73.9771},
                {"link_id": "NYC_57_3A", "link_name": "57th St & 3rd Ave",    "lat": 40.7638, "lng": -73.9818},
                {"link_id": "NYC_57_5A", "link_name": "57th St & 5th Ave",    "lat": 40.7638, "lng": -73.9858},
                {"link_id": "NYC_57_7A", "link_name": "57th St & 7th Ave",    "lat": 40.7638, "lng": -73.9995},
                {"link_id": "NYC_57_8A", "link_name": "57th St & 8th Ave",    "lat": 40.7638, "lng": -74.0009},
                {"link_id": "NYC_57_9A", "link_name": "57th St & 9th Ave",    "lat": 40.7638, "lng": -74.0023},
                # --- 72nd St cross (E-W, 6 segments) ---
                {"link_id": "NYC_72_1A", "link_name": "72nd St & 1st Ave",    "lat": 40.7762, "lng": -73.9771},
                {"link_id": "NYC_72_3A", "link_name": "72nd St & 3rd Ave",    "lat": 40.7762, "lng": -73.9818},
                {"link_id": "NYC_72_5A", "link_name": "72nd St & 5th Ave",    "lat": 40.7762, "lng": -73.9858},
                {"link_id": "NYC_72_7A", "link_name": "72nd St & 7th Ave",    "lat": 40.7762, "lng": -73.9995},
                {"link_id": "NYC_72_8A", "link_name": "72nd St & 8th Ave",    "lat": 40.7762, "lng": -74.0009},
                {"link_id": "NYC_72_9A", "link_name": "72nd St & 9th Ave",    "lat": 40.7762, "lng": -74.0023},
            ]
        else:
            segments = [
                # Madhya Marg — main arterial (N-S spine)
                {"link_id": "chd_001", "link_name": "Madhya Marg (Sec 1-4)", "lat": 30.7620, "lng": 76.7775},
                {"link_id": "chd_002", "link_name": "Madhya Marg (Sec 4-8)", "lat": 30.7560, "lng": 76.7780},
                {"link_id": "chd_003", "link_name": "Madhya Marg (Sec 8-11)", "lat": 30.7490, "lng": 76.7785},
                {"link_id": "chd_004", "link_name": "Madhya Marg (Sec 11-17)", "lat": 30.7420, "lng": 76.7790},
                {"link_id": "chd_005", "link_name": "Madhya Marg (Sec 17-22)", "lat": 30.7370, "lng": 76.7792},
                {"link_id": "chd_006", "link_name": "Madhya Marg (Sec 22-26)", "lat": 30.7333, "lng": 76.7794},
                {"link_id": "chd_007", "link_name": "Madhya Marg (Sec 26-30)", "lat": 30.7280, "lng": 76.7796},
                {"link_id": "chd_008", "link_name": "Madhya Marg (Sec 30-35)", "lat": 30.7220, "lng": 76.7798},
                {"link_id": "chd_009", "link_name": "Madhya Marg (Sec 35-43)", "lat": 30.7140, "lng": 76.7800},
                # Jan Marg (E-W)
                {"link_id": "chd_010", "link_name": "Jan Marg (Sec 3-9)", "lat": 30.7554, "lng": 76.7875},
                {"link_id": "chd_011", "link_name": "Jan Marg (Sec 9-15)", "lat": 30.7554, "lng": 76.7950},
                {"link_id": "chd_012", "link_name": "Jan Marg (Sec 15-24)", "lat": 30.7554, "lng": 76.8040},
                {"link_id": "chd_013", "link_name": "Jan Marg (IT Park)", "lat": 30.7270, "lng": 76.8010},
                # Dakshin Marg (S-N)
                {"link_id": "chd_014", "link_name": "Dakshin Marg (Sec 18-20)", "lat": 30.7208, "lng": 76.7876},
                {"link_id": "chd_015", "link_name": "Dakshin Marg (Sec 20-23)", "lat": 30.7260, "lng": 76.7874},
                {"link_id": "chd_016", "link_name": "Dakshin Marg (Sec 23-27)", "lat": 30.7310, "lng": 76.7872},
                {"link_id": "chd_017", "link_name": "Dakshin Marg (Sec 27-33)", "lat": 30.7160, "lng": 76.7870},
                # Vidhya Path
                {"link_id": "chd_018", "link_name": "Vidhya Path (Sec 14-15)", "lat": 30.7516, "lng": 76.7738},
                {"link_id": "chd_019", "link_name": "Vidhya Path (Sec 15-16)", "lat": 30.7516, "lng": 76.7820},
                {"link_id": "chd_020", "link_name": "Vidhya Path (Sec 16-17)", "lat": 30.7516, "lng": 76.7900},
                # Himalaya Marg
                {"link_id": "chd_021", "link_name": "Himalaya Marg (Sec 35-37)", "lat": 30.7258, "lng": 76.7562},
                {"link_id": "chd_022", "link_name": "Himalaya Marg (Sec 37-38)", "lat": 30.7220, "lng": 76.7600},
                {"link_id": "chd_023", "link_name": "Himalaya Marg (Sec 40-43)", "lat": 30.7180, "lng": 76.7640},
                # Purv Marg / Industrial Area
                {"link_id": "chd_024", "link_name": "Purv Marg (Ind Area Phase 1)", "lat": 30.7095, "lng": 76.7905},
                {"link_id": "chd_025", "link_name": "Purv Marg (Ind Area Phase 2)", "lat": 30.7060, "lng": 76.7950},
                # Major chowks
                {"link_id": "chd_026", "link_name": "Sector 17 Chowk", "lat": 30.7412, "lng": 76.7788},
                {"link_id": "chd_027", "link_name": "Tribune Chowk", "lat": 30.7270, "lng": 76.7675},
                {"link_id": "chd_028", "link_name": "PGI Chowk", "lat": 30.7646, "lng": 76.7760},
                {"link_id": "chd_029", "link_name": "Sector 22 Chowk", "lat": 30.7320, "lng": 76.7780},
                {"link_id": "chd_030", "link_name": "IT Park Chowk", "lat": 30.7270, "lng": 76.8010},
                {"link_id": "chd_031", "link_name": "Aroma Light Point", "lat": 30.7315, "lng": 76.7845},
                {"link_id": "chd_032", "link_name": "Piccadily Chowk", "lat": 30.7246, "lng": 76.7621},
                {"link_id": "chd_033", "link_name": "Transport Chowk", "lat": 30.7212, "lng": 76.8040},
                {"link_id": "chd_034", "link_name": "Housing Board Chowk", "lat": 30.7135, "lng": 76.8202},
                {"link_id": "chd_035", "link_name": "Sector 43 ISBT Approach", "lat": 30.7226, "lng": 76.7511},
                {"link_id": "chd_036", "link_name": "Elante Mall Access Road", "lat": 30.7061, "lng": 76.8016},
                {"link_id": "chd_037", "link_name": "Punjab University Gate", "lat": 30.7602, "lng": 76.7681},
                {"link_id": "chd_038", "link_name": "Rose Garden Bypass", "lat": 30.7441, "lng": 76.7813},
                {"link_id": "chd_039", "link_name": "Rock Garden Road", "lat": 30.7523, "lng": 76.8078},
                {"link_id": "chd_040", "link_name": "Sukhna Lake Road", "lat": 30.7311, "lng": 76.7915},
                # Sector connector roads
                {"link_id": "chd_041", "link_name": "Sector 7-8 Road", "lat": 30.7480, "lng": 76.7850},
                {"link_id": "chd_042", "link_name": "Sector 9-10 Road", "lat": 30.7450, "lng": 76.7860},
                {"link_id": "chd_043", "link_name": "Sector 10-11 Road", "lat": 30.7430, "lng": 76.7870},
                {"link_id": "chd_044", "link_name": "Sector 11-12 Road", "lat": 30.7400, "lng": 76.7820},
                {"link_id": "chd_045", "link_name": "Sector 15-16 Road", "lat": 30.7370, "lng": 76.7755},
                {"link_id": "chd_046", "link_name": "Sector 16-17 Road", "lat": 30.7350, "lng": 76.7810},
                {"link_id": "chd_047", "link_name": "Sector 19-20 Road", "lat": 30.7290, "lng": 76.7830},
                {"link_id": "chd_048", "link_name": "Sector 20-21 Road", "lat": 30.7260, "lng": 76.7840},
                {"link_id": "chd_049", "link_name": "Sector 24-25 Service Road", "lat": 30.7185, "lng": 76.7760},
                {"link_id": "chd_050", "link_name": "Sector 32-33 Connector", "lat": 30.7148, "lng": 76.7700},
            ]
        
        frames = []
        np.random.seed(42)
        
        # Generate 60 frames (5 minutes of data at 5s intervals)
        for i in range(60):
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
        first_iteration = True
        while self.is_running:
            if self.frames:
                idx = self.current_frame_idx % len(self.frames)

                # On wrap-around (not first run): reset detector + optionally refetch
                if idx == 0 and not first_iteration:
                    logger.info("Feed replay loop wrap — firing loop_end callbacks")
                    for cb in self._loop_end_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(cb):
                                await cb()
                            else:
                                cb()
                        except Exception as e:
                            logger.error(f"Loop-end callback error: {e}")
                    # Try to refresh data from NYC API
                    if self.active_city == "nyc" and self.app_token:
                        fresh = await self._fetch_nyc_live()
                        if fresh:
                            self.frames = fresh
                            self.current_frame_idx = 0
                            logger.info(f"Refreshed NYC data: {len(fresh)} frames")

                first_iteration = False
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
