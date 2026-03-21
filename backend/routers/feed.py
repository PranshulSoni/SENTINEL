"""Feed REST endpoints — current segments, city info, baselines."""

import logging

from fastapi import APIRouter, HTTPException, Request

from data.signal_baselines import CITY_BASELINES, CITY_CENTERS
from models.schemas import CitySwitchRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/current")
async def get_current_segments(request: Request):
    """Return the latest feed frame."""
    try:
        segments = request.app.state.feed_simulator.get_current_segments()
        return {"segments": segments}
    except Exception as e:
        logger.error(f"get_current_segments error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch current segments")


@router.get("/city")
async def get_city(request: Request):
    """Return the active city and its map center info."""
    city = request.app.state.active_city
    center = CITY_CENTERS.get(city, {})
    return {"city": city, "center": center}


@router.options("/city/switch")
async def options_switch_city():
    """Handle CORS preflight for city switch endpoint."""
    return {}


@router.post("/city/switch")
async def switch_city(body: CitySwitchRequest, request: Request):
    """Switch the active city — restarts feed and resets detector."""
    city = body.city.lower()
    if city not in CITY_BASELINES:
        raise HTTPException(status_code=400, detail=f"Unknown city: {city}")

    try:
        await request.app.state.feed_simulator.switch_city(city)
        request.app.state.incident_detector.reset()
        request.app.state.collision_service.clear_cache()
        request.app.state.routing_service.clear_cache()
        request.app.state.active_city = city

        logger.info(f"Switched active city to {city}")
        return {"city": city, "center": CITY_CENTERS.get(city, {})}
    except Exception as e:
        logger.error(f"switch_city error: {e}")
        raise HTTPException(status_code=500, detail="Failed to switch city")


@router.get("/baselines")
async def get_baselines(request: Request):
    """Return signal baselines for the active city."""
    city = request.app.state.active_city
    baselines = CITY_BASELINES.get(city, {})
    return {"city": city, "baselines": baselines}
