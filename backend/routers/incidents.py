"""Incident REST endpoints."""

import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

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
    if "resolved_at" in doc and hasattr(doc["resolved_at"], 'isoformat'):
        doc["resolved_at"] = doc["resolved_at"].isoformat()
    return doc

class IncidentReport(BaseModel):
    title: str
    city: str
    location_str: str
    description: str
    severity: str = "moderate"
    needs_ambulance: bool = False
    media_url: str | None = None

class ResolveRequest(BaseModel):
    operator: str

@router.post("/report")
async def report_incident(report: IncidentReport, request: Request):
    """User-app endpoint to report an incident and queue it for operators."""
    city = report.city.lower()
    incident_doc = {
        "title": report.title,
        "city": city,
        "status": "active",
        "severity": report.severity,
        "on_street": report.location_str,
        "description": report.description,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "assigned_operator": None,
        "needs_ambulance": report.needs_ambulance,
        "media_url": report.media_url
    }
    
    if db.incidents is None:
        raise HTTPException(status_code=503, detail="Database offline")

    # Insert
    result = await db.incidents.insert_one(incident_doc)
    incident_id = str(result.inserted_id)
    incident_doc["_id"] = incident_id
    
    # Enqueue the incident
    ws_manager = request.app.state.ws_manager
    queue_manager = request.app.state.operator_queue
    
    assigned_op = await queue_manager.enqueue_incident(city, incident_id, ws_manager)
    incident_doc["assigned_operator"] = assigned_op
    
    # Broadcast the new incident
    await ws_manager.broadcast_to_city(city, {
        "type": "incident_detected",
        "data": {**incident_doc}
    })
    
    return {"status": "reported", "incident_id": incident_id, "assigned_operator": assigned_op}


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
async def resolve_incident(incident_id: str, body: ResolveRequest, request: Request):
    """Mark an incident as resolved — only the assigned operator can resolve."""
    if db.incidents is None:
        raise HTTPException(status_code=503, detail="Database offline")
    try:
        oid = ObjectId(incident_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")

    # Fetch the incident first
    doc = await db.incidents.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Check operator authorization
    assigned = doc.get("assigned_operator")
    if assigned and assigned != body.operator:
        raise HTTPException(
            status_code=403,
            detail=f"Only the assigned operator ({assigned}) can resolve this incident"
        )

    # Mark resolved
    await db.incidents.update_one(
        {"_id": oid},
        {"$set": {"status": "resolved", "resolved_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Clear incident-generated congestion zone
    if db.congestion_zones is not None:
        await db.congestion_zones.delete_many({"incident_id": incident_id})

    # Broadcast resolution via WebSocket
    ws_manager = request.app.state.ws_manager
    incident_city = doc.get("city", "nyc")

    await ws_manager.broadcast_to_city(incident_city, {
        "type": "congestion_cleared",
        "data": {"zone_id": f"incident_{incident_id}"},
    })

    await ws_manager.broadcast_to_city(incident_city, {
        "type": "incident_resolved",
        "data": {"incident_id": incident_id},
    })

    # Free the operator
    if assigned:
        queue_manager = request.app.state.operator_queue
        await queue_manager.free_operator(doc.get("city"), assigned, ws_manager)

    logger.info(f"Incident {incident_id} resolved by {body.operator}")
    return {"status": "resolved", "incident_id": incident_id}


@router.post("/{incident_id}/dismiss")
async def dismiss_incident(incident_id: str, body: ResolveRequest, request: Request):
    """Mark an incident as dismissed (false alarm / bluff) — only assigned operator can dismiss."""
    if db.incidents is None:
        raise HTTPException(status_code=503, detail="Database offline")
    try:
        oid = ObjectId(incident_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")

    doc = await db.incidents.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Incident not found")

    assigned = doc.get("assigned_operator")
    if assigned and assigned != body.operator:
        raise HTTPException(
            status_code=403,
            detail=f"Only the assigned operator ({assigned}) can dismiss this incident"
        )

    await db.incidents.update_one(
        {"_id": oid},
        {"$set": {
            "status": "dismissed",
            "dismissed_at": datetime.now(timezone.utc).isoformat(),
            "dismissed_by": body.operator,
            "dismiss_reason": "false_alarm",
        }},
    )

    # Clear incident-generated congestion zone
    if db.congestion_zones is not None:
        await db.congestion_zones.delete_many({"incident_id": incident_id})

    ws_manager = request.app.state.ws_manager
    incident_city = doc.get("city", "nyc")

    await ws_manager.broadcast_to_city(incident_city, {
        "type": "congestion_cleared",
        "data": {"zone_id": f"incident_{incident_id}"},
    })

    await ws_manager.broadcast_to_city(incident_city, {
        "type": "incident_resolved",
        "data": {"incident_id": incident_id},
    })

    if assigned:
        queue_manager = request.app.state.operator_queue
        await queue_manager.free_operator(doc.get("city"), assigned, ws_manager)

    logger.info(f"Incident {incident_id} dismissed by {body.operator} (false alarm)")
    return {"status": "dismissed", "incident_id": incident_id}


@router.post("/{incident_id}/claim")
async def claim_incident(incident_id: str, body: ResolveRequest, request: Request):
    """Allow an operator to manually claim an unassigned incident."""
    if db.incidents is None:
        raise HTTPException(status_code=503, detail="Database offline")
    try:
        oid = ObjectId(incident_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")

    doc = await db.incidents.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Incident not found")

    if doc.get("assigned_operator"):
        raise HTTPException(status_code=400, detail="Incident is already assigned")

    # Update DB
    await db.incidents.update_one(
        {"_id": oid},
        {"$set": {"assigned_operator": body.operator}}
    )

    ws_manager = request.app.state.ws_manager
    incident_city = doc.get("city", "nyc")
    
    # Broadcast claim
    await ws_manager.broadcast_to_city(incident_city, {
        "type": "incident_assigned",
        "data": {"incident_id": incident_id, "operator": body.operator, "city": incident_city}
    })

    # Update operator queue state
    queue_manager = request.app.state.operator_queue
    city_state = queue_manager.state.get(incident_city)
    if city_state:
        if body.operator in city_state["ready"]:
            city_state["ready"].remove(body.operator)
        city_state["blocked"].add(body.operator)
        if incident_id in city_state["wait"]:
            try:
                city_state["wait"].remove(incident_id)
            except ValueError:
                pass

    logger.info(f"Incident {incident_id} manually claimed by {body.operator}")
    return {"status": "claimed", "incident_id": incident_id, "operator": body.operator}


@router.get("/{incident_id}/routes")
async def get_incident_routes(incident_id: str):
    """Return stored routes for an incident from the diversion_routes collection."""
    if db.diversion_routes is None:
        return {
            "version": "v2",
            "incident_id": incident_id,
            "blocked": None,
            "alternate": None,
            "origin": None,
            "destination": None,
            "meta": {},
        }

    route_doc = await db.diversion_routes.find_one({"incident_id": incident_id})
    if not route_doc:
        return {
            "version": "v2",
            "incident_id": incident_id,
            "blocked": None,
            "alternate": None,
            "origin": None,
            "destination": None,
            "meta": {},
        }

    blocked = route_doc.get("blocked") or route_doc.get("blocked_route")
    alternate = route_doc.get("alternate") or route_doc.get("alternate_route")

    return {
        "version": route_doc.get("schema_version", "v1"),
        "incident_id": incident_id,
        "blocked": blocked,
        "alternate": alternate,
        "origin": route_doc.get("origin"),
        "destination": route_doc.get("destination"),
        "meta": route_doc.get("route_meta", {}),
    }


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
    if "version" not in doc:
        doc["version"] = "v1"
    return _serialize(doc)
