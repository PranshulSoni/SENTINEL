"""
Simple in-process circuit breaker.
States: CLOSED (normal) → OPEN (skip) → HALF-OPEN (probe)
No external library required.
"""
import asyncio
import time
import logging
from enum import Enum
from core.metrics import circuit_breaker_opens

logger = logging.getLogger(__name__)

class State(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_sec: float = 30.0):
        self.name = name
        self._threshold = failure_threshold
        self._recovery_sec = recovery_sec
        self._failures = 0
        self._opened_at: float | None = None
        self._state = State.CLOSED

    @property
    def state(self) -> State:
        """Return the current state, checking for recovery timeout."""
        if self._state == State.OPEN and self._opened_at:
            if time.monotonic() - self._opened_at >= self._recovery_sec:
                self._state = State.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} moved to HALF_OPEN")
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if the breaker is currently blocking calls."""
        return self.state == State.OPEN

    def record_success(self) -> None:
        if self._state != State.CLOSED:
            logger.info(f"Circuit breaker {self.name} closed (success)")
        self._failures = 0
        self._state = State.CLOSED
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold and self._state == State.CLOSED:
            logger.warning(f"Circuit breaker {self.name} opened after {self._failures} failures")
            self._state = State.OPEN
            self._opened_at = time.monotonic()
            circuit_breaker_opens.labels(service=self.name).inc()

    async def call(self, coro):
        """Execute a coroutine through the circuit breaker."""
        if self.is_open:
            raise RuntimeError(f"Circuit breaker OPEN for {self.name} — skipping call")
        try:
            result = await coro
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

# Registry of breakers per external dependency
_breakers: dict[str, CircuitBreaker] = {}

def get_breaker(name: str, threshold: int = 3, recovery_sec: float = 30.0) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name, threshold, recovery_sec)
    return _breakers[name]
