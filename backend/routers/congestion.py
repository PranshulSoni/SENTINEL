from fastapi import APIRouter, Request
import db as db_module

router = APIRouter()


@router.get("/active")
async def get_active_congestion(request: Request):
    """Return all currently active congestion zones."""
    detector = request.app.state.congestion_detector
    zones = detector.get_active_zones()
    return {"zones": zones}


@router.get("/zones/default")
async def list_default_zones(city: str = "nyc"):
    """List default congestion zones for a city."""
    if db_module.congestion_zones is None:
        return []
    cursor = db_module.congestion_zones.find(
        {"city": city, "source": "default"},
        {"_id": 0}
    )
    return [doc async for doc in cursor]


@router.get("/history")
async def get_congestion_history(request: Request, limit: int = 20):
    """Return recent congestion zones from DB."""
    congestion_col = getattr(db_module, 'congestion_zones', None)
    if congestion_col is None:
        return {"zones": []}
    cursor = congestion_col.find({}, {"_id": 0}).sort("detected_at", -1).limit(limit)
    zones = await cursor.to_list(length=limit)
    return {"zones": zones}