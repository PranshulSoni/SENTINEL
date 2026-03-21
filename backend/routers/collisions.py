"""Collision REST endpoints — nearby lookups and LLM context."""

import logging

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/nearby")
async def get_nearby_collisions(
    request: Request,
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius_deg: float = Query(0.005, description="Search radius in degrees"),
):
    """Fetch recent collisions near a coordinate."""
    try:
        collisions = await request.app.state.collision_service.get_nearby_collisions(
            lat, lng, radius_deg=radius_deg
        )
        return {"count": len(collisions), "collisions": collisions}
    except Exception as e:
        logger.error(f"get_nearby_collisions error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch collisions")


@router.get("/context")
async def get_collision_context(
    request: Request,
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
):
    """Return formatted collision context string for LLM consumption."""
    try:
        service = request.app.state.collision_service
        collisions = await service.get_nearby_collisions(lat, lng)
        context = service.get_collision_context_for_llm(collisions)
        return {"context": context}
    except Exception as e:
        logger.error(f"get_collision_context error: {e}")
        raise HTTPException(status_code=500, detail="Failed to build collision context")
