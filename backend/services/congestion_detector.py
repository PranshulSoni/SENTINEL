import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Callable
from collections import defaultdict

logger = logging.getLogger(__name__)


class CongestionDetector:
    """Detects traffic congestion from sustained low speeds (not sudden drops)."""
    
    def __init__(
        self,
        speed_threshold: float = 12.0,       # mph — below this = congested
        min_congested_frames: int = 6,        # 6 frames × 5s = 30s sustained
        min_congested_segments: int = 2,      # at least 2 segments in same area
        cooldown_seconds: float = 180,        # 3 min between congestion alerts
        recovery_frames: int = 4,             # 4 clear frames to clear congestion
    ):
        self.speed_threshold = speed_threshold
        self.min_congested_frames = min_congested_frames
        self.min_congested_segments = min_congested_segments
        self.cooldown_seconds = cooldown_seconds
        self.recovery_frames_needed = recovery_frames
        
        # Per-segment consecutive low-speed frame count
        self._low_speed_count: dict[str, int] = defaultdict(int)
        # Per-segment metadata
        self._segment_meta: dict[str, dict] = {}
        # Currently active congestion zones: {zone_id: zone_data}
        self._active_zones: dict[str, dict] = {}
        # Recovery counters per zone
        self._zone_recovery: dict[str, int] = defaultdict(int)
        # Last alert time
        self._last_alert_time: float = 0
        # Callbacks
        self._congestion_callbacks: list[Callable] = []
        self._clear_callbacks: list[Callable] = []
    
    def on_congestion(self, callback: Callable):
        """Register callback for new congestion detection."""
        self._congestion_callbacks.append(callback)
    
    def on_clear(self, callback: Callable):
        """Register callback for congestion cleared."""
        self._clear_callbacks.append(callback)
    
    def get_active_zones(self) -> list[dict]:
        """Return all active congestion zones."""
        return list(self._active_zones.values())
    
    async def process_frame(self, segments: list[dict]):
        """Process a feed frame and check for congestion."""
        congested_segments = []
        
        for seg in segments:
            link_id = seg["link_id"]
            speed = seg.get("speed", 0)
            
            # Cache metadata
            self._segment_meta[link_id] = {
                "link_name": seg.get("link_name", ""),
                "lat": seg.get("lat", 0),
                "lng": seg.get("lng", 0),
            }
            
            if speed < self.speed_threshold and speed > 0:
                self._low_speed_count[link_id] += 1
            else:
                self._low_speed_count[link_id] = 0
            
            # Check if this segment has been congested long enough
            if self._low_speed_count[link_id] >= self.min_congested_frames:
                meta = self._segment_meta[link_id]
                congested_segments.append({
                    "link_id": link_id,
                    "link_name": meta.get("link_name", ""),
                    "speed": speed,
                    "avg_speed": round(speed, 1),  # current speed (already sustained)
                    "congested_frames": self._low_speed_count[link_id],
                    "lat": meta.get("lat", 0),
                    "lng": meta.get("lng", 0),
                })
        
        # Check for new congestion zones (cluster of congested segments)
        if len(congested_segments) >= self.min_congested_segments:
            # Check cooldown
            now = time.time()
            if now - self._last_alert_time < self.cooldown_seconds and self._active_zones:
                # Update existing zones but don't create new alerts
                self._update_existing_zones(congested_segments)
                return
            
            # Create/update congestion zone
            zone_id = self._get_zone_id(congested_segments)
            if zone_id not in self._active_zones:
                await self._trigger_congestion(zone_id, congested_segments)
            else:
                # Reset recovery counter since congestion is still present
                self._zone_recovery[zone_id] = 0
        
        # Check for recovery of active zones
        zones_to_clear = []
        for zone_id, zone in self._active_zones.items():
            zone_segment_ids = {s["link_id"] for s in zone.get("segments", [])}
            still_congested = any(
                s["link_id"] in zone_segment_ids for s in congested_segments
            )
            if not still_congested:
                self._zone_recovery[zone_id] += 1
                if self._zone_recovery[zone_id] >= self.recovery_frames_needed:
                    zones_to_clear.append(zone_id)
            else:
                self._zone_recovery[zone_id] = 0
        
        for zone_id in zones_to_clear:
            await self._clear_congestion(zone_id)
    
    def _get_zone_id(self, segments: list[dict]) -> str:
        """Generate a zone ID from the primary congested segment."""
        if not segments:
            return "unknown"
        primary = max(segments, key=lambda s: s.get("congested_frames", 0))
        return f"congestion_{primary['link_id']}"
    
    def _update_existing_zones(self, congested_segments: list[dict]):
        """Update existing zone data without triggering new alerts."""
        for zone_id, zone in self._active_zones.items():
            zone["segments"] = congested_segments
            zone["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    async def _trigger_congestion(self, zone_id: str, congested_segments: list[dict]):
        """Create a new congestion zone and notify callbacks."""
        primary = max(congested_segments, key=lambda s: s.get("congested_frames", 0))
        
        zone = {
            "zone_id": zone_id,
            "city": "",  # set by caller
            "type": "congestion",
            "status": "active",
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "severity": "moderate" if primary["speed"] > 5 else "severe",
            "location": {
                "type": "Point",
                "coordinates": [primary["lng"], primary["lat"]],
            },
            "primary_street": primary["link_name"],
            "segments": congested_segments,
            "affected_segment_ids": [s["link_id"] for s in congested_segments],
        }
        
        self._active_zones[zone_id] = zone
        self._zone_recovery[zone_id] = 0
        self._last_alert_time = time.time()
        
        logger.info(
            f"CONGESTION DETECTED: {primary['link_name']} "
            f"(speed: {primary['speed']:.0f} mph, sustained {primary['congested_frames']} frames)"
        )
        
        for callback in self._congestion_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(zone)
                else:
                    callback(zone)
            except Exception as e:
                logger.error(f"Congestion callback error: {e}")
    
    async def _clear_congestion(self, zone_id: str):
        """Clear a congestion zone."""
        zone = self._active_zones.pop(zone_id, None)
        self._zone_recovery.pop(zone_id, None)
        
        if zone:
            zone["status"] = "cleared"
            zone["cleared_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Congestion cleared: {zone.get('primary_street', zone_id)}")
            
            for callback in self._clear_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(zone)
                    else:
                        callback(zone)
                except Exception as e:
                    logger.error(f"Congestion clear callback error: {e}")
    
    def reset(self):
        """Reset all state (e.g., on city switch or loop wrap)."""
        self._low_speed_count.clear()
        self._segment_meta.clear()
        self._active_zones.clear()
        self._zone_recovery.clear()
        self._last_alert_time = 0
