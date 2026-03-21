import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Callable
from collections import defaultdict

logger = logging.getLogger(__name__)


class IncidentDetector:
    """Detects traffic incidents from speed anomalies in feed data."""
    
    def __init__(self, baseline_window: int = 5, drop_threshold: float = 0.4, 
                 min_adjacent_segments: int = 2):
        self.baseline_window = baseline_window  # Number of frames for rolling baseline
        self.drop_threshold = drop_threshold      # 40% speed drop = incident
        self.min_adjacent_segments = min_adjacent_segments
        
        # Rolling speed history per segment: {link_id: [speeds]}
        self._speed_history: dict[str, list[float]] = defaultdict(list)
        # Segment metadata cache
        self._segment_meta: dict[str, dict] = {}
        # Currently active incident
        self._active_incident: Optional[dict] = None
        # Callbacks for incident events
        self._callbacks: list[Callable] = []
    
    def on_incident(self, callback: Callable):
        """Register callback for incident detection events."""
        self._callbacks.append(callback)
    
    def get_active_incident(self) -> Optional[dict]:
        """Return currently active incident or None."""
        return self._active_incident
    
    async def process_frame(self, segments: list[dict]):
        """Process a feed frame and check for incidents."""
        anomalous_segments = []
        
        for seg in segments:
            link_id = seg["link_id"]
            speed = seg["speed"]
            
            # Cache metadata
            self._segment_meta[link_id] = {
                "link_name": seg.get("link_name", ""),
                "lat": seg.get("lat", 0),
                "lng": seg.get("lng", 0),
            }
            
            # Update rolling history
            history = self._speed_history[link_id]
            history.append(speed)
            if len(history) > self.baseline_window + 1:
                history.pop(0)
            
            # Need at least baseline_window frames to compare
            if len(history) <= self.baseline_window:
                continue
            
            # Compute baseline (average of previous frames, excluding current)
            baseline = sum(history[:-1]) / len(history[:-1])
            
            if baseline > 5:  # Avoid division issues on already-slow segments
                drop_ratio = 1 - (speed / baseline)
                if drop_ratio >= self.drop_threshold:
                    anomalous_segments.append({
                        "link_id": link_id,
                        "link_name": seg.get("link_name", ""),
                        "speed": speed,
                        "baseline": round(baseline, 1),
                        "drop_pct": round(drop_ratio * 100, 1),
                        "lat": seg.get("lat", 0),
                        "lng": seg.get("lng", 0),
                        "status": seg.get("status", "SLOW"),
                    })
        
        # Check if enough adjacent segments have anomalies
        if len(anomalous_segments) >= self.min_adjacent_segments and not self._active_incident:
            await self._trigger_incident(anomalous_segments)
        elif self._active_incident and len(anomalous_segments) == 0:
            # All segments recovered — resolve incident
            await self._resolve_incident()
    
    async def _trigger_incident(self, anomalous_segments: list[dict]):
        """Create and broadcast a new incident."""
        # Use the segment with the worst drop as the primary location
        worst = max(anomalous_segments, key=lambda s: s["drop_pct"])
        
        severity = "critical" if worst["speed"] < 2 else "major" if worst["speed"] < 10 else "minor"
        
        self._active_incident = {
            "city": "",  # Set by caller
            "status": "active",
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": None,
            "severity": severity,
            "location": {
                "type": "Point",
                "coordinates": [worst["lng"], worst["lat"]]
            },
            "on_street": worst["link_name"].split("(")[0].strip() if "(" in worst["link_name"] else worst["link_name"],
            "cross_street": "",
            "affected_segment_ids": [s["link_id"] for s in anomalous_segments],
            "affected_segments": anomalous_segments,
            "source": "speed_anomaly",
            "crash_record_id": None,
        }
        
        logger.info(f"INCIDENT DETECTED: {severity} at {worst['link_name']} "
                    f"(speed: {worst['speed']} mph, baseline: {worst['baseline']} mph)")
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self._active_incident)
                else:
                    callback(self._active_incident)
            except Exception as e:
                logger.error(f"Incident callback error: {e}")
    
    async def _resolve_incident(self):
        """Mark the active incident as resolved."""
        if self._active_incident:
            self._active_incident["status"] = "resolved"
            self._active_incident["resolved_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("Incident resolved — all segments recovered")
            self._active_incident = None
    
    def reset(self):
        """Reset detector state (e.g., on city switch)."""
        self._speed_history.clear()
        self._segment_meta.clear()
        self._active_incident = None
