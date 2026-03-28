"""
Request trace ID — propagated via Python contextvars.
No Jaeger/OTEL needed. One UUID ties together:
  - Structured logs
  - EventBus payloads
  - WebSocket messages
  - LLM call logs
  - External API call logs
"""
import uuid
from contextvars import ContextVar

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

def new_trace_id() -> str:
    tid = str(uuid.uuid4())[:12]  # short UUID, e.g. "a3f2-9c1e-bb"
    _trace_id_var.set(tid)
    return tid

def get_trace_id() -> str:
    return _trace_id_var.get() or "no-trace"

def set_trace_id(tid: str) -> None:
    _trace_id_var.set(tid)
