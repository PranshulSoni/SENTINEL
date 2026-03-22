"""Demo endpoints — inject synthetic incidents for live dashboard demonstrations."""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class InjectIncidentRequest(BaseModel):
    city: str = "nyc"
    severity: str = "major"          # "minor" | "major" | "critical"
    street_name: str = "W 34th St & 7th Ave"
    cross_street: str = ""
    lat: float = 40.7505
    lng: float = -73.9904
    operator: str = ""


# Pre-defined NYC demo locations matching CITY_BASELINES keys in signal_baselines.py
NYC_DEMO_STREETS: dict[str, dict] = {
    "W 34th St & 7th Ave":  {"lat": 40.7505, "lng": -73.9904, "cross": "7th Ave"},
    "Broadway & 34th St":   {"lat": 40.7484, "lng": -73.9878, "cross": "34th St"},
    "10th Ave & 42nd St":   {"lat": 40.7579, "lng": -73.9980, "cross": "42nd St"},
    "W 34th St & 8th Ave":  {"lat": 40.7522, "lng": -73.9932, "cross": "8th Ave"},
    "7th Ave & 33rd St":    {"lat": 40.7498, "lng": -73.9895, "cross": "33rd St"},
}

CHD_DEMO_STREETS: dict[str, dict] = {
    "Madhya Marg & Sector 17 Chowk":  {"lat": 30.7412, "lng": 76.7788, "cross": "Sector 17"},
    "Madhya Marg & Sector 22 Chowk":  {"lat": 30.7320, "lng": 76.7780, "cross": "Sector 22"},
    "Madhya Marg & Aroma Light":      {"lat": 30.7315, "lng": 76.7845, "cross": "Aroma Chowk"},
    "Madhya Marg & PGI Chowk":        {"lat": 30.7646, "lng": 76.7760, "cross": "PGI"},
    "Jan Marg & IT Park Chowk":       {"lat": 30.7270, "lng": 76.8010, "cross": "IT Park"},
    "Jan Marg & Sector 9 Chowk":      {"lat": 30.7554, "lng": 76.7875, "cross": "Sector 9"},
    "Dakshin Marg & Transport Chowk": {"lat": 30.7212, "lng": 76.8040, "cross": "Transport"},
    "Himalaya Marg & Piccadily Sq":   {"lat": 30.7246, "lng": 76.7621, "cross": "Piccadily"},
    "Vidhya Path & Sector 15":        {"lat": 30.7516, "lng": 76.7738, "cross": "Sector 15"},
    "Purv Marg & Housing Board":      {"lat": 30.7135, "lng": 76.8202, "cross": "Housing Board"},
    "Sector 43 ISBT Road":            {"lat": 30.7226, "lng": 76.7511, "cross": "ISBT"},
    "Tribune Chowk":                  {"lat": 30.7270, "lng": 76.7675, "cross": "Tribune"},
    "Rock Garden Road":               {"lat": 30.7523, "lng": 76.8078, "cross": "Rock Garden"},
    "Elante Mall Road":               {"lat": 30.7061, "lng": 76.8016, "cross": "Elante"},
    "Sector 32-33 Connector":         {"lat": 30.7148, "lng": 76.7700, "cross": "Sector 33"},
}

CITY_DEMO_STREETS: dict[str, dict[str, dict]] = {
    "nyc": NYC_DEMO_STREETS,
    "chandigarh": CHD_DEMO_STREETS,
}


_SEVERITY_SPEEDS  = {"minor": 8.0,  "major": 3.0,  "critical": 0.5}
_SEVERITY_DROPS   = {"minor": 71.0, "major": 89.0, "critical": 98.0}
_SEVERITY_BASELINES = {"minor": 27.5, "major": 26.8, "critical": 25.0}
_SEVERITY_STATUS  = {"minor": "SLOW", "major": "SLOW", "critical": "BLOCKED"}


@router.post("/inject-incident")
async def inject_incident(body: InjectIncidentRequest, request: Request):
    """
    Directly inject a synthetic incident into the full _on_incident pipeline.

    - Bypasses IncidentDetector (no 5-frame warmup needed).
    - Returns immediately; LLM pipeline runs as a background asyncio task.
    - Frontend receives `incident_detected` then `llm_output` via WebSocket.
    """
    on_incident = getattr(request.app.state, "on_incident", None)
    if on_incident is None:
        raise HTTPException(
            status_code=503,
            detail="Incident pipeline not ready — app may still be starting up",
        )

    # Resolve coordinates from lookup table (city-aware) — fuzzy partial match
    city_streets = CITY_DEMO_STREETS.get(body.city, NYC_DEMO_STREETS)
    street_data = city_streets.get(body.street_name)
    if street_data is None:
        # Partial match: find first key containing the user's input
        needle = body.street_name.lower()
        for key, val in city_streets.items():
            if needle in key.lower() or key.lower() in needle:
                street_data = val
                break
    street_data = street_data or {}
    lat = street_data.get("lat", body.lat)
    lng = street_data.get("lng", body.lng)
    cross = body.cross_street or street_data.get("cross", "")

    severity = body.severity if body.severity in _SEVERITY_SPEEDS else "major"
    sim_speed    = _SEVERITY_SPEEDS[severity]
    sim_drop     = _SEVERITY_DROPS[severity]
    sim_baseline = _SEVERITY_BASELINES[severity]
    sim_status   = _SEVERITY_STATUS[severity]

    # Street display name: strip cross street from link_name format
    street_label = body.street_name.split("&")[0].strip()

    # Build incident dict matching IncidentDetector._trigger_incident shape exactly
    incident: dict = {
        "city": body.city,
        "status": "active",
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
        "severity": severity,
        "location": {
            "type": "Point",
            "coordinates": [lng, lat],  # GeoJSON: [lng, lat]
        },
        "on_street": street_label,
        "cross_street": cross,
        "needs_ambulance": severity in ("major", "critical"),
        "media_url": "https://images.unsplash.com/photo-1544431527-fc3deed1b559?q=80&w=800&auto=format&fit=crop" if severity in ("major", "critical") else None,
        "affected_segment_ids": [f"demo_{severity}_001"],
        "affected_segments": [
            {
                "link_id": f"demo_{severity}_001",
                "link_name": body.street_name,
                "speed": sim_speed,
                "baseline": sim_baseline,
                "drop_pct": sim_drop,
                "lat": lat,
                "lng": lng,
                "status": sim_status,
            }
        ],
        "source": "demo_injection",
        "crash_record_id": None,
        "requested_operator": body.operator or None,
    }

    # Run the full pipeline as a background task — returns immediately to caller
    asyncio.create_task(on_incident(incident))

    logger.info(f"Demo incident injected: {severity} at {body.street_name}")
    return {
        "status": "injected",
        "severity": severity,
        "street": body.street_name,
        "lat": lat,
        "lng": lng,
        "operator": body.operator or None,
        "message": "Incident injected — LLM pipeline running in background. Watch the WebSocket for updates.",
    }


@router.get("/streets")
async def list_demo_streets(city: str = "nyc"):
    """Return available demo street locations for the given city."""
    streets_dict = CITY_DEMO_STREETS.get(city, NYC_DEMO_STREETS)
    return {
        "city": city,
        "streets": [
            {"name": name, "lat": data["lat"], "lng": data["lng"]}
            for name, data in streets_dict.items()
        ],
    }
