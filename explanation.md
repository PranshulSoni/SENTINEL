# SENTINEL Explanation Guide

This file is written for interview prep. It explains what each major module does, how the system fits together, and which parts are active versus only present in the repository.

## 1. 30-Second Project Explanation

SENTINEL is a traffic incident response system with 3 runtime surfaces:

1. a FastAPI backend
2. an operator dashboard for traffic controllers
3. a citizen-facing app

The backend ingests live or cached traffic data, tracks congestion, accepts incident reports and surveillance uploads, computes blocked and safe routes, runs an LLM pipeline for operator guidance, stores operational data in MongoDB, and pushes updates to both frontends over city-scoped WebSockets.

## 2. Hard Numbers You Can Mention

- 3 runtime surfaces
- 2 supported cities: NYC and Chandigarh
- 86 code files and about 17,783 lines of application code
- 48 backend Python files
- 38 frontend files across the 2 React apps
- 10 mounted router modules
- 33 mounted HTTP/WebSocket endpoints
- 9 backend service modules
- 12 MongoDB collections
- 20 MongoDB indexes
- 3 LLM providers in fallback order
- 2 ORS containers for local routing
- 2 mapping stacks: Leaflet and Mapbox GL
- 12 named operators total, 6 per city
- 12 signal baseline records
- 20 seeded intersections
- 23 seeded road segments
- 8 seeded default congestion zones
- 5 seeded social users
- 20 predefined demo/report street locations
- 5 CCTV camera points in the operator map
- 5,000 cached NYC speed rows
- 3,000 cached Chandigarh speed rows
- 250 Chandigarh collision records
- 4 unittest files with 29 authored test cases

## 3. End-To-End Runtime Flow

### 3.1 Traffic Feed And Congestion Flow

1. `backend/services/feed_simulator.py` loads traffic data for the active city.
2. It prefers live NYC API data, then CSV cache, then synthetic demo frames.
3. `backend/app.py` pushes each frame into the active pipeline every 5 seconds by default.
4. `backend/services/congestion_detector.py` looks for sustained low-speed clusters.
5. When congestion is detected, `backend/app.py` saves the zone, computes alternate routes, and broadcasts the zone over WebSocket.
6. The operator dashboard and citizen app both update their maps from the same backend broadcast stream.

### 3.2 Incident Flow

There are 3 active incident entry paths in the current app:

1. `POST /api/demo/inject-incident`
2. `POST /api/incidents/report`
3. surveillance upload plus stream processing under `/api/surveillance/*`

All 3 eventually call the shared `_on_incident` pipeline in `backend/app.py`. That pipeline:

1. persists the incident
2. assigns or queues an operator
3. computes blocked and alternate routes
4. creates an incident-linked congestion zone
5. builds the LLM prompt from feed, baselines, collisions, routes, and CCTV context
6. stores the LLM output
7. broadcasts incident, route, and LLM updates to the correct city room

### 3.3 Frontend Flow

1. Both frontends connect to `/ws`
2. The operator dashboard subscribes with a city query param and listens for feed, incident, route, congestion, social, and police-dispatch events
3. The citizen app also listens to the same city-scoped events but presents them in a simplified mobile-style UI
4. Both frontends use Zustand stores to keep live state in sync

## 4. Complexity Hotspots

These are the biggest code hotspots in the repo and the best places to talk about engineering depth:

| File | Approx lines | Why it matters |
| --- | ---: | --- |
| `backend/services/routing_service.py` | 2,653 | Core routing logic, ORS integration, local A* fallback, geometry guards, degradation handling |
| `backend/app.py` | 1,250 | Main orchestration layer, startup lifecycle, callbacks, WebSocket manager, route recompute logic |
| `frontend/src/components/outputs/Sidebar.tsx` | 729 | Main operator workflow UI: assignment, police dispatch, LLM actions, alert publishing |
| `backend/services/feed_simulator.py` | 643 | Feed ingestion and replay logic across API, CSV, and synthetic sources |
| `user-app/src/components/outputs/Sidebar.tsx` | 560 | Citizen incident reporting UI and live incident list |

