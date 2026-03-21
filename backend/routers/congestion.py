from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/active")
async def get_active_congestion(request: Request):
    """Return all currently active congestion zones."""
    detector = request.app.state.congestion_detector
    zones = detector.get_active_zones()
    return {"zones": zones}
