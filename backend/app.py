"""SENTINEL — Main FastAPI application with lifespan-managed services."""

import asyncio
import json
import logging
import time
import os
from fastapi.staticfiles import StaticFiles
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
from services.operator_queue import OperatorQueueManager
from data.signal_baselines import CITY_BASELINES
from data.default_congestion_zones import DEFAULT_CONGESTION_ZONES
from data.intersections import DEFAULT_INTERSECTIONS
from data.road_segments import DEFAULT_ROAD_SEGMENTS
from routers import incidents, feed, collisions, websocket as ws_router, chat, llm, demo, congestion, surveillance

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections with city-based rooms."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()
        self.city_rooms: dict[str, set[WebSocket]] = {}
        self.connection_city: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, city: str = "nyc"):
        await websocket.accept()
        self.active_connections.add(websocket)
        # Add to city room
        if city not in self.city_rooms:
            self.city_rooms[city] = set()
        self.city_rooms[city].add(websocket)
        self.connection_city[websocket] = city
        logger.info(f"WebSocket connected to room '{city}'. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        city = self.connection_city.pop(websocket, None)
        if city and city in self.city_rooms:
            self.city_rooms[city].discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    def switch_city(self, websocket: WebSocket, new_city: str):
        """Move a WebSocket connection from one city room to another."""
        old_city = self.connection_city.get(websocket)
        if old_city and old_city in self.city_rooms:
            self.city_rooms[old_city].discard(websocket)
        if new_city not in self.city_rooms:
            self.city_rooms[new_city] = set()
        self.city_rooms[new_city].add(websocket)
        self.connection_city[websocket] = new_city

    async def broadcast(self, message: dict):
        """Broadcast to ALL connections (for system-wide messages)."""
        payload = json.dumps(message, default=str)
        stale: list[WebSocket] = []
        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                stale.append(conn)
        for conn in stale:
            self.disconnect(conn)

    async def broadcast_to_city(self, city: str, message: dict):
        """Broadcast only to connections in a specific city room."""
        payload = json.dumps(message, default=str)
        stale: list[WebSocket] = []
        for conn in self.city_rooms.get(city, set()):
            try:
                await conn.send_text(payload)
            except Exception:
                stale.append(conn)
        for conn in stale:
            self.disconnect(conn)


# ---------------------------------------------------------------------------
# Helper: convert segment point to line geometry
# ---------------------------------------------------------------------------

def _segment_to_line_geometry(lat: float, lng: float, link_name: str, length_deg: float = 0.001):
    """
    Create a short line geometry centered on a segment point.
    Detects road direction from link_name:
      - Avenues/Broadway → N-S (offset latitude)
      - Streets → E-W (offset longitude)
    Returns [[lng1, lat1], [lng2, lat2]]
    """
    link_lower = link_name.lower() if link_name else ""
    # N-S roads: avenues, broadway
    if "ave" in link_lower or "avenue" in link_lower or "broadway" in link_lower:
        # Offset latitude for N-S direction
        return [[lng, lat - length_deg / 2], [lng, lat + length_deg / 2]]
    else:
        # E-W roads (streets, etc): offset longitude
        return [[lng - length_deg / 2, lat], [lng + length_deg / 2, lat]]


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
    routing_service = RoutingService(
        ors_api_key=settings.ors_api_key,
        mapbox_token=settings.mapbox_token,
    )
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
    operator_queue = OperatorQueueManager()
    operator_queue.db = db

    # Seed default congestion zones if collection is empty
    if db.congestion_zones is not None:
        count = await db.congestion_zones.count_documents({"source": "default"})
        if count == 0:
            docs = [{**z, "source": "default", "status": "permanent"} for z in DEFAULT_CONGESTION_ZONES]
            await db.congestion_zones.insert_many(docs)
            logger.info(f"Seeded {len(docs)} default congestion zones")

    # Seed intersections
    if db.intersections is not None:
        existing = await db.intersections.count_documents({})
        if existing == 0:
            all_intersections = DEFAULT_INTERSECTIONS.get("nyc", []) + DEFAULT_INTERSECTIONS.get("chandigarh", [])
            if all_intersections:
                await db.intersections.insert_many(all_intersections)
                logger.info(f"Seeded {len(all_intersections)} intersections")

    # Seed road segments
    if db.road_segments is not None:
        existing = await db.road_segments.count_documents({})
        if existing == 0:
            all_segments = DEFAULT_ROAD_SEGMENTS.get("nyc", []) + DEFAULT_ROAD_SEGMENTS.get("chandigarh", [])
            if all_segments:
                await db.road_segments.insert_many(all_segments)
                logger.info(f"Seeded {len(all_segments)} road segments")

    # Store on app.state for router access
    app.state.feed_simulator = feed_simulator
    app.state.incident_detector = incident_detector
    app.state.congestion_detector = congestion_detector
    app.state.collision_service = collision_service
    app.state.routing_service = routing_service
    app.state.llm_service = llm_service
    app.state.prompt_builder = prompt_builder
    app.state.ws_manager = ws_manager
    app.state.operator_queue = operator_queue
    app.state.active_city = settings.active_city

    # Reconcile queue state from DB — assigns unassigned active incidents to operators
    logger.info("Running operator queue reconciliation from DB...")
    await operator_queue.reconcile_from_db(ws_manager)

    # ---- wire callbacks ----

    frame_counter = {"count": 0}

    async def _on_frame(segments: list[dict]):
        """Forward every feed frame to detectors and broadcast."""
        # Auto-detection disabled — incidents only via /api/demo/inject-incident
        # await incident_detector.process_frame(segments)
        await congestion_detector.process_frame(segments)
        await ws_manager.broadcast_to_city(feed_simulator.active_city, {
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

    async def _recompute_other_routes(current_incident_id: str, city: str):
        """Recompute routes for all other active incidents with updated avoidance set."""
        if db.incidents is None:
            return
        try:
            all_active = await db.incidents.find(
                {"status": "active", "city": city}
            ).to_list(50)

            if len(all_active) < 2:
                return  # Only one incident, nothing to recompute

            for inc in all_active:
                inc_id = str(inc["_id"])
                if inc_id == current_incident_id:
                    continue

                # Build avoidance from ALL OTHER active incidents
                extra_avoid = []
                for other in all_active:
                    other_id = str(other["_id"])
                    if other_id == inc_id:
                        continue
                    oloc = other.get("location", {}).get("coordinates", [])
                    if len(oloc) >= 2:
                        olng, olat = oloc[0], oloc[1]
                        buf = 0.002
                        extra_avoid.append([
                            [olng - buf, olat - buf],
                            [olng + buf, olat - buf],
                            [olng + buf, olat + buf],
                            [olng - buf, olat + buf],
                            [olng - buf, olat - buf],
                        ])

                # Also add congestion zones
                if db.congestion_zones is not None:
                    try:
                        zones = await db.congestion_zones.find(
                            {"city": city, "status": {"$in": ["active", "permanent"]}}
                        ).to_list(50)
                        for zone in zones:
                            poly = zone.get("polygon")
                            if poly and len(poly) >= 4:
                                closed = poly if poly[0] == poly[-1] else poly + [poly[0]]
                                extra_avoid.append(closed)
                    except Exception:
                        pass

                inc_coords = inc.get("location", {}).get("coordinates", [0, 0])
                inc_lng, inc_lat = inc_coords[0], inc_coords[1]

                try:
                    current_segments = feed_simulator.get_current_segments()
                    new_routes = await routing_service.compute_incident_route_pair(
                        inc_lng, inc_lat,
                        city=city,
                        on_street=inc.get("on_street", ""),
                        extra_avoid_polygons=extra_avoid if extra_avoid else None,
                        severity=inc.get("severity", "moderate"),
                        feed_segments=current_segments,
                    )

                    if new_routes and new_routes.get("alternate"):
                        # Update DB
                        if db.diversion_routes is not None:
                            await db.diversion_routes.update_one(
                                {"incident_id": inc_id},
                                {"$set": {
                                    "schema_version": "v2",
                                    "blocked_route": new_routes["blocked"],
                                    "alternate_route": new_routes["alternate"],
                                    "blocked": new_routes["blocked"],
                                    "alternate": new_routes["alternate"],
                                    "origin": new_routes["origin"],
                                    "destination": new_routes["destination"],
                                    "route_meta": new_routes.get("meta", {}),
                                    "recomputed_at": datetime.now(timezone.utc).isoformat(),
                                }},
                                upsert=True,
                            )
                        # Broadcast updated routes
                        await ws_manager.broadcast_to_city(city, {
                            "type": "incident_routes",
                            "data": {
                                "version": "v2",
                                "incident_id": inc_id,
                                    "origin": new_routes["origin"],
                                    "destination": new_routes["destination"],
                                    "blocked": new_routes["blocked"],
                                    "alternate": new_routes["alternate"],
                                    "meta": new_routes.get("meta", {}),
                                },
                            })
                        logger.info(f"Recomputed routes for incident {inc_id} with {len(extra_avoid)} avoidance zones")
                except Exception as e:
                    logger.warning(f"Failed to recompute routes for {inc_id}: {e}")
        except Exception as e:
            logger.error(f"Route recomputation error: {e}")

    async def _on_incident(incident: dict):
        """Full LLM pipeline triggered when an incident is detected."""
        city = feed_simulator.active_city
        incident["city"] = city

        # Block auto-detection while this incident is active
        if incident.get("source") == "demo_injection":
            incident_detector._active_incident = incident

        try:
            # 1. Save incident to DB
            incident_id = "offline"
            if db.incidents is not None:
                result = await db.incidents.insert_one(incident)
                incident_id = str(result.inserted_id)
            logger.info(f"Incident saved: {incident_id}")

            # Store _id back so resolve callbacks can reference it
            incident["_id"] = incident_id

            # Assignment:
            # - If demo injection specifies a requesting operator, force-assign to them.
            # - Else use queue-driven assignment.
            requested_operator = (incident.get("requested_operator") or "").strip()
            if requested_operator:
                assigned_op = await operator_queue.force_assign_incident(
                    city=city,
                    incident_id=incident_id,
                    operator=requested_operator,
                    ws_manager=ws_manager,
                )
            else:
                assigned_op = await operator_queue.enqueue_incident(city, incident_id, ws_manager)
            incident["assigned_operator"] = assigned_op

            # Broadcast incident detection
            await ws_manager.broadcast_to_city(city, {
                "type": "incident_detected",
                "data": {**incident, "_id": incident_id},
            })

            # 2. Fetch nearby collisions + compute routes IN PARALLEL
            coords = incident.get("location", {}).get("coordinates", [0, 0])
            lng, lat = coords[0], coords[1]

            t0 = time.time()

            # Collect avoidance zones from ALL other active incidents + congestion zones
            extra_avoid = []
            if db.incidents is not None:
                try:
                    other_incidents = await db.incidents.find(
                        {"status": "active", "city": city}
                    ).to_list(50)
                    for other in other_incidents:
                        oid = str(other.get("_id", ""))
                        if oid == incident_id:
                            continue
                        oloc = other.get("location", {}).get("coordinates", [])
                        if len(oloc) >= 2:
                            olng, olat = oloc[0], oloc[1]
                            buf = 0.002
                            extra_avoid.append([
                                [olng - buf, olat - buf],
                                [olng + buf, olat - buf],
                                [olng + buf, olat + buf],
                                [olng - buf, olat + buf],
                                [olng - buf, olat - buf],
                            ])
                except Exception as e:
                    logger.warning(f"Failed to query other incidents for avoidance: {e}")

            if db.congestion_zones is not None:
                try:
                    active_zones = await db.congestion_zones.find(
                        {"city": city, "status": {"$in": ["active", "permanent"]}}
                    ).to_list(50)
                    for zone in active_zones:
                        poly = zone.get("polygon")
                        if poly and len(poly) >= 4:
                            closed = poly if poly[0] == poly[-1] else poly + [poly[0]]
                            extra_avoid.append(closed)
                except Exception as e:
                    logger.warning(f"Failed to query congestion zones for avoidance: {e}")

            current_segments = feed_simulator.get_current_segments()
            collision_task = collision_service.get_nearby_collisions(lat, lng, city=city)
            route_task = routing_service.compute_incident_route_pair(
                lng, lat, city=city,
                on_street=incident.get("on_street", ""),
                extra_avoid_polygons=extra_avoid if extra_avoid else None,
                severity=incident.get("severity", "moderate"),
                feed_segments=current_segments,
            )

            results = await asyncio.gather(collision_task, route_task, return_exceptions=True)

            # Unpack results safely
            collisions_data = results[0] if not isinstance(results[0], Exception) else []
            incident_routes = results[1] if not isinstance(results[1], Exception) else None

            if isinstance(results[0], Exception):
                logger.error(f"Collision lookup failed: {results[0]}")
            if isinstance(results[1], Exception):
                logger.error(f"Route computation failed: {results[1]}")

            logger.info(f"Parallel stage (collisions+routing) took {time.time() - t0:.1f}s")

            collision_context = collision_service.get_collision_context_for_llm(collisions_data)
            cctv_context = "No recent CCTV visual events."
            if db.cctv_events is not None:
                try:
                    cctv_events = await db.cctv_events.find(
                        {"city": city, "incident_id": {"$in": [incident_id, None]}},
                    ).sort("detected_at", -1).to_list(3)
                    if cctv_events:
                        cctv_context = "\n".join(
                            f"- {ev.get('event_type', 'unknown')} "
                            f"(camera={ev.get('camera_id', 'n/a')}, confidence={ev.get('confidence', 0)})"
                            for ev in cctv_events
                        )
                except Exception:
                    cctv_context = "No CCTV context available."

            # Broadcast collisions for map overlay
            if collisions_data:
                await ws_manager.broadcast_to_city(city, {
                    "type": "collisions",
                    "data": {
                        "incident_id": incident_id,
                        "collisions": collisions_data,
                    },
                })

            # 3. Use pre-computed incident routes from parallel stage
            if incident_routes is None:
                # Fallback: routes failed, use empty structure
                incident_routes = {
                    "version": "v2",
                    "origin": [lng, lat],
                    "destination": [lng, lat],
                    "blocked": {"geometry": {"type": "LineString", "coordinates": []}, "total_length_km": 0, "street_names": []},
                    "alternate": {"geometry": {"type": "LineString", "coordinates": []}, "total_length_km": 0, "estimated_extra_minutes": 0, "avg_speed_kmh": 0, "street_names": []},
                    "meta": {
                        "routing_engine": "local_astar",
                        "fallback_used": True,
                        "ors_calls": 0,
                        "astar_score": 0.0,
                    },
                }

            # 3b. Persist incident routes to DB
            if db.diversion_routes is not None:
                try:
                    await db.diversion_routes.insert_one({
                        "schema_version": "v2",
                        "city": city,
                        "incident_id": incident_id,
                        "blocked_location": {"type": "Point", "coordinates": [lng, lat]},
                        "computed_at": datetime.now(timezone.utc),
                        "origin": incident_routes["origin"],
                        "destination": incident_routes["destination"],
                        "blocked_route": incident_routes["blocked"],
                        "alternate_route": incident_routes["alternate"],
                        "blocked": incident_routes["blocked"],
                        "alternate": incident_routes["alternate"],
                        "route_meta": incident_routes.get("meta", {}),
                    })
                except Exception as e:
                    logger.warning(f"Failed to save incident routes: {e}")

            # 3c. Broadcast immediately — NO button needed, auto-apply on frontend
            await ws_manager.broadcast_to_city(city, {
                "type": "incident_routes",
                "data": {
                    "version": "v2",
                    "incident_id": incident_id,
                    "origin": incident_routes["origin"],
                    "destination": incident_routes["destination"],
                    "blocked": incident_routes["blocked"],
                    "alternate": incident_routes["alternate"],
                    "meta": incident_routes.get("meta", {}),
                },
            })
            logger.info(f"Incident routes broadcast: blocked={len(incident_routes['blocked'].get('geometry', {}).get('coordinates', []))} pts, alternate={len(incident_routes['alternate'].get('geometry', {}).get('coordinates', []))} pts")

            # Recompute routes for other active incidents with awareness of this new one
            asyncio.create_task(_recompute_other_routes(incident_id, city))

            # ═══ Create congestion zone around incident based on severity ═══
            severity = incident.get("severity", "moderate")
            severity_radius = {
                "critical": 0.006,   # ~660m radius
                "major": 0.004,      # ~440m radius
                "moderate": 0.003,   # ~330m radius
                "minor": 0.002,      # ~220m radius
            }
            radius = severity_radius.get(severity, 0.003)

            # Create segment geometry for the incident point
            on_street = incident.get("on_street", "unknown")
            incident_segment_geometry = _segment_to_line_geometry(lat, lng, on_street, length_deg=0.001)

            incident_zone = {
                "zone_id": f"incident_{incident_id}",
                "city": city,
                "name": f"Incident zone — {on_street}",
                "severity": "severe" if severity in ("critical", "major") else "moderate",
                "center": [lng, lat],
                "polygon": [
                    [lng - radius, lat - radius],
                    [lng + radius, lat - radius],
                    [lng + radius, lat + radius],
                    [lng - radius, lat + radius],
                    [lng - radius, lat - radius],
                ],
                "source": "incident",
                "status": "active",
                "incident_id": incident_id,
                "segment_geometries": [
                    {
                        "segment_id": f"incident_{incident_id}_seg",
                        "name": on_street,
                        "speed": 0,  # Blocked due to incident
                        "geometry": incident_segment_geometry,
                    }
                ],
            }

            if db.congestion_zones is not None:
                await db.congestion_zones.insert_one(incident_zone.copy())

            await ws_manager.broadcast_to_city(city, {
                "type": "congestion_alert",
                "data": incident_zone,
            })
            logger.info(f"Created congestion zone around incident: radius={radius}° severity={severity}")

            # Keep diversions for LLM context(reuse existing field name for backward compat)
            diversions = [
                {
                    "priority": 1,
                    "name": "Alternate Route",
                    "segment_names": incident_routes["alternate"].get("street_names", []),
                    "geometry": incident_routes["alternate"]["geometry"],
                    "total_length_km": incident_routes["alternate"].get("total_length_km", 0),
                    "estimated_extra_minutes": incident_routes["alternate"].get("estimated_extra_minutes", 0),
                }
            ]

            # 4. Build prompt
            baselines = CITY_BASELINES.get(city, {})
            segments = current_segments
            system_prompt, user_content = prompt_builder.build_incident_prompt(
                city=city,
                incident=incident,
                segments=segments,
                diversions=diversions,
                baselines=baselines,
                collision_context=collision_context,
                cctv_context=cctv_context,
            )

            # 5. Call LLM
            raw_output = await llm_service.generate(system_prompt, user_content)

            if raw_output:
                # 6. Parse structured output
                parsed = LLMService.parse_structured_output_v2(raw_output)

                # 7. Save LLM output to DB
                llm_doc = {
                    "version": "v2",
                    "city": city,
                    "incident_id": incident_id,
                    "signal_retiming": parsed.get("signal_retiming", {"intersections": [], "raw_text": ""}),
                    "diversions": parsed.get("diversions", {"routes": [], "raw_text": ""}),
                    "alerts": parsed.get("alerts", {}),
                    "narrative_update": parsed.get("narrative_update", ""),
                    "cctv_summary": parsed.get("cctv_summary", ""),
                    "sections_present": parsed.get("sections_present", []),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                if db.llm_outputs is not None:
                    await db.llm_outputs.insert_one(llm_doc)
                logger.info(f"LLM output saved for incident {incident_id}")

                # 8. Broadcast LLM output via WebSocket
                await ws_manager.broadcast_to_city(city, {
                    "type": "llm_output",
                    "data": {
                        **llm_doc,
                        "version": "v2",
                        "incident_id": incident_id,
                        "diversion_geometry": diversions if diversions else [],
                        "incident_routes": incident_routes,
                    },
                })
            else:
                logger.warning("LLM returned no output for incident")
                await ws_manager.broadcast_to_city(city, {
                    "type": "llm_output",
                    "data": {
                        "version": "v2",
                        "city": city,
                        "incident_id": incident_id,
                        "signal_retiming": {"intersections": [], "raw_text": ""},
                        "diversions": {"routes": [], "raw_text": ""},
                        "alerts": {"vms": "LLM analysis unavailable — all providers rate limited", "radio": "", "social_media": ""},
                        "narrative_update": "LLM analysis could not be generated — all providers are currently rate limited. The system will retry on the next incident.",
                        "cctv_summary": cctv_context,
                        "diversion_geometry": diversions if diversions else [],
                        "incident_routes": incident_routes,
                    },
                })

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Incident handler error: {e}", exc_info=True)
            with open("error_debug.txt", "w") as f:
                f.write(error_trace)

    async def _on_resolve(incident: dict):
        """Handle incident resolution."""
        incident_id = incident.get("_id", "unknown")
        city = incident.get("city", feed_simulator.active_city)
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
        await ws_manager.broadcast_to_city(city, {
            "type": "incident_resolved",
            "data": {"incident_id": incident_id, "resolved_at": incident.get("resolved_at", "")},
        })
        logger.info(f"Incident resolved broadcast: {incident_id}")

    async def _on_congestion(zone: dict):
        """Handle congestion zone detection — compute alternate routes and broadcast."""
        city = feed_simulator.active_city
        zone["city"] = city
        try:
            # Save congestion zone to DB
            if db.congestion_zones is not None:
                try:
                    zone_doc = {
                        "zone_id": zone["zone_id"],
                        "city": city,
                        "type": "congestion",
                        "status": "active",
                        "severity": zone["severity"],
                        "location": zone["location"],
                        "primary_street": zone["primary_street"],
                        "affected_segment_ids": zone.get("affected_segment_ids", []),
                        "segments": zone.get("segments", []),
                        "detected_at": zone.get("detected_at", datetime.now(timezone.utc).isoformat()),
                    }
                    await db.congestion_zones.insert_one(zone_doc)
                    logger.info(f"Congestion zone saved: {zone['zone_id']}")
                except Exception as e:
                    logger.warning(f"Failed to save congestion zone: {e}")

            # Use segment-aware routing for congestion (entry/exit from bounding box of congested segments)
            congestion_routes = await routing_service.compute_congestion_route_pair(
                zone.get("segments", []),
                city=city,
                feed_segments=feed_simulator.get_current_segments(),
            )
            alt_routes = [
                {
                    "priority": 1,
                    "name": "Congestion Alternate",
                    "geometry": congestion_routes["alternate"]["geometry"],
                    "total_length_km": congestion_routes["alternate"].get("total_length_km", 0),
                    "estimated_extra_minutes": congestion_routes["alternate"].get("estimated_extra_minutes", 0),
                }
            ]

            # Broadcast congestion alert with routes
            # Build segment geometries for road-following overlays
            segment_geometries = [
                {
                    "segment_id": seg.get("link_id", ""),
                    "name": seg.get("link_name", ""),
                    "speed": seg.get("speed", 0),
                    "geometry": _segment_to_line_geometry(
                        seg.get("lat", 0),
                        seg.get("lng", 0),
                        seg.get("link_name", ""),
                        length_deg=0.001
                    ),
                }
                for seg in zone.get("segments", [])
            ]

            await ws_manager.broadcast_to_city(city, {
                "type": "congestion_alert",
                "data": {
                    "version": "v2",
                    "zone_id": zone["zone_id"],
                    "city": city,
                    "severity": zone["severity"],
                    "primary_street": zone["primary_street"],
                    "location": zone["location"],
                    "segments": zone["segments"],
                    "segment_geometries": segment_geometries,
                    "detected_at": zone["detected_at"],
                    "alternate_routes": alt_routes,
                    "origin": congestion_routes["origin"],
                    "destination": congestion_routes["destination"],
                    "blocked_geometry": congestion_routes["blocked"]["geometry"],
                    "meta": congestion_routes.get("meta", {}),
                },
            })
            logger.info(f"Congestion alert broadcast: {zone['primary_street']} with {len(alt_routes)} routes")

        except Exception as e:
            logger.error(f"Congestion handler error: {e}", exc_info=True)

    async def _on_congestion_clear(zone: dict):
        """Handle congestion cleared — update DB and notify frontend."""
        # Update DB status
        if db.congestion_zones is not None:
            try:
                await db.congestion_zones.update_one(
                    {"zone_id": zone["zone_id"]},
                    {"$set": {"status": "cleared", "cleared_at": zone.get("cleared_at", "")}}
                )
            except Exception as e:
                logger.warning(f"Failed to update congestion zone in DB: {e}")

        await ws_manager.broadcast_to_city(feed_simulator.active_city, {
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
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
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
app.include_router(surveillance.router, prefix="/api/surveillance", tags=["surveillance"])

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    city = getattr(app.state, "active_city", "nyc")
    return {"status": "ok", "project": "SENTINEL", "city": city}
