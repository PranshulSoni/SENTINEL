"""Pydantic models for all SENTINEL API request/response types."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------

class GeoJSONPoint(BaseModel):
    type: str = "Point"
    coordinates: list[float] = Field(
        ..., description="[longitude, latitude]"
    )

    model_config = {"from_attributes": True}


class GeoJSONLineString(BaseModel):
    type: str = "LineString"
    coordinates: list[list[float]] = Field(
        ..., description="[[lng, lat], ...]"
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Traffic feed
# ---------------------------------------------------------------------------

class Segment(BaseModel):
    link_id: str
    link_name: str
    speed: float
    travel_time: float
    status: str  # free | slow | blocked
    lat: float
    lng: float

    model_config = {"from_attributes": True}


class FeedSnapshot(BaseModel):
    city: str
    snapshot_time: datetime
    segments: list[Segment]
    incident_id: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

class Incident(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    city: str
    status: str = "active"  # active | resolved
    severity: str = "medium"  # low | medium | high | critical
    location: GeoJSONPoint
    on_street: str
    cross_street: str = ""
    affected_segment_ids: list[str] = []
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    source: str = "feed"  # feed | manual | cctv
    crash_record_id: Optional[str] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


# ---------------------------------------------------------------------------
# LLM outputs
# ---------------------------------------------------------------------------

class SignalRetimingIntersection(BaseModel):
    name: str
    current_green_ns: int
    current_green_ew: int
    recommended_green_ns: int
    recommended_green_ew: int
    reasoning: str = ""


class SignalRetiming(BaseModel):
    intersections: list[SignalRetimingIntersection] = []


class DiversionRouteDetail(BaseModel):
    priority: int
    name: str
    path: list[str] = []
    estimated_absorption_pct: float = 0.0
    activate_condition: str = ""


class Diversions(BaseModel):
    routes: list[DiversionRouteDetail] = []


class Alerts(BaseModel):
    vms: str = ""
    radio: str = ""
    social_media: str = ""


class LLMOutput(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    incident_id: str
    signal_retiming: SignalRetiming = Field(default_factory=SignalRetiming)
    diversions: Diversions = Field(default_factory=Diversions)
    alerts: Alerts = Field(default_factory=Alerts)
    narrative_update: str = ""
    cctv_summary: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True, "populate_by_name": True}


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str  # user | assistant | system
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    model_used: Optional[str] = None

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class ChatSession(BaseModel):
    incident_id: str
    city: str
    session_start: datetime = Field(default_factory=datetime.utcnow)
    messages: list[ChatMessage] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Signal baselines
# ---------------------------------------------------------------------------

class SignalBaseline(BaseModel):
    city: str
    intersection_name: str
    osm_node_id: Optional[int] = None
    lat: float
    lng: float
    ns_green_seconds: int
    ew_green_seconds: int
    cycle_length_seconds: int
    source: str = "static"  # static | survey | adaptive

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Diversion routes
# ---------------------------------------------------------------------------

class DiversionRouteGeometry(BaseModel):
    priority: int
    name: str
    segment_names: list[str] = []
    geometry: Optional[GeoJSONLineString] = None
    total_length_km: float = 0.0
    estimated_extra_minutes: float = 0.0


class DiversionRoute(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    city: str
    blocked_segment_id: str
    routes: list[DiversionRouteGeometry] = []

    model_config = {"from_attributes": True, "populate_by_name": True}


# ---------------------------------------------------------------------------
# CCTV events
# ---------------------------------------------------------------------------

class CCTVEvent(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    city: str
    incident_id: Optional[str] = None
    camera_id: str
    camera_location: GeoJSONPoint
    event_type: str  # congestion | accident | vehicle_stopped | pedestrian_risk
    confidence: float = 0.0
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    frame_url: Optional[str] = None
    metadata: dict[str, Any] = {}

    model_config = {"from_attributes": True, "populate_by_name": True}


# ---------------------------------------------------------------------------
# Collision records (NYC Open Data)
# ---------------------------------------------------------------------------

class CollisionRecord(BaseModel):
    crash_date: Optional[str] = None
    crash_time: Optional[str] = None
    borough: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    on_street_name: Optional[str] = None
    cross_street_name: Optional[str] = None
    number_of_persons_injured: Optional[int] = 0
    number_of_persons_killed: Optional[int] = 0
    contributing_factor_vehicle_1: Optional[str] = None
    vehicle_type_code1: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# WebSocket message types
# ---------------------------------------------------------------------------

class FeedUpdateMessage(BaseModel):
    type: str = "feed_update"
    data: FeedSnapshot


class IncidentDetectedMessage(BaseModel):
    type: str = "incident_detected"
    data: Incident


class LLMOutputMessage(BaseModel):
    type: str = "llm_output"
    data: LLMOutput


# ---------------------------------------------------------------------------
# API request models
# ---------------------------------------------------------------------------

class CitySwitchRequest(BaseModel):
    city: str


class ChatRequest(BaseModel):
    message: str
    incident_id: Optional[str] = None


class NearbyCollisionRequest(BaseModel):
    lat: float
    lng: float
    radius_deg: float = 0.005