If an interviewer asks where the hardest engineering work is, `routing_service.py` is the strongest answer.

## 5. Backend Module Breakdown

### 5.1 Core Backend Files

| File | What it does | Interview talking point |
| --- | --- | --- |
| `backend/app.py` | Main FastAPI app, startup/shutdown lifecycle, service wiring, DB seeding, WebSocket manager, route recomputation, and shared incident pipeline | "This is the orchestration layer that turns separate services into one live system." |
| `backend/config.py` | Centralized environment settings for MongoDB, LLMs, ORS, Mapbox, feed interval, and server config | "I kept external integrations configurable through a single settings module." |
| `backend/db.py` | Opens MongoDB connection, exposes 12 collections, creates 20 indexes | "I used explicit collection handles and indexes instead of hidden ORM magic." |
| `backend/main_gpu.py` | YOLOv8-based surveillance processing with CUDA/OpenVINO fallback, frame skipping, vehicle tracking, and accident visualization | "This is the computer-vision path for surveillance uploads." |
| `backend/check_db.py` | Utility script to inspect active incidents and operator assignments in MongoDB | "A maintenance script for debugging live state." |
| `backend/clear_db.py` | Utility script to delete non-demo incidents from the database | "A cleanup helper for demo resets." |
| `backend/cleanup_mismatch.py` | Utility script to remove cross-city incident mismatches from MongoDB | "A data hygiene helper for city-label drift." |
| `backend/run_flake8_critical.py` | Runs flake8 for critical Python issues and saves output to a file | "A lightweight static-check helper." |

### 5.2 Mounted Router Modules

These 10 router files are actually mounted in `backend/app.py`.

| Router file | Live endpoints | What it does | Notes |
| --- | ---: | --- | --- |
| `backend/routers/incidents.py` | 9 | User incident reporting, incident list/detail, claim, resolve, dismiss, dispatch police, fetch stored routes, fetch latest LLM output | Main operational workflow router |
| `backend/routers/feed.py` | 4 | Current feed, current city, city switch, and signal baselines | Drives map context and replay switching |
| `backend/routers/collisions.py` | 2 | Nearby collision lookup and LLM-ready collision context | Uses NYC Open Data or Chandigarh JSON |
| `backend/routers/chat.py` | 3 | Copilot chat, history fetch, history clear | Stores messages in `chat_history` |
| `backend/routers/llm.py` | 1 | Manual LLM regeneration for an incident | Rebuilds output from current backend state |
| `backend/routers/congestion.py` | 4 | Active congestion, default zones, visible zones, congestion history | Supports map overlays and replay review |
| `backend/routers/social.py` | 3 | Social users, social alerts, social publish | City-scoped public alert path |
| `backend/routers/surveillance.py` | 3 | Video upload, MJPEG feed stream, feed status | Runs YOLO path and dispatches incidents |
| `backend/routers/demo.py` | 2 | Demo incident injection and demo street list | Important for live demos |
| `backend/routers/websocket.py` | 1 | WebSocket endpoint with city-room switching | Real-time backbone for both frontends |

### 5.3 Service Modules

