"""SENTINEL — Main FastAPI application with lifespan-managed services."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db import connect_db, close_db
import db
from services.feed_simulator import FeedSimulator
from services.incident_detector import IncidentDetector
from services.congestion_detector import CongestionDetector
from services.collision_service import CollisionService
from services.routing_service import RoutingService
from services.llm_service import LLMService
from services.prompt_builder import PromptBuilder
from data.signal_baselines import CITY_BASELINES, CITY_CENTERS
from routers import incidents, feed, collisions, websocket as ws_router, chat, llm, demo, congestion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        payload = json.dumps(message, default=str)
        stale: list[WebSocket] = []
        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                stale.append(conn)
        for conn in stale:
            self.active_connections.discard(conn)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # ---- startup ----
    await connect_db()

    # Instantiate services
    feed_simulator = FeedSimulator(data_dir="data", app_token=settings.nyc_app_token)
    incident_detector = IncidentDetector()
    congestion_detector = CongestionDetector()
    collision_service = CollisionService(app_token=settings.nyc_app_token)
    routing_service = RoutingService(api_key=settings.ors_api_key)
    llm_service = LLMService(
        provider=settings.llm_provider,
        model=settings.llm_model,
        groq_model=settings.groq_model,
        groq_key=settings.groq_api_key,
        gemini_key=settings.gemini_api_key,
        openrouter_key=settings.openrouter_api_key,
    )
    prompt_builder = PromptBuilder()
    ws_manager = ConnectionManager()

    # Store on app.state for router access
    app.state.feed_simulator = feed_simulator
    app.state.incident_detector = incident_detector
    app.state.congestion_detector = congestion_detector
    app.state.collision_service = collision_service
    app.state.routing_service = routing_service
    app.state.llm_service = llm_service
    app.state.prompt_builder = prompt_builder
    app.state.ws_manager = ws_manager
    app.state.active_city = settings.active_city

    # ---- wire callbacks ----

    frame_counter = {"count": 0}

    async def _on_frame(segments: list[dict]):
        """Forward every feed frame to the incident detector and broadcast."""
        await incident_detector.process_frame(segments)
        await congestion_detector.process_frame(segments)
        await ws_manager.broadcast({
            "type": "feed_update",
            "data": {
                "city": feed_simulator.active_city,
                "snapshot_time": datetime.now(timezone.utc).isoformat(),
                "segments": segments,
            },
        })

        # Persist every 6th frame to DB
        frame_counter["count"] += 1
        if frame_counter["count"] % 6 == 0 and db.feed_snapshots is not None:
            try:
                await db.feed_snapshots.insert_one({
                    "city": feed_simulator.active_city,
                    "snapshot_time": datetime.now(timezone.utc),
                    "segments": segments,
                })
            except Exception as e:
                logger.warning(f"Failed to save feed snapshot: {e}")

    async def _on_incident(incident: dict):
        """Full LLM pipeline triggered when an incident is detected."""
        city = feed_simulator.active_city
        incident["city"] = city
        try:
            # 1. Save incident to DB
            incident_id = "offline"
            if db.incidents is not None:
                result = await db.incidents.insert_one(incident)
                incident_id = str(result.inserted_id)
            logger.info(f"Incident saved: {incident_id}")

            # Store _id back so resolve callbacks can reference it
            incident["_id"] = incident_id

            # Broadcast incident detection
            await ws_manager.broadcast({
                "type": "incident_detected",
                "data": {**incident, "_id": incident_id},
            })

            # 2. Fetch nearby collisions
            coords = incident.get("location", {}).get("coordinates", [0, 0])
            lng, lat = coords[0], coords[1]
            collisions_data = await collision_service.get_nearby_collisions(lat, lng)
            collision_context = collision_service.get_collision_context_for_llm(collisions_data)

            # Broadcast collisions for map overlay
            if collisions_data:
                await ws_manager.broadcast({
                    "type": "collisions",
                    "data": {
                        "incident_id": incident_id,
                        "collisions": collisions_data,
                    },
                })

            # 3. Compute diversion routes
            diversions = await routing_service.compute_diversions_for_incident(
                (lng, lat), city=city
            )

            # 3b. Persist diversion routes to DB
            if diversions and db.diversion_routes is not None:
                try:
                    await db.diversion_routes.insert_one({
                        "city": city,
                        "incident_id": incident_id,
                        "blocked_location": {"type": "Point", "coordinates": [lng, lat]},
                        "computed_at": datetime.now(timezone.utc),
                        "routes": diversions,
                    })
                except Exception as e:
                    logger.warning(f"Failed to save diversion routes: {e}")

            # 3c. Broadcast diversion geometry for map overlay
            if diversions:
                await ws_manager.broadcast({
                    "type": "diversion_routes",
                    "data": {
                        "incident_id": incident_id,
                        "routes": diversions,
                    },
                })

            # 4. Build prompt
            baselines = CITY_BASELINES.get(city, {})
            segments = feed_simulator.get_current_segments()
            system_prompt, user_content = prompt_builder.build_incident_prompt(
                city=city,
                incident=incident,
                segments=segments,
                diversions=diversions,
                baselines=baselines,
                collision_context=collision_context,
            )

            # 5. Call LLM
            raw_output = await llm_service.generate(system_prompt, user_content)

            if raw_output:
                # 6. Parse structured output
                parsed = LLMService.parse_structured_output(raw_output)

                # 7. Save LLM output to DB
                llm_doc = {
                    "incident_id": incident_id,
                    "signal_retiming": parsed.get("signal_retiming", {"intersections": [], "raw_text": ""}),
                    "diversions": parsed.get("diversions", {"routes": [], "raw_text": ""}),
                    "alerts": parsed.get("alerts", {}),
                    "narrative_update": parsed.get("narrative_update", ""),
                    "cctv_summary": parsed.get("cctv_summary", ""),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                if db.llm_outputs is not None:
                    await db.llm_outputs.insert_one(llm_doc)
                logger.info(f"LLM output saved for incident {incident_id}")

                # 8. Broadcast LLM output via WebSocket
                await ws_manager.broadcast({
                    "type": "llm_output",
                    "data": {
                        **llm_doc,
                        "incident_id": incident_id,
                        "diversion_geometry": diversions if diversions else [],
                    },
                })
            else:
                logger.warning("LLM returned no output for incident")
                await ws_manager.broadcast({
                    "type": "llm_output",
                    "data": {
                        "incident_id": incident_id,
                        "signal_retiming": {"intersections": [], "raw_text": ""},
                        "diversions": {"routes": [], "raw_text": ""},
                        "alerts": {"vms": "LLM analysis unavailable — all providers rate limited", "radio": "", "social_media": ""},
                        "narrative_update": "LLM analysis could not be generated — all providers are currently rate limited. The system will retry on the next incident.",
                        "diversion_geometry": diversions if diversions else [],
                    },
                })

        except Exception as e:
            logger.error(f"Incident handler error: {e}", exc_info=True)

    async def _on_resolve(incident: dict):
        """Handle incident resolution."""
        incident_id = incident.get("_id", "unknown")
        # Update DB
        if db.incidents is not None and incident_id != "unknown":
            try:
                from bson import ObjectId
                await db.incidents.update_one(
                    {"_id": ObjectId(incident_id)},
                    {"$set": {"status": "resolved", "resolved_at": incident.get("resolved_at")}},
                )
            except Exception:
                pass
        # Broadcast
        await ws_manager.broadcast({
            "type": "incident_resolved",
            "data": {"incident_id": incident_id, "resolved_at": incident.get("resolved_at", "")},
        })
        logger.info(f"Incident resolved broadcast: {incident_id}")

    async def _on_congestion(zone: dict):
        """Handle congestion zone detection — compute alternate routes and broadcast."""
        city = feed_simulator.active_city
        zone["city"] = city
        try:
            # Get congestion location
            coords = zone.get("location", {}).get("coordinates", [0, 0])
            lng, lat = coords[0], coords[1]
            
            # Compute alternate routes around congested area
            alt_routes = await routing_service.compute_diversions_for_incident(
                (lng, lat), city=city
            )
            
            # Broadcast congestion alert with routes
            await ws_manager.broadcast({
                "type": "congestion_alert",
                "data": {
                    "zone_id": zone["zone_id"],
                    "city": city,
                    "severity": zone["severity"],
                    "primary_street": zone["primary_street"],
                    "location": zone["location"],
                    "segments": zone["segments"],
                    "detected_at": zone["detected_at"],
                    "alternate_routes": alt_routes if alt_routes else [],
                },
            })
            logger.info(f"Congestion alert broadcast: {zone['primary_street']} with {len(alt_routes)} routes")
            
        except Exception as e:
            logger.error(f"Congestion handler error: {e}", exc_info=True)

    async def _on_congestion_clear(zone: dict):
        """Handle congestion cleared — notify frontend to remove overlay."""
        await ws_manager.broadcast({
            "type": "congestion_cleared",
            "data": {
                "zone_id": zone["zone_id"],
                "cleared_at": zone.get("cleared_at", ""),
            },
        })
        logger.info(f"Congestion cleared broadcast: {zone.get('primary_street', '')}")

    feed_simulator.on_frame(_on_frame)
    incident_detector.on_incident(_on_incident)
    incident_detector.on_resolve(_on_resolve)
    feed_simulator.on_loop_end(incident_detector.reset)
    congestion_detector.on_congestion(_on_congestion)
    congestion_detector.on_clear(_on_congestion_clear)
    feed_simulator.on_loop_end(congestion_detector.reset)

    # Expose pipeline for demo injection endpoint
    app.state.on_incident = _on_incident

    # Load city data and start feed
    await feed_simulator.load_city(settings.active_city)
    await feed_simulator.start(interval=settings.feed_interval_seconds)

    logger.info(f"SENTINEL started — city={settings.active_city}")

    yield

    # ---- shutdown ----
    await feed_simulator.stop()
    await close_db()
    logger.info("SENTINEL shut down")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SENTINEL",
    description="Traffic Incident Co-Pilot API",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(feed.router, prefix="/api/feed", tags=["feed"])
app.include_router(collisions.router, prefix="/api/collisions", tags=["collisions"])
app.include_router(ws_router.router, prefix="/ws", tags=["websocket"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(llm.router, prefix="/api/llm", tags=["llm"])
app.include_router(demo.router, prefix="/api/demo", tags=["demo"])
app.include_router(congestion.router, prefix="/api/congestion", tags=["congestion"])


@app.get("/")
async def root():
    city = getattr(app.state, "active_city", "nyc")
    return {"status": "ok", "project": "SENTINEL", "city": city}
