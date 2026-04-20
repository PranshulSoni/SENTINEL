"""Social alert endpoints for city-scoped user delivery."""

from datetime import datetime, timezone
import logging

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from pydantic import BaseModel

import db
from data.social_users import DEFAULT_SOCIAL_USERS
from core.auth import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


class PublishSocialAlertRequest(BaseModel):
    city: str
    message: str
    incident_id: str | None = None
    operator: str | None = None


def _serialize_doc(doc: dict) -> dict:
    out = dict(doc)
    if "_id" in out:
        out["_id"] = str(out["_id"])
    if "published_at" in out and hasattr(out["published_at"], "isoformat"):
        out["published_at"] = out["published_at"].isoformat()
    return out


def _default_users_for_city(city: str) -> list[dict]:
    city_l = (city or "").lower()
    return [u for u in DEFAULT_SOCIAL_USERS if u.get("city") == city_l]


def _resolve_city_recipients(city: str, db_users: list[dict] | None = None) -> list[str]:
    """
    Resolve all recipients for a city. If DB users are missing/empty, fallback to
    seeded defaults so publish always reaches the full city audience.
    """
    candidates = db_users if db_users else _default_users_for_city(city)
    recipients: list[str] = []
    seen: set[str] = set()
    for u in candidates:
        name = str(u.get("name", "")).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        recipients.append(name)
    return recipients


@router.get("/users")
async def get_social_users(city: str = Query(..., description="nyc or chandigarh")):
    city_l = city.lower().strip()
    if city_l not in ("nyc", "chandigarh"):
        raise HTTPException(status_code=400, detail=f"Unsupported city: {city}")

    if db.user_profiles is None:
        return _default_users_for_city(city_l)

    docs = await db.user_profiles.find({"city": city_l}).sort("name", 1).to_list(100)
    return [{"name": d.get("name"), "city": d.get("city")} for d in docs]


@router.get("/alerts")
async def get_social_alerts(
    city: str = Query(..., description="nyc or chandigarh"),
    username: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
):
    city_l = city.lower().strip()
    if city_l not in ("nyc", "chandigarh"):
        raise HTTPException(status_code=400, detail=f"Unsupported city: {city}")

    if db.social_alerts is None:
        return []

    query: dict = {"city": city_l}
    if username:
        query["recipients"] = username
    docs = await db.social_alerts.find(query).sort("published_at", -1).to_list(limit)
    return [_serialize_doc(d) for d in docs]


@router.post("/publish")
async def publish_social_alert(body: PublishSocialAlertRequest, request: Request, _=Depends(require_api_key)):
    city = (body.city or "").lower().strip()
    if city not in ("nyc", "chandigarh"):
        raise HTTPException(status_code=400, detail=f"Unsupported city: {body.city}")
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Alert message is required")

    recipients: list[str]
    if db.user_profiles is None:
        recipients = _resolve_city_recipients(city)
    else:
        users = await db.user_profiles.find({"city": city}).sort("name", 1).to_list(200)
        recipients = _resolve_city_recipients(city, users)

    alert_doc = {
        "city": city,
        "message": message,
        "incident_id": body.incident_id,
        "operator": body.operator or "controller",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "recipients": recipients,
        "recipient_count": len(recipients),
        "channel": "social_media",
    }

    if db.social_alerts is not None:
        await db.social_alerts.insert_one(dict(alert_doc))

    ws_manager = request.app.state.ws_manager
    await ws_manager.broadcast_to_city(city, {
        "type": "social_alert_published",
        "data": alert_doc,
    })

    logger.info(
        "Social alert published city=%s recipients=%s incident=%s",
        city,
        len(recipients),
        body.incident_id or "none",
    )
    return {"status": "published", **alert_doc}