| Service file | Status | What it does | Key numbers and details |
| --- | --- | --- | --- |
| `backend/services/feed_simulator.py` | Active | Loads traffic data and replays frames | 5-second default interval, 5,000 NYC CSV rows, 3,000 Chandigarh CSV rows, 12 replay frames from API/CSV sources, 60 synthetic demo frames |
| `backend/services/collision_service.py` | Active | Pulls nearby collisions and formats them for prompts | 30-day collision history window, default limit 500, Chandigarh fallback file has 250 records |
| `backend/services/congestion_detector.py` | Active | Detects sustained congestion clusters | 12 mph threshold, 6 frames sustained, at least 2 segments, 180-second cooldown, 4 recovery frames |
| `backend/services/incident_detector.py` | Implemented but currently disabled from feed loop | Detects incidents from sudden speed drops | 5-frame baseline window, 50 percent drop threshold, 3 adjacent segments, 12-frame resolve cooldown, 120-second incident cooldown |
| `backend/services/routing_service.py` | Active | Computes blocked and alternate routes | ORS primary, local ORS per city, local A* fallback, locality guards, detour guards, cache, degradation metadata |
| `backend/services/llm_service.py` | Active | Runs LLM calls and parses 5-section responses | 3 providers, structured parser for signal retiming, diversions, alerts, narrative update, and CCTV summary |
| `backend/services/prompt_builder.py` | Active | Builds system prompts and chat prompts | Enforces exact 5-section incident output format |
| `backend/services/operator_queue.py` | Active | Round-robin operator assignment and startup reconciliation | 12 named operators total, 6 per city, ready/blocked/wait queues |
| `backend/services/roadblock_vision_service.py` | Implemented, not wired into mounted incident report flow | Strict JSON roadblock scoring using Hugging Face or Ollama vision backends | Good prototype module, but not part of the current live request path |

### 5.4 Data Modules

| File | What it contains | Actual counts |
| --- | --- | ---: |
| `backend/data/signal_baselines.py` | Signal timing baselines and city centers | 12 baseline records total |
| `backend/data/intersections.py` | Key intersections for routing and operations context | 20 intersections total |
| `backend/data/road_segments.py` | Core road graph segments for local routing fallback | 23 road segments total |
| `backend/data/default_congestion_zones.py` | Known permanent congestion hotspots | 8 zones total |
| `backend/data/social_users.py` | Seed social recipients for alerts | 5 users total |
| `backend/data/nyc_link_speed.csv` | Cached NYC link-speed feed | 5,000 rows |
| `backend/data/chandigarh_link_speed.csv` | Cached Chandigarh link-speed feed | 3,000 rows |
| `backend/data/chandigarh_collisions.json` | Local Chandigarh collision dataset | 250 records |

### 5.5 Pydantic Models

`backend/models/schemas.py` is the main schema file for:

- GeoJSON points and lines
- traffic segments and feed snapshots
- incidents
- LLM outputs
- chat messages and sessions
- signal baselines
- diversion routes
- CCTV events
- collision records
- API request models

Interview answer:

"I used Pydantic models to keep backend input/output contracts explicit across incidents, routes, LLM results, chat, and geospatial objects."

## 6. Backend Features That Exist But Are Not Fully Live

This section matters because it protects you from overclaiming in interviews.

### 6.1 `incident_narrative/`

This folder is a real subsystem, but it is not mounted into `backend/app.py`.

| File | What it does |
| --- | --- |
| `backend/incident_narrative/models.py` | Pydantic models for a running narrative, events, and query payloads |
| `backend/incident_narrative/narrative_engine.py` | In-memory narrative store and prompt serializer |
| `backend/incident_narrative/gemini_query.py` | Gemini-based narrative QA, including optional audio input |
| `backend/incident_narrative/seed_data.py` | Demo incident narrative with 10 chronological events |
| `backend/incident_narrative/routes.py` | 5 API endpoints for narrative read/query/update |

Safe way to describe it:

"There is an implemented narrative-query submodule in the repo, but it is not mounted into the main FastAPI app yet."

### 6.2 Voice Query Support

Both React apps include microphone capture UI in their chat panels. However:

- the mounted `/api/chat` route accepts only text-oriented `ChatRequest`
- audio fields are only supported inside the unmounted `incident_narrative` submodule

Safe way to describe it:

"Voice capture UI exists, but full audio query processing is only implemented in an unmounted narrative prototype."

### 6.3 Feed-Based Incident Detection

`IncidentDetector` is implemented, but `backend/app.py` has the live frame callback commented so feed frames currently do not auto-create incidents.

Current live incident sources are:

1. demo injection
2. citizen reports
3. surveillance uploads

