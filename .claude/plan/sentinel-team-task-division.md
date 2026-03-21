# SENTINEL — Team Task Division Plan (v2)

## Project: LLM Co-Pilot for Traffic Incident Command (Smart Transport PS3)

### Overview

The system is divided into 4 major work streams assigned to 4 team members.  
- **Members 1–3** handle the core technical pillars (Backend, Frontend, CCTV/YOLO).  
- **Member 4** handles the Chatbot, Data Preparation, and lighter integration tasks.

> **v2 Changes (from Report v4):**
> - ❌ REMOVED: 511NY REST API & TomTom Traffic Incidents API — no longer used
> - ✅ ADDED: NYPD Motor Vehicle Collisions dataset (`h9gi-nx95`) — replaces 511NY/TomTom as crash/incident source
> - ✅ ENHANCED: NYC DOT Traffic Speeds — now includes SODA API pagination (`$limit`/`$offset`), 1,000-row limit fix, paginated Python fetch
> - ✅ UPDATED: Chandigarh synthetic incidents now mirror NYPD collision schema (not TomTom)
> - ✅ SIMPLIFIED: One NYC Open Data app token covers both DOT Speed + NYPD Collisions endpoints
> - 🔄 Frontend (Member 2) & Chatbot (Member 4 chat tasks) — **NO CHANGES**

---

## 👤 MEMBER 1 — Backend Core (Python / FastAPI / LLM)

**Role:** Backend Architect & API Lead  
**Complexity:** 🔴 High  
**Tech:** Python, FastAPI, MongoDB (Motor), Groq API, OpenRouteService API, NYC Open Data SODA API, pandas, threading

### Tasks

| # | Task | Description |
|---|------|-------------|
| 1.1 | **FastAPI Server Setup** | Create the FastAPI project structure (`backend/`), configure CORS, environment variables (`.env`), and the main `app.py` entry point |
| 1.2 | **MongoDB Atlas Connection** | Set up `db.py` with `motor.motor_asyncio.AsyncIOMotorClient`, define all 7 collections (`incidents`, `feed_snapshots`, `llm_outputs`, `chat_history`, `signal_baselines`, `diversion_routes`, `cctv_events`), create indexes (2dsphere, TTL, compound) |
| 1.3 | **Feed Simulator Engine** | Build the pandas + threading feed simulator that replays NYC CSV / Chandigarh CSV at 5-second intervals, emitting `List[{link_id, link_name, speed, lat, lng}]` per tick. **Use `$limit=50000&$offset=0` pagination for SODA API downloads; handle the 1,000-row default limit** |
| 1.4 | **Incident Detection Algorithm** | Implement rolling 5-frame baseline per segment; flag incident when speed drops > 40% on 2+ adjacent segments; write to `incidents` collection |
| 1.5 | **NYPD Collision Data Integration** | **(NEW)** Integrate NYPD Motor Vehicle Collisions API (`h9gi-nx95`). Query recent crashes by bounding box coordinates, match to OSM road segments, use as ground-truth incident trigger. Inject historical collision frequency per intersection into LLM context ("this location has had 8 crashes in 30 days"). Python paginated fetch with `$$app_token` |
| 1.6 | **WebSocket Server** | FastAPI WebSocket endpoint broadcasting 3 event types: `feed_update`, `incident_detected`, `llm_output` — each on the 5s tick cycle |
| 1.7 | **OpenRouteService Integration** | ORS API calls (`POST /v2/directions/driving-car/geojson`); compute diversion routes and store in `diversion_routes` collection |
| 1.8 | **Structured Prompt Builder** | Build the prompt assembler that injects: affected segments, intersection names, diversion candidates, signal baselines, **NYPD collision history**, and CCTV context into the 5-section LLM prompt template |
| 1.9 | **LLM Integration (Groq)** | Integrate Groq API (`llama-3.3-70b-versatile`), parse response into the 5 structured sections (`SIGNAL_RETIMING`, `DIVERSIONS`, `ALERTS`, `NARRATIVE_UPDATE`, `CCTV_SUMMARY`), store in `llm_outputs` |
| 1.10 | **Fallback LLM Providers** | Wire up Gemini Flash and OpenRouter as fallback providers with a one-line switch |
| 1.11 | **REST API Endpoints** | Create REST endpoints: `GET /incidents`, `GET /feed/current`, `POST /city/switch`, `GET /diversions/{incident_id}`, **`GET /collisions/nearby`** |
| 1.12 | **Signal Baselines Seeding** | Pre-populate `signal_baselines` collection on startup for both NYC and Chandigarh intersections |

