"""
SENTINEL — Incident Narrative Data Models
Pydantic models for incident events, narrative state, and query/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ──────────────────────────────────────────────
# Core Data Models
# ──────────────────────────────────────────────

class IncidentEvent(BaseModel):
    """A single event in the running incident narrative."""
    id: int
    timestamp: str
    category: str          # dispatch | hazard | traffic | medical | resource | update | resolution
    description: str
    severity: str          # critical | high | medium | low | info
    reported_by: str = "System"


class IncidentNarrative(BaseModel):
    """The full running narrative of a traffic incident."""
    incident_id: str
    incident_type: str
    location: str
    started_at: str
    commander: str
    status: str            # active | contained | resolved
    hazmat_involved: bool
    lanes_affected: dict   # e.g. {"southbound_lane_1": "closed", "northbound_all": "open"}
    weather: str
    events: list[IncidentEvent]


# ──────────────────────────────────────────────
# API Request / Response Schemas
# ──────────────────────────────────────────────

class QueryRequest(BaseModel):
    """Officer's conversational question or voice command."""
    question: Optional[str] = None
    audio_base64: Optional[str] = None
    audio_mime_type: Optional[str] = None


class QueryResponse(BaseModel):
    """Structured answer returned to the officer."""
    answer: str
    safety_assessment: str  # safe | caution | unsafe | unknown
    confidence: str         # high | medium | low
    timestamp: str
    sources_referenced: int


class AddEventRequest(BaseModel):
    """Request to add a new event to the running narrative."""
    category: str
    description: str
    severity: str = "medium"
    reported_by: str = "Officer"