## 7. Operator Dashboard Module Breakdown

The operator dashboard is the desktop-style control console in `frontend/`.

| File | What it does | Interview talking point |
| --- | --- | --- |
| `frontend/src/App.tsx` | Composes the 3-pane app shell and activates the WebSocket hook | "Simple composition entrypoint." |
| `frontend/src/components/layout/AppShell.tsx` | 3-column operator layout, header, city switcher, live status, theme toggle, operator dropdown | "This file defines the command-center shell." |
| `frontend/src/components/outputs/Sidebar.tsx` | Main operator workflow panel: incident view, claim/resolve/dismiss, police dispatch, LLM sections, social publish, logs, active incidents | "This is the operational control surface." |
| `frontend/src/components/map/TrafficMap.tsx` | Leaflet map with incidents, congestion overlays, blocked routes, safe routes, and camera points | "This is the live geospatial command view." |
| `frontend/src/components/layout/ChatPanel.tsx` | Copilot chat UI with history, streaming state, and microphone button | "This is the operator-facing AI conversation panel." |
| `frontend/src/components/layout/OperatorDropdown.tsx` | Session and operator switching across the 2 city rosters | "Supports session reassignment and operator context." |
| `frontend/src/components/map/CameraPopup.tsx` | CCTV upload popup and MJPEG surveillance feed viewer | "Connects the map UI to the surveillance pipeline." |
| `frontend/src/hooks/useWebSocket.ts` | WebSocket subscription and state updates for live messages | "Real-time state bridge between backend events and UI stores." |
| `frontend/src/hooks/useTheme.ts` | Theme persistence and CSS variable switching | "Simple but practical UX state module." |
| `frontend/src/store/index.ts` | Zustand stores for feed, incidents, chat, routes, congestion, and operator session | "Central live state model for the operator app." |
| `frontend/src/services/api.ts` | HTTP client helpers for incident, feed, route, chat, demo, social, and congestion APIs | "Thin API layer so components stay declarative." |
| `frontend/src/types/index.ts` | Shared TypeScript interfaces for incidents, routes, chat, and LLM output | "Keeps the frontend contract typed." |
| `frontend/src/components/demo/DemoControls.tsx` | Demo injector UI for synthetic incidents | Present in repo, but not mounted in the current app shell |

## 8. Citizen App Module Breakdown

The citizen app is the mobile-style client in `user-app/`.

| File | What it does | Interview talking point |
| --- | --- | --- |
| `user-app/src/App.tsx` | Wires together the citizen app shell, map, chat, sidebar, and social panel | "Main citizen-app composition layer." |
| `user-app/src/components/layout/AppShell.tsx` | 4-tab mobile shell: Home, Map, Copilot, Social | "This app is intentionally mobile-first and task-focused." |
| `user-app/src/components/outputs/Sidebar.tsx` | Incident reporting modal, compulsory photo upload, street search, live incident list | "This is the citizen incident-intake surface." |
| `user-app/src/components/map/TrafficMap.tsx` | Mapbox GL incident map with blocked/safe route overlays and congestion lines | "This is the simplified public map experience." |
| `user-app/src/components/social/SocialPanel.tsx` | City-specific social alert inbox and user-session switching | "Shows public-facing dissemination after the operator publishes alerts." |
| `user-app/src/components/layout/ChatPanel.tsx` | Mobile copilot chat UI | "Reuses the copilot concept in a simpler form." |
| `user-app/src/hooks/useWebSocket.ts` | Live event subscription for the citizen UI | "Same real-time model, simpler state updates." |
| `user-app/src/store/index.ts` | Zustand state for feed, incidents, chat, and congestion | "State isolation for the second frontend." |
| `user-app/src/services/api.ts` | HTTP client for report submission, incidents, routes, social alerts, and chat | "Clean client-side interface to the same backend." |
| `user-app/src/utils/city.ts` | City normalization and coordinate/street heuristics | "Prevents cross-city leaks in UI state." |
| `user-app/src/types/index.ts` | Citizen-side TypeScript interfaces | "Typed API surface for the second client." |

