"""
SENTINEL — Incident Narrative API Routes
FastAPI router that exposes the narrative query endpoints.
Mount this router in the main application:

    from incident_narrative.routes import router as narrative_router
    app.include_router(narrative_router)
"""

from fastapi import APIRouter, HTTPException

from .models import (
    IncidentNarrative,
    IncidentEvent,
    QueryRequest,
    QueryResponse,
    AddEventRequest,
)
from .narrative_engine import NarrativeEngine
from .gemini_query import GeminiQueryService
from .seed_data import create_demo_narrative

# ──────────────────────────────────────────────
# Initialise module state
# ──────────────────────────────────────────────

# Create the demo narrative and engine on module load
_narrative = create_demo_narrative()
_engine = NarrativeEngine(_narrative)
_query_service = GeminiQueryService(_engine)

# ──────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────

router = APIRouter(prefix="/api/narrative", tags=["Incident Narrative"])


@router.get("/", response_model=IncidentNarrative)
async def get_narrative():
    """
    Return the current incident narrative timeline.
    Includes all metadata and chronological events.
    """
    return _engine.narrative


@router.post("/query", response_model=QueryResponse)
async def query_narrative(request: QueryRequest):
    """
    Process an officer's conversational query against the running narrative.
    Uses Google Gemini to analyse the incident context and provide
    a safety-aware answer.

    Example questions:
      - "Is it safe to open the southbound lane now?"
      - "What's the status of the fuel spill cleanup?"
      - "Are there any injured people still on scene?"
    """
    try:
        return await _query_service.query(request.model_dump())
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/event", response_model=IncidentEvent)
async def add_event(request: AddEventRequest):
    """
    Add a new event to the running incident narrative.
    This keeps the narrative up-to-date as the incident evolves,
    so subsequent queries reflect the latest situation.
    """
    return _engine.add_event(request)


@router.get("/events", response_model=list[IncidentEvent])
async def get_events():
    """Return only the list of narrative events (without metadata)."""
    return _engine.narrative.events


@router.get("/lanes", response_model=dict)
async def get_lane_status():
    """Return the current lane status summary."""
    return _engine.narrative.lanes_affected