### Deliverables
- Working FastAPI server with WebSocket + REST
- Feed simulator replaying both city CSVs with proper SODA API pagination
- **NYPD Collision data integration** — bounding box queries, segment matching, LLM context enrichment
- Incident detection → LLM pipeline → structured output → WebSocket broadcast
- MongoDB collections populated and indexed

---

## 👤 MEMBER 2 — Frontend (React + TypeScript + Leaflet Map)

**Role:** Frontend Developer & UI Lead  
**Complexity:** 🔴 High  
**Tech:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Leaflet.js, react-leaflet, Zustand

### Tasks

| # | Task | Description |
|---|------|-------------|
| 2.1 | **Project Scaffolding** | `npm create vite@latest frontend -- --template react-ts`, install all dependencies (react-leaflet, zustand, tailwind, shadcn/ui, lucide-react, radix-ui) |
| 2.2 | **Three-Panel Layout** | Build `AppShell.tsx` — left sidebar (LLM output cards), center (Leaflet map), right panel (chat interface). Responsive, dark-mode dashboard aesthetic |
| 2.3 | **Leaflet Map — `TrafficMap.tsx`** | Interactive map centred on selected city. Subscribes to `feedStore` for real-time segment updates |
| 2.4 | **Speed Layer — `SpeedLayer.tsx`** | Polylines coloured by speed (green > 25mph, yellow 15-25, red < 15, black = blocked). Re-renders only changed segments |
| 2.5 | **Incident Marker — `IncidentMarker.tsx`** | Pulsing red marker on crash coordinates when incident detected |
| 2.6 | **Diversion Overlay — `DiversionOverlay.tsx`** | Blue polyline drawn from GeoJSON geometry on A* route activation |
| 2.7 | **Sidebar Output Cards** | Build `SignalCard.tsx`, `DiversionCard.tsx`, `AlertDraftCard.tsx` — collapsible cards that independently update from Zustand slices |
| 2.8 | **Zustand State Stores** | Create `incidentStore.ts` (incident state + LLM outputs), `feedStore.ts` (live speed data), `chatStore.ts` (chat history) |
| 2.9 | **WebSocket Hook — `useWebSocket.ts`** | WebSocket connection to FastAPI with auto-reconnect (3s backoff). Routes messages to correct Zustand store based on `type` field |
| 2.10 | **City Selector — `useCitySelector.ts`** | Toggle hook: NYC ↔ Chandigarh. On switch: reset all stores, tell backend to swap feed, re-centre map |
| 2.11 | **CCTV UI Components** | Build `CCTVEventCard.tsx` (YOLO detection results), `DetectionBadge.tsx` (CONFIRMED / INJURY / AMBULANCE overlays), `CameraFeed.tsx` (simulated frame thumbnail) |
| 2.12 | **Hospital Alert Modal — `HospitalAlertModal.tsx`** | Pop-up modal when injury detected. Shows hospital name, route, injured count. One-click confirm button for dispatch |
| 2.13 | **Minutes Saved Panel** | Static comparison table (manual baseline vs AI co-pilot) displayed in sidebar footer |
| 2.14 | **TypeScript Interfaces** | Define all types in `types/` — `incident.ts`, `feed.ts`, `llm.ts`, `cctv.ts` |
| 2.15 | **API Client — `client.ts`** | Typed REST API calls to FastAPI backend using fetch |

### Deliverables
- Fully working React dashboard with 3-panel layout
- Real-time map updates via WebSocket
- All LLM output cards rendering live data
- City toggle working end-to-end
- CCTV detection badges + hospital alert modal

---

