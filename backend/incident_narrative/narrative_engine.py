"""
SENTINEL — Narrative Engine
Core logic for managing the incident narrative state — adding events,
serialising the narrative for LLM context, and updating lane statuses.
"""

from datetime import datetime
from .models import IncidentEvent, IncidentNarrative, AddEventRequest


class NarrativeEngine:
    """
    Manages the in-memory incident narrative.
    Provides methods to query state, add events, and serialise
    the narrative into a prompt-ready text block.
    """

    def __init__(self, narrative: IncidentNarrative):
        self._narrative = narrative

    # ── Read ──────────────────────────────────

    @property
    def narrative(self) -> IncidentNarrative:
        return self._narrative

    @property
    def event_count(self) -> int:
        return len(self._narrative.events)

    # ── Write ─────────────────────────────────

    def add_event(self, request: AddEventRequest) -> IncidentEvent:
        """Append a new event to the running narrative."""
        new_id = (
            max(e.id for e in self._narrative.events) + 1
            if self._narrative.events
            else 1
        )
        event = IncidentEvent(
            id=new_id,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            category=request.category,
            description=request.description,
            severity=request.severity,
            reported_by=request.reported_by,
        )
        self._narrative.events.append(event)
        return event

    # ── Serialise for LLM ─────────────────────

    def to_prompt_context(self) -> str:
        """
        Serialise the entire narrative into a structured text block
        suitable for injecting into an LLM system prompt.
        """
        narr = self._narrative

        events_text = "\n".join(
            f"  [{e.timestamp}] [{e.severity.upper()}] [{e.category.upper()}] "
            f"(Reported by: {e.reported_by}) — {e.description}"
            for e in narr.events
        )

        lanes_text = "\n".join(
            f"  • {lane.replace('_', ' ').title()}: {status}"
            for lane, status in narr.lanes_affected.items()
        )

        return (
            f"CURRENT INCIDENT DETAILS:\n"
            f"  Incident ID: {narr.incident_id}\n"
            f"  Type: {narr.incident_type}\n"
            f"  Location: {narr.location}\n"
            f"  Started: {narr.started_at}\n"
            f"  Commander: {narr.commander}\n"
            f"  Status: {narr.status}\n"
            f"  HazMat Involved: {'YES' if narr.hazmat_involved else 'NO'}\n"
            f"  Weather: {narr.weather}\n"
            f"\n"
            f"LANE STATUS:\n"
            f"{lanes_text}\n"
            f"\n"
            f"RUNNING INCIDENT NARRATIVE (chronological):\n"
            f"{events_text}"
        )
