"""LLM intelligence endpoints — manual trigger and retrieval."""

import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request

import db
from data.signal_baselines import CITY_BASELINES
from services.llm_service import LLMService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/regenerate/{incident_id}")
async def regenerate_llm(incident_id: str, request: Request):
    """Manually re-trigger the LLM pipeline for an existing incident."""
    # Validate incident exists
    if db.incidents is None:
        raise HTTPException(status_code=503, detail="Database offline")
    
    try:
        oid = ObjectId(incident_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid incident ID")
    
    incident = await db.incidents.find_one({"_id": oid})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    incident["_id"] = str(incident["_id"])
    
    # Get services
    llm_service = request.app.state.llm_service
    prompt_builder = request.app.state.prompt_builder
    collision_service = request.app.state.collision_service
    routing_service = request.app.state.routing_service
    feed_simulator = request.app.state.feed_simulator
    ws_manager = request.app.state.ws_manager
    city = incident.get("city", request.app.state.active_city)
    
    # Gather context
    segments = feed_simulator.get_current_segments()
    
    coords = incident.get("location", {}).get("coordinates", [0, 0])
    lng, lat = coords[0], coords[1]
    
    # Fetch collisions
    collision_context = ""
    try:
        collisions = await collision_service.get_nearby_collisions(lat, lng)
        collision_context = collision_service.get_collision_context_for_llm(collisions)
    except Exception:
        pass
    
    # Compute diversions
    diversions = []
    try:
        diversions = await routing_service.compute_diversions_for_incident(
            (lng, lat), city=city
        )
    except Exception:
        pass
    
    baselines = CITY_BASELINES.get(city, {})
    
    # Build prompt
    system_prompt, user_content = prompt_builder.build_incident_prompt(
        city=city,
        incident=incident,
        segments=segments,
        diversions=diversions,
        baselines=baselines,
        collision_context=collision_context,
    )
    
    # Call LLM
    raw_output = await llm_service.generate(system_prompt, user_content)
    
    if not raw_output:
        raise HTTPException(status_code=502, detail="LLM returned no output")
    
    # Parse and save
    parsed = LLMService.parse_structured_output(raw_output)
    
    llm_doc = {
        "incident_id": incident_id,
        "signal_retiming": parsed.get("signal_retiming", {"intersections": [], "raw_text": ""}),
        "diversions": parsed.get("diversions", {"routes": [], "raw_text": ""}),
        "alerts": parsed.get("alerts", {}),
        "narrative_update": parsed.get("narrative_update", ""),
        "cctv_summary": parsed.get("cctv_summary", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    if db.llm_outputs is not None:
        await db.llm_outputs.insert_one(llm_doc)

    # Serialize ObjectId before broadcast/return
    if "_id" in llm_doc:
        llm_doc["_id"] = str(llm_doc["_id"])

    # Broadcast via WebSocket
    await ws_manager.broadcast_to_city(city, {
        "type": "llm_output",
        "data": {**llm_doc, "incident_id": incident_id},
    })

    logger.info(f"LLM regenerated for incident {incident_id}")
    return llm_doc
