"""Incident REST endpoints."""

import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Request

import db

logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize(doc: dict) -> dict:
    """Convert MongoDB document for JSON response."""
    if not doc:
        return doc
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if "created_at" in doc and hasattr(doc["created_at"], 'isoformat'):
        doc["created_at"] = doc["created_at"].isoformat()
    if "detected_at" in doc and hasattr(doc["detected_at"], 'isoformat'):
        doc["detected_at"] = doc["detected_at"].isoformat()
    if "resolved_at" in doc and hasattr(doc["resolved_at"], 'isoformat'):
        doc["resolved_at"] = doc["resolved_at"].isoformat()
    return doc


@router.get("/")
async def list_incidents(
    request: Request,
    city: str | None = Query(None),
    status: str | None = Query(None),
):
    """List incidents with optional city/status filters."""
    if db.incidents is None:
        return []
    try:
        query: dict = {}
        if city:
            query["city"] = city
        if status:
            query["status"] = status
        cursor = db.incidents.find(query).sort("detected_at", -1)
        results = [_serialize(doc) async for doc in cursor]
        return results
    except Exception as e:
        logger.error(f"list_incidents error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch incidents")


@router.get("/{incident_id}")
async def get_incident(incident_id: str):
    """Get a single incident by ID."""
    if db.incidents is None:
        raise HTTPException(status_code=503, detail="Database offline")
    try:
        doc = await db.incidents.find_one({"_id": ObjectId(incident_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")

    if not doc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize(doc)


@router.post("/{incident_id}/resolve")
async def resolve_incident(incident_id: str, request: Request):
    """Mark an incident as resolved."""
    if db.incidents is None:
        raise HTTPException(status_code=503, detail="Database offline")
    try:
        oid = ObjectId(incident_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")

    result = await db.incidents.update_one(
        {"_id": oid},
        {"$set": {"status": "resolved", "resolved_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Broadcast resolution via WebSocket
    ws_manager = request.app.state.ws_manager
    await ws_manager.broadcast({
        "type": "incident_resolved",
        "data": {"incident_id": incident_id},
    })

    logger.info(f"Incident {incident_id} resolved")
    return {"status": "resolved", "incident_id": incident_id}


@router.get("/{incident_id}/llm-output")
async def get_llm_output(incident_id: str):
    """Get the latest LLM output for an incident."""
    if db.llm_outputs is None:
        raise HTTPException(status_code=503, detail="Database offline")
    try:
        ObjectId(incident_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")

    doc = await db.llm_outputs.find_one(
        {"incident_id": incident_id},
        sort=[("created_at", -1)],
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No LLM output for this incident")
    return _serialize(doc)
