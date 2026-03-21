"""Chat API endpoints — conversational LLM co-pilot."""

import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request

import db
from models.schemas import ChatRequest
from data.signal_baselines import CITY_BASELINES

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("")
async def send_chat(body: ChatRequest, request: Request):
    """Send a message to the LLM co-pilot and get a response."""
    llm_service = request.app.state.llm_service
    prompt_builder = request.app.state.prompt_builder
    collision_service = request.app.state.collision_service
    feed_simulator = request.app.state.feed_simulator
    incident_detector = request.app.state.incident_detector
    city = request.app.state.active_city
    
    # Get current context
    incident = incident_detector.get_active_incident()
    segments = feed_simulator.get_current_segments()
    
    # If incident_id provided, try to load from DB
    if body.incident_id and db.incidents is not None:
        try:
            stored = await db.incidents.find_one({"_id": ObjectId(body.incident_id)})
            if stored:
                incident = stored
                incident["_id"] = str(incident["_id"])
        except Exception:
            pass
    
    # Build collision context if we have incident location
    collision_context = ""
    if incident:
        coords = incident.get("location", {}).get("coordinates", [0, 0])
        if isinstance(coords, list) and len(coords) >= 2:
            lng, lat = coords[0], coords[1]
        else:
            lat = incident.get("location", {}).get("lat", 0)
            lng = incident.get("location", {}).get("lng", 0)
        
        if lat and lng:
            try:
                collisions = await collision_service.get_nearby_collisions(lat, lng)
                collision_context = collision_service.get_collision_context_for_llm(collisions)
            except Exception:
                pass
    
    # Build system prompt for chat mode
    system_prompt = prompt_builder.build_chat_prompt(
        city=city,
        incident=incident,
        segments=segments,
        collision_context=collision_context,
    )
    
    # Build message history from DB if available
    chat_messages = [{"role": "system", "content": system_prompt}]
    
    incident_id_str = body.incident_id or "general"
    
    if db.chat_history is not None:
        try:
            history_doc = await db.chat_history.find_one(
                {"incident_id": incident_id_str},
                sort=[("session_start", -1)]
            )
            if history_doc and "messages" in history_doc:
                # Add last 10 messages for context window management
                for msg in history_doc["messages"][-10:]:
                    chat_messages.append({
                        "role": msg["role"],
                        "content": msg["content"],
                    })
        except Exception as e:
            logger.warning(f"Failed to load chat history: {e}")
    
    # Add current user message
    chat_messages.append({"role": "user", "content": body.message})
    
    # Call LLM
    try:
        response_text = await llm_service.generate_chat_response(
            messages=chat_messages, max_tokens=1000
        )
    except Exception as e:
        logger.error(f"LLM chat error: {e}")
        response_text = None
    
    if not response_text:
        response_text = "I'm unable to generate a response right now. Please check LLM API keys in your .env configuration."
    
    # Save to chat_history
    now = datetime.now(timezone.utc)
    user_msg = {"role": "user", "content": body.message, "timestamp": now.isoformat()}
    assistant_msg = {"role": "assistant", "content": response_text, "timestamp": now.isoformat()}
    
    if db.chat_history is not None:
        try:
            await db.chat_history.update_one(
                {"incident_id": incident_id_str},
                {
                    "$push": {"messages": {"$each": [user_msg, assistant_msg]}},
                    "$setOnInsert": {
                        "city": city,
                        "session_start": now,
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.warning(f"Failed to save chat history: {e}")
    
    return {
        "role": "assistant",
        "content": response_text,
        "timestamp": now.isoformat(),
        "incident_id": incident_id_str,
    }


@router.get("/history/{incident_id}")
async def get_chat_history(incident_id: str):
    """Retrieve chat history for an incident."""
    if db.chat_history is None:
        return {"incident_id": incident_id, "messages": []}
    
    try:
        doc = await db.chat_history.find_one(
            {"incident_id": incident_id},
            sort=[("session_start", -1)]
        )
        if not doc:
            return {"incident_id": incident_id, "messages": []}
        
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc
    except Exception as e:
        logger.error(f"get_chat_history error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chat history")


@router.delete("/history/{incident_id}")
async def clear_chat_history(incident_id: str):
    """Clear chat history for an incident."""
    if db.chat_history is None:
        return {"status": "ok", "message": "No database connection"}
    
    try:
        result = await db.chat_history.delete_many({"incident_id": incident_id})
        return {"status": "ok", "deleted": result.deleted_count}
    except Exception as e:
        logger.error(f"clear_chat_history error: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear chat history")
