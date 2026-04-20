"""
Simple asynchronus Event Bus for inter-service communication.
Decouples producers from consumers.
"""
import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List
from core.tracing import get_trace_id, set_trace_id

logger = logging.getLogger(__name__)

# Type for subscriber: a function that takes event data (dict)
Subscriber = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Subscriber]] = {}

    def subscribe(self, event_type: str, handler: Subscriber):
        """Add a handler for a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type}")

    async def publish(self, event_type: str, data: Dict[str, Any]):
        """Publish an event to all subscribers of the given type."""
        tid = get_trace_id()
        handlers = self._subscribers.get(event_type, [])
        
        if not handlers:
            logger.debug(f"No subscribers for event: {event_type}")
            return

        logger.info(f"Publishing {event_type} to {len(handlers)} subscribers (trace_id={tid})")
        
        # Run all handlers in parallel as background tasks to avoid blocking the publisher
        for handler in handlers:
            asyncio.create_task(self._safe_execute(handler, data, tid))

    async def _safe_execute(self, handler: Subscriber, data: Dict[str, Any], tid: str | None):
        """Execute a single handler safely."""
        set_trace_id(tid)
        try:
            await handler(data)
        except Exception as e:
            logger.error(f"Event handler {handler.__name__} failed: {e}", exc_info=True)
