"""
WebSocket Broadcaster. Subsribes to EventBus and sends WS messages.
Decouples business logic from communication protocol.
"""
import logging
from typing import Any, Dict
from core.event_bus import EventBus

logger = logging.getLogger(__name__)

class Broadcaster:
    def __init__(self, event_bus: EventBus, ws_manager: Any):
        self.event_bus = event_bus
        self.ws_manager = ws_manager
        self._register_handlers()

    def _register_handlers(self):
        """Subscribe to all events that should be broadcast."""
        # Mapping: event_type -> ws_message_type
        self.event_bus.subscribe("incident_detected", self.handle_incident_detected)
        self.event_bus.subscribe("incident_resolved", self.handle_incident_resolved)
        self.event_bus.subscribe("incident_routes", self.handle_incident_routes)
        self.event_bus.subscribe("congestion_alert", self.handle_congestion_alert)
        self.event_bus.subscribe("congestion_cleared", self.handle_congestion_cleared)
        self.event_bus.subscribe("llm_output", self.handle_llm_output)
        self.event_bus.subscribe("vlm_analysis", self.handle_vlm_analysis)
        self.event_bus.subscribe("collisions", self.handle_collisions)
        self.event_bus.subscribe("cctv_event", self.handle_cctv_event)

    async def _broadcast(self, city: str, msg_type: str, data: Dict[str, Any]):
        """Internal helper for city-based broadcast."""
        if not self.ws_manager:
            return
        await self.ws_manager.broadcast_to_city(city, {
            "type": msg_type,
            "data": data
        })

    # --- Handlers ---
    async def handle_incident_detected(self, data: Dict[str, Any]):
        await self._broadcast(data.get("city"), "incident_detected", data)

    async def handle_incident_resolved(self, data: Dict[str, Any]):
        await self._broadcast(data.get("city"), "incident_resolved", data)

    async def handle_incident_routes(self, data: Dict[str, Any]):
        await self._broadcast(data.get("city"), "incident_routes", data)

    async def handle_congestion_alert(self, data: Dict[str, Any]):
        await self._broadcast(data.get("city"), "congestion_alert", data)

    async def handle_congestion_cleared(self, data: Dict[str, Any]):
        await self._broadcast(data.get("city"), "congestion_cleared", data)

    async def handle_llm_output(self, data: Dict[str, Any]):
        await self._broadcast(data.get("city"), "llm_output", data)

    async def handle_vlm_analysis(self, data: Dict[str, Any]):
        await self._broadcast(data.get("city"), "vlm_analysis", data)

    async def handle_collisions(self, data: Dict[str, Any]):
        await self._broadcast(data.get("city"), "collisions", data)

    async def handle_cctv_event(self, data: Dict[str, Any]):
        await self._broadcast(data.get("city"), "cctv_event", data)