### Citizen App Features Worth Mentioning

- 4-tab navigation model
- compulsory photo attachment in the incident report modal
- predefined searchable street lists for both cities
- city-specific social alert inbox
- live incident and safe-route display

## 9. Routing Infrastructure

`routing/docker-compose.yml` defines 2 self-hosted ORS instances:

1. Chandigarh on port `8081`
2. NYC on port `8082`

Why this matters:

- routing stays local for demos and resilience
- the backend can still fall back to remote ORS if local routing is unavailable
- `routing_service.py` also includes a local graph-based A* fallback so the system can degrade gracefully instead of dropping route guidance completely

Interview answer:

"I designed routing with multiple layers of fallback so the UI still has route behavior even if the primary routing engine is unavailable."

## 10. Frontend And Product Design Decisions

### Why 2 separate frontends?

- The operator dashboard is dense, workflow-heavy, and optimized for a control-room view
- The citizen app is simplified, mobile-first, and focused on reporting and awareness

### Why city-scoped WebSockets?

- It prevents NYC events from leaking into Chandigarh sessions and vice versa
- It reduces frontend filtering complexity
- It matches the way the operator queue is partitioned per city

### Why both Leaflet and Mapbox GL?

- The operator console benefits from a flexible overlay-driven control map, which is easy to build with Leaflet
- The citizen app uses a more consumer-oriented map presentation with Mapbox GL

## 11. Testing Status

### What exists in the repo

| Test file | Focus | Test cases |
| --- | --- | ---: |
| `backend/tests/test_routing_v2.py` | Routing fallback logic and geometry guards | 16 |
| `backend/tests/test_roadblock_vision_service.py` | Vision JSON parsing and provider normalization | 8 |
| `backend/tests/test_llm_parse_v2.py` | LLM 5-section response parsing | 3 |
| `backend/tests/test_incident_report_vision_gate.py` | Vision-gated incident report path | 2 |

Total authored cases: 29

### What I observed during verification

- Running unittest discovery in this workspace hit import-time Python `asyncio` issues on Windows for 3 test modules
- 8 roadblock-vision tests still executed and passed
- `test_incident_report_vision_gate.py` appears to target a vision-gated report flow that is not present in the currently mounted `backend/routers/incidents.py`

Safe interview answer:

"The repo includes unit tests around routing, parsing, and vision helpers, but I would not claim full green CI from this local snapshot without rerunning in a clean Python environment."

## 12. Strong Interview Answers To Common Questions

### "What was the hardest part?"

"The routing layer. I had to combine ORS, local ORS, and local graph fallback logic while also preventing bad alternates like city-spanning detours or disappearing routes."

### "How did you handle real-time updates?"

"I used city-scoped WebSocket rooms. The backend broadcasts feed, incident, route, congestion, and alert events, and both frontends keep synchronized state through Zustand stores."

### "How did you keep the AI grounded?"

"The LLM prompt is not free-form. It is assembled from live feed data, collision history, signal baselines, computed diversions, and CCTV context, and the output parser expects 5 specific sections."

### "How did you make the system resilient?"

"I used multiple fallbacks: live API to CSV to synthetic data for feeds, ORS to local ORS to local A* for routing, and a 3-provider fallback chain for LLM generation."

### "What should I not overclaim?"

"I would not say the system currently does fully live feed-triggered incident detection, full production voice query handling, or fully mounted narrative QA, because those pieces are only partially wired in the current repo."

## 13. Short Version To Memorize

If you need a compact answer, use this:

"SENTINEL is a 3-surface traffic incident response platform built with FastAPI, React, TypeScript, MongoDB, WebSockets, ORS routing, and LLM fallback. It supports 2 cities, exposes 33 live API/WebSocket endpoints, uses 12 collections with 20 indexes, computes safe routes with ORS plus local fallback, and synchronizes an operator dashboard and citizen app in real time." 