## 👤 MEMBER 3 — CCTV + YOLO Visual Intelligence Pipeline

**Role:** Computer Vision & AI Pipeline Lead  
**Complexity:** 🔴 High  
**Tech:** YOLOv8 (Ultralytics), OpenCV, Python, MongoDB, FastAPI integration

### Tasks

| # | Task | Description |
|---|------|-------------|
| 3.1 | **YOLOv8 Setup** | Install Ultralytics + OpenCV. Load pre-trained YOLOv8 model. Verify detection on sample traffic images |
| 3.2 | **CCTV Frame Simulator** | For hackathon demo: simulate camera feeds using annotated traffic images/frames. Map camera IDs to locations (`cam_014` → coordinates) |
| 3.3 | **Feature 1 — Incident Confirmation** | When speed-drop incident flagged, route nearest camera frames to YOLO. Detect stopped vehicles, debris, people on carriageway. Return `incident_confirmed` or `incident_unconfirmed`. **Cross-reference with NYPD collision records at that coordinate to enrich officer alert** |
| 3.4 | **Feature 2 — Multi-Incident Prioritization** | When 2+ incidents active, score each visually: stationary vehicle count, injured persons, emergency vehicle proximity, lane obstruction severity. Generate priority ranking (0–100 scale) |
| 3.5 | **Feature 3 — Anomaly Detection** | Continuous detection even without feed-triggered incident: vehicle stopped mid-road, abnormal speed patterns, road obstructions, smoke/fire. Raise alerts independently |
| 3.6 | **Feature 4 — Ambulance Detection + Green Corridor** | Detect ambulance class in frames. Identify location + direction from camera position. Trigger green-corridor signal re-timing suggestions via ORS fastest hospital route |
| 3.7 | **Feature 5 — Injury Detection + Hospital Alert** | Detect persons in non-standing positions (lying on road, slumped). Flag as injury event. Find nearest hospital via OSM/GeoJSON. Generate hospital alert message for officer confirmation |
| 3.8 | **Feature 6 — CCTV Context for LLM** | Store all YOLO events as structured data in `cctv_events` collection. Ensure data format is ready for injection into LLM prompt context (event_type, detection counts, confidence, injury flags) |
| 3.9 | **Event Classification Engine** | Classify each detection into: `incident_confirmed`, `incident_unconfirmed`, `injury_detected`, `ambulance_detected`, `anomaly_stopped_vehicle`, `anomaly_speed`, `anomaly_obstruction` |
| 3.10 | **FastAPI Integration** | Create CCTV-related endpoints. Wire YOLO pipeline to run when incident detected (triggered by Member 1's incident detection). WebSocket events for CCTV updates |
| 3.11 | **Demo Frame Preparation** | Curate/prepare annotated frames for each demo scenario (NYC crash with injuries, Chandigarh breakdown with ambulance) so YOLO produces convincing results during live demo |

### Deliverables
- Working YOLOv8 pipeline processing simulated camera frames
- All 6 CCTV features functional (confirmation, prioritization, anomaly, ambulance, injury, chat context)
- `cctv_events` collection properly populated
- Demo frames curated for both cities

---

## 👤 MEMBER 4 — Chatbot + Data Preparation + Integration (Lighter Tasks)

**Role:** Chatbot Developer & Data/Integration Support  
**Complexity:** 🟡 Medium  
**Tech:** React (ChatPanel), Python (FastAPI chat endpoint), MongoDB, pandas, OSMnx (data gen only)

### Tasks

| # | Task | Description |
|---|------|-------------|
| 4.1 | **Chat Panel UI — `ChatPanel.tsx`** | Right-panel chat interface with controlled input field. Renders messages progressively (officer messages + AI responses). Scrollable message history with timestamps |
| 4.2 | **Chat API Endpoint — `POST /chat`** | FastAPI endpoint that receives officer query, fetches chat history + latest `cctv_events` from MongoDB, appends user message, calls Groq LLM with full conversation context, returns response via SSE streaming |
| 4.3 | **Chat History Persistence** | Store multi-turn conversation in `chat_history` collection. Fetch full document per incident session. Support at least 10 turns |
| 4.4 | **Chat Context Assembly** | Build the conversational prompt: inject system prompt + feed state + CCTV context + full chat history before each LLM call |
| 4.5 | **Chandigarh Synthetic Data Generation** | Run the synthetic data generation script: download Chandigarh OSM graph via OSMnx, generate speed CSV mirroring NYC schema, inject demo incident at Madhya Marg & Sector 22. **Generate synthetic collision records using NYPD Motor Vehicle Collisions schema (`h9gi-nx95` field structure)** |
| 4.6 | **NYC Data Download & Prep** | Download NYC DOT Link Speed CSV **using `$limit=50000` + `$$app_token` to bypass 1,000-row default**. **Also download NYPD Motor Vehicle Collisions data (`h9gi-nx95`) for W 34th St area using bounding box query**. Identify a real high-injury crash timestamp, trim both CSVs to the relevant time window for demo replay |
| 4.7 | **Signal Baselines Dicts** | Create static Python dicts for both cities (`NYC_SIGNAL_BASELINES`, `CHD_SIGNAL_BASELINES`) with intersection names and phase durations |
| 4.8 | **Alert Draft Templates** | Ensure VMS, Radio, and Social Media alert formats are properly templated and rendered in `AlertDraftCard` on the frontend |
| 4.9 | **API Key Setup Guide** | Create a setup guide / `.env.example` for: Groq, OpenRouteService, MongoDB Atlas URI, **NYC Open Data app token (one token covers both DOT Speed + NYPD Collisions endpoints)**. ~~511NY and TomTom keys no longer needed~~ |
| 4.10 | **README & Documentation** | Write the project README with setup instructions, architecture overview, demo run steps, and API key registration links |
| 4.11 | **Demo Script Preparation** | Prepare the live demo walkthrough script (Section 13.3 from report) — what to click, what to say, judge Q&A talking points |
| 4.12 | **Environment & DevOps** | Set up `.env` files, `requirements.txt` (backend), `package.json` verification (frontend), and a single startup script (`start.sh` / `start.bat`) |

### Deliverables
- Fully working officer chat interface (UI + backend)
- Both city datasets ready (NYC CSV trimmed, Chandigarh synthetic CSV generated)
- Signal baselines and alert templates in place
- README, .env.example, and demo script ready
- Single-command project startup

---

## 📊 Task Dependency Map

```
Member 1 (Backend)  ──────────┐
   Feed simulator              │
   Incident detection          ├──→  Member 3 (CCTV) triggers on incident events
   WebSocket server            │         │
   LLM pipeline                │         │
                               │         ▼
Member 2 (Frontend) ◄─────────┤    CCTV events → WebSocket → Frontend
   Map + Sidebar               │
   CCTV UI components          │
                               │
Member 4 (Chatbot + Data) ◄───┘
   Chat UI (needs WebSocket from M1)
   Data CSVs (needed by M1's feed simulator)
   Signal baselines (needed by M1's prompt builder)
```

### Recommended Start Order
1. **Member 4** starts FIRST — generate datasets, signal baselines, and `.env` setup (other members need this data)
2. **Member 1** starts once CSVs and baselines are ready — build backend pipeline
3. **Member 2** can start immediately (scaffold frontend, build UI) — connects to backend when ready
4. **Member 3** starts YOLO pipeline independently — integrates with backend once incident detection works

---

## 🧮 Workload Summary

| Member | Role | # Tasks | Complexity | Key Tech |
|--------|------|---------|------------|----------|
| **1** | Backend Core | 12 | 🔴 High | FastAPI, MongoDB, Groq, ORS, NYPD Collisions API, SODA pagination, pandas |
| **2** | Frontend | 15 | 🔴 High | React, TypeScript, Leaflet, Zustand, Tailwind |
| **3** | CCTV + YOLO | 11 | 🔴 High | YOLOv8, OpenCV, Python |
| **4** | Chatbot + Data | 12 | 🟡 Medium | React (chat), Python (simple), pandas, docs |

---

*Plan generated for SENTINEL — Smart Transportation PS3 Hackathon*
