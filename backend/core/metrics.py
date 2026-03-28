"""Prometheus metrics registry for Sentinel."""
from prometheus_client import Counter, Histogram, Gauge

incidents_created = Counter(
    "sentinel_incidents_created_total",
    "Total incidents created",
    ["city", "severity", "source"]
)
incidents_resolved = Counter(
    "sentinel_incidents_resolved_total",
    "Total incidents resolved",
    ["city"]
)
llm_latency = Histogram(
    "sentinel_llm_latency_seconds",
    "LLM generation latency",
    ["provider"],
    buckets=[0.5, 1, 2, 5, 10, 30]
)
active_incidents = Gauge(
    "sentinel_active_incidents",
    "Currently active incidents",
    ["city"]
)
ws_connections = Gauge(
    "sentinel_ws_connections_total",
    "Active WebSocket connections"
)
route_recomputes = Counter(
    "sentinel_route_recomputes_total",
    "Route recomputations triggered",
    ["city", "reason"]
)
circuit_breaker_opens = Counter(
    "sentinel_circuit_breaker_opens_total",
    "Circuit breaker open events",
    ["service"]
)
task_queue_depth = Gauge(
    "sentinel_task_queue_depth",
    "Pending background tasks",
    ["task_type"]
)
