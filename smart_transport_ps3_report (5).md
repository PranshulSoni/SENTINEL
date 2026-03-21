# Smart Transportation — Problem Statement 3
## LLM Co-Pilot for Traffic Incident Command
### Hackathon Project Report

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement Analysis](#2-problem-statement-analysis)
3. [Solution Architecture](#3-solution-architecture)
4. [Four Core Output Types](#4-four-core-output-types)
   - 4.5 [CCTV + YOLO Visual Intelligence Layer](#45-cctv--yolo-visual-intelligence-layer)
5. [Technology Stack](#5-technology-stack)
6. [Frontend Architecture — React + TypeScript](#6-frontend-architecture--react--typescript)
7. [Data Sources — Dual City Strategy](#7-data-sources--dual-city-strategy)
8. [Synthetic Data Generation — Chandigarh](#8-synthetic-data-generation--chandigarh)
9. [MongoDB Atlas — Database Design](#9-mongodb-atlas--database-design)
10. [LLM Provider Options — Free Alternatives](#10-llm-provider-options--free-alternatives)
11. [System Data Flow](#11-system-data-flow)
12. [Functional & Non-Functional Requirements](#12-functional--non-functional-requirements)
13. [Demo Strategy](#13-demo-strategy)
14. [Scope Boundaries](#14-scope-boundaries)
15. [Risk Register](#15-risk-register)

---

## 1. Executive Summary

This project builds an **LLM-powered incident co-pilot** for traffic control officers managing live road accidents across two cities: **New York City** (real structured open data) and **Chandigarh** (synthetic data generated to mirror NYC structure). The dual-city approach demonstrates that the system is geographically portable — not NYC-specific — which is a strong differentiator at evaluation.

When a major incident occurs, officers today must mentally reconcile sensor feeds, camera streams, radio calls, and city maps — all simultaneously, all manually. There is no integrated view, no computational support for decisions, and no automated drafting of public alerts.

The co-pilot changes this. It ingests a live traffic speed feed, detects incidents automatically, and generates four types of real-time intelligence in natural language: signal re-timing suggestions, diversion route recommendations, publish-ready public alerts, and a conversational incident narrative the officer can query at any time.

Layered on top of this is a **CCTV + YOLO visual intelligence pipeline** — cameras continuously analyse the road, confirm or reject reported incidents, detect unusual events (vehicles stopped mid-road, anomalous speeds, emergency crises), prioritise ambulance routing, and automatically alert hospitals when injuries are detected. This eliminates false-alarm responses and gives the officer a visually-verified, AI-summarised picture of what is actually happening on the ground.

**The officer stays in command. The AI handles the cognitive synthesis.**

---

## 2. Problem Statement Analysis

### 2.1 The Core Breakdown

The problem is not a shortage of data. Traffic sensors and GPS feeds generate enormous amounts of real-time information. The breakdown is **synthesis under pressure** — no system connects these feeds into coherent, actionable decisions fast enough to matter.

### 2.2 Four Failure Modes

| Failure Mode | Current State | Cost |
|---|---|---|
| **Fragmented information** | Sensor data, incident reports, and road maps in separate systems | Officer must mentally reconcile multiple screens simultaneously |
| **Manual signal decisions** | Re-timing made from experience alone, no computational support | Suboptimal signal cascade, longer queue formation |
| **Manual diversion planning** | Officers estimate alternate routes without load redistribution data | Over-saturated diversion routes, secondary congestion |
| **Hand-drafted public alerts** | VMS, radio, and social media copy written manually during peak chaos | Alert delays, inconsistent messaging, public misinformation |
| **No visual ground truth** | Officers cannot verify if a reported incident is real or distinguish severity without physically attending | Fake reports waste resources; real injuries go undetected until someone calls |

### 2.3 The Compounding Cost of Delay

- Longer traffic clearance time on the primary incident segment
- Higher probability of **secondary accidents** in the backed-up zone
- Greater economic loss from gridlock (fuel, productivity, logistics)
- Increased officer stress and error rate under sustained cognitive load

---

## 3. Solution Architecture

### 3.1 Design Philosophy

The co-pilot is a **decision-support layer**, not an autonomous system. It never takes automated actions. Every recommendation is surfaced to the officer for approval. This keeps the officer legally and operationally in command while the AI removes the cognitive synthesis burden.

### 3.2 System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    REACT + TYPESCRIPT FRONTEND                   │
│                                                                  │
│  LEFT PANEL             CENTER MAP            RIGHT PANEL        │
│  City Selector          Leaflet.js Map        Chat Interface     │
│  Signal Re-timing       Speed-coloured        Multi-turn         │
│  Diversion Routes       Segments              Narrative          │
│  Alert Drafts           Diversion Overlay     Officer Input      │
│  Incident Log           Incident Marker                          │
└────────────┬────────────────────────────────────────────────────┘
             │  WebSocket / REST API
┌────────────▼────────────────────────────────────────────────────┐
│                    FASTAPI PYTHON BACKEND                        │
│                                                                  │
│  Feed Simulator     OSMnx + NetworkX      LLM Layer             │
│  pandas + threading  A* Routing           Groq / Gemini          │
│  5s tick intervals  Diversion Candidates  Structured Prompt      │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│              CCTV + YOLO VISUAL INTELLIGENCE LAYER               │
│                                                                  │
│  YOLOv8 object detection on CCTV frame streams                   │
│  Incident confirmation · Injury detection · Ambulance detection  │
│  Anomaly detection (stopped vehicle, wrong speed, blockage)      │
│  Event priority scoring · Hospital alert dispatch               │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│                    MONGODB ATLAS                                  │
│                                                                  │
│  incidents    feed_snapshots    llm_outputs                      │
│  chat_history  signal_baselines  diversion_routes                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Four Core Output Types

### 4.1 Signal Re-Timing Suggestions

The LLM identifies specific named intersections (from the OSM road graph) and recommends exact phase duration changes with reasoning.

**Example output — NYC:**
> *"Extend northbound green on W 34th St & 7th Ave from 45s to 90s. Reduce eastbound phase at Broadway & 34th St to 20s to cut inflow toward incident zone. Hold 10th Ave & 42nd St at current phase — diversion load peaks there in ~4 min."*

**Example output — Chandigarh:**
> *"Extend northbound green on Sector 17 Chowk from 40s to 80s. Reduce Phase 3B & Tribune Chowk eastbound to 18s to prevent queue build-up toward incident segment."*

### 4.2 Diversion Route Recommendations

NetworkX runs A* on the OSM graph to compute alternative paths when the incident segment is flagged blocked. The LLM outputs a prioritised activation sequence with estimated load redistribution.

**Example output:**
> *"Activate Diversion A first: 10th Ave → W 42nd St → 9th Ave. Expected to absorb ~60% of diverted volume. If 10th Ave drops below 15mph within 6 minutes, activate Diversion B. Do not activate both simultaneously — combined load exceeds 42nd St capacity."*

### 4.3 Ready-to-Publish Alert Drafts

Three format variants auto-generated on incident detection, not on manual request.

**VMS (Variable Message Sign):**
```
ACCIDENT W 34TH ST
EXPECT DELAYS
USE 10TH AVE ALTERNATE
```

**Radio broadcast:**
> *"Drivers on West 34th Street between 7th and 9th Avenues should expect significant delays. A multi-vehicle accident was reported at 14:32. Traffic management recommends 10th Avenue as an alternate route."*

**Social media:**
> *"Traffic alert: Multi-vehicle accident on W 34th St (7th–9th Ave). Significant delays expected. Use 10th Ave as alternate. Updates to follow. #NYCTraffic #Manhattan"*

### 4.4 Conversational Incident Narrative

A multi-turn chat interface the officer queries in plain English throughout the incident.

**Supported query types:**
- *"Is it safe to open the southbound lane now?"*
- *"What is the current congestion level on the diversion route?"*
- *"How long until clearance if we hold current diversions?"*
- *"What caused the speed drop on 9th Ave?"*

---

## 4.5 CCTV + YOLO Visual Intelligence Layer

Speed sensors and GPS feeds tell you *something is happening*. CCTV + YOLO tells you *what is actually happening*. This layer uses YOLOv8 real-time object detection running on camera frame streams to provide visual ground truth for every event the system detects — making the co-pilot the difference between reacting to data and understanding reality.

### Feature 1 — Incident Confirmation (Real vs False Alarm)

When a speed drop triggers an incident flag in the feed, the nearest CCTV camera's frame stream is automatically routed to the YOLO pipeline. The model checks for vehicles stopped in abnormal positions, debris on the road, emergency vehicles present, or clusters of people on the carriageway.

If visual evidence matches the sensor report → incident is confirmed and the officer is told it is real.
If visual evidence shows free-flowing traffic → incident is flagged as a probable sensor error or cleared road, saving an officer from dispatching resources to a ghost event.

**Officer notification:**
> *"Incident on W 34th St confirmed by Camera #14. YOLO detected 2 stationary vehicles and 4 persons on carriageway. Confidence: 94%."*

---

### Feature 2 — Multi-Incident Prioritisation

When two or more blockages are active simultaneously, the YOLO pipeline scores each visually using detected signals: number of stationary vehicles, presence of injured persons, emergency vehicle proximity, and lane obstruction severity. The LLM receives both YOLO scores and generates a prioritisation recommendation for the officer.

**Officer notification:**
> *"Two active incidents. Priority 1: Sector 22 Chowk — YOLO detects injured persons on road, no ambulance yet present. Priority 2: Tribune Chowk — vehicles stopped but occupants appear uninjured and walking. Recommend attending Sector 22 first."*

---

### Feature 3 — Unusual Event Detection

The YOLO pipeline runs continuously on all camera feeds even when no incident has been reported by the speed feed. It detects anomalies that sensors cannot surface:

- **Vehicle stopped mid-road** — stationary vehicle in a moving lane with no crash context (medical emergency, breakdown, car stall)
- **Abnormal speed** — vehicle moving significantly faster or slower than surrounding traffic (possible medical episode, technical failure, reckless driving)
- **Emergency crisis** — person on foot on a carriageway, road obstruction (debris, fallen object), smoke or fire near a vehicle

When an anomaly is detected, the system raises an alert to the officer and opens a camera feed thumbnail in the dashboard. The officer decides whether to investigate.

**Officer notification:**
> *"Anomaly on Madhya Marg near Sector 11: single vehicle stationary in lane 2 for 4+ minutes, no surrounding vehicles stopped. Possible breakdown or medical situation. Camera #7 thumbnail available."*

---

### Feature 4 — Ambulance Detection and Priority Routing

The YOLO model is trained to detect ambulance vehicle classes. When an ambulance is detected in a camera feed, the system:

1. Identifies the ambulance's current location and direction of travel from the camera position
2. Queries the OSM road graph and MongoDB `diversion_routes` for the fastest clear path to the nearest hospital
3. Triggers signal re-timing suggestions for intersections on that route to create a green corridor
4. Broadcasts a priority routing recommendation to the officer

**Officer notification:**
> *"Ambulance detected on 9th Ave northbound (Camera #22). Fastest clear route to NYU Langone: 9th Ave → W 34th St → 1st Ave. Recommending green extension at W 34th St & 9th Ave and W 34th St & 1st Ave. Estimated arrival with clear corridor: 4 min vs 11 min in current traffic."*

---

### Feature 5 — Injury Detection and Automatic Hospital Alert

When a crash is detected on camera, YOLO checks for persons in non-standing positions (lying on road, slumped against vehicles). If injured persons are detected, the system does not wait for a 112 call:

1. Flags the incident as an injury event in MongoDB `cctv_events`
2. Identifies the nearest hospital(s) using the OSM graph and GeoJSON coordinates
3. Generates a hospital alert message with incident location, number of detected injured persons, and the fastest ambulance route
4. Surfaces this to the officer for one-click dispatch confirmation

This addresses a critical real-world gap: bystanders frequently hesitate to call emergency services after a crash. The camera sees the injury and acts immediately.

**Officer notification:**
> *"Injury detected at W 34th St & 8th Ave (Camera #14). YOLO: 2 persons down on carriageway. Nearest hospital: Bellevue Hospital (1.4 km). Recommended ambulance route: 8th Ave → W 30th St → 1st Ave. Alert ready to dispatch — confirm?"*

---

### Feature 6 — Visual Context for Officer Chat Queries

YOLO detection results are stored as structured data in MongoDB `cctv_events` and injected into the LLM prompt context alongside the speed feed data. This means the officer can ask visual questions conversationally:

> *"Are there people injured on the road?"*
> *"Is the ambulance still stuck in traffic?"*
> *"Which incident looks worse right now?"*

The LLM answers using both the sensor data and the visual detection record, giving the officer a genuinely informed response rather than an inference from speed data alone.

---

## 5. Technology Stack

### 5.1 Full Stack Overview

| Layer | Technology | Role |
|---|---|---|
| **Frontend** | React 18 + TypeScript + Vite | SPA with three-panel layout, real-time WebSocket updates |
| **Styling** | Tailwind CSS + shadcn/ui | Component library, dark-mode dashboard aesthetic |
| **Map** | Leaflet.js + react-leaflet | Interactive map, speed-coloured polylines, diversion overlays |
| **State** | Zustand | Global incident state, feed state, chat history |
| **Real-time** | WebSocket (native browser API + FastAPI WebSocket) | Live feed updates every 5s without polling |
| **Backend** | FastAPI (Python) | REST + WebSocket server, feed simulator, routing, LLM calls |
| **Road Network** | OSMnx + NetworkX | Graph download, A* routing, intersection name extraction |
| **Feed Simulator** | pandas + Python threading | Replay NYC/Chandigarh CSV at 5s intervals |
| **Visual Intelligence** | YOLOv8 (Ultralytics) + OpenCV | Object detection on CCTV frames — incident confirmation, injury detection, ambulance detection, anomaly detection |
| **Database** | MongoDB Atlas | All persistence — incidents, feed snapshots, LLM outputs, chat, CCTV events |
| **LLM** | Groq API (free) | All four output types + conversational narrative, CCTV context injection |

### 5.2 Why React + TypeScript over Streamlit

Streamlit was listed in the PS as a suggested tool but it creates fundamental limitations that conflict with this project's component requirements:

| Requirement | Streamlit | React + TypeScript |
|---|---|---|
| Real-time map updates every 5s | Full page re-render on every update — causes flicker and lag | Surgical component re-renders via Zustand state diffing |
| Three independent live panels (map, sidebar, chat) | No true independent panel state | Each panel is an isolated component with its own state |
| Chat interface with input + response streaming | Awkward input handling, no streaming | Native controlled inputs, streaming LLM responses via SSE |
| Professional dashboard UI | Limited to Streamlit widgets | Full control — Tailwind + shadcn/ui, dark mode, custom layout |
| Leaflet diversion overlays | streamlit-folium has render latency issues | react-leaflet provides direct Leaflet API access |
| TypeScript type safety across API contracts | Not applicable | Full end-to-end type safety from API response to UI render |

---

## 6. Frontend Architecture — React + TypeScript

### 6.1 Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx          # Three-panel layout wrapper
│   │   │   ├── Sidebar.tsx           # Left panel — LLM outputs
│   │   │   └── ChatPanel.tsx         # Right panel — officer chat
│   │   ├── map/
│   │   │   ├── TrafficMap.tsx        # react-leaflet map root
│   │   │   ├── SpeedLayer.tsx        # Polylines coloured by speed
│   │   │   ├── IncidentMarker.tsx    # Pulsing incident location marker
│   │   │   └── DiversionOverlay.tsx  # A* route polyline overlay
│   │   ├── outputs/
│   │   │   ├── SignalCard.tsx        # Signal re-timing suggestions
│   │   │   ├── DiversionCard.tsx     # Diversion route recommendations
│   │   │   ├── AlertDraftCard.tsx    # VMS / Radio / Social drafts
│   │   │   └── CCTVEventCard.tsx     # YOLO detection results + confirmation badge
│   │   ├── cctv/
│   │   │   ├── CameraFeed.tsx        # CCTV thumbnail panel (simulated frame)
│   │   │   ├── DetectionBadge.tsx    # Overlay badges: CONFIRMED / INJURY / AMBULANCE
│   │   │   └── HospitalAlertModal.tsx # One-click hospital dispatch confirmation
│   │   └── ui/                       # shadcn/ui components
│   ├── store/
│   │   ├── incidentStore.ts          # Zustand — incident state
│   │   ├── feedStore.ts              # Zustand — live speed data
│   │   └── chatStore.ts              # Zustand — chat history
│   ├── hooks/
│   │   ├── useWebSocket.ts           # WebSocket connection + reconnect
│   │   └── useCitySelector.ts        # NYC vs Chandigarh toggle
│   ├── types/
│   │   ├── incident.ts               # TypeScript interfaces
│   │   ├── feed.ts
│   │   └── llm.ts
│   └── api/
│       └── client.ts                 # Typed REST API calls to FastAPI
```

### 6.2 Key Component Descriptions

#### `TrafficMap.tsx`
The central panel. Renders a Leaflet map centred on the selected city. Subscribes to `feedStore` — on each 5s tick, `SpeedLayer` updates polyline colours based on new speed values. When an incident is detected, `IncidentMarker` drops a pulsing red marker at the crash coordinates. `DiversionOverlay` draws the A* route as a distinct blue polyline.

#### `Sidebar.tsx`
Left panel. Renders three collapsible cards — `SignalCard`, `DiversionCard`, and `AlertDraftCard`. Each card subscribes to its own Zustand slice and updates independently when new LLM output arrives. No full-panel re-render.

#### `ChatPanel.tsx`
Right panel. Controlled input field. On submit, sends the officer query to the FastAPI `/chat` endpoint. Responses stream back via SSE and are rendered progressively. Full conversation history maintained in `chatStore`, which is persisted to MongoDB `chat_history` collection.

#### `useCitySelector.ts`
Hook that manages the city toggle between NYC and Chandigarh. On city switch: resets all Zustand stores, tells the backend to swap to the correct feed dataset, re-centres the Leaflet map on the new city's coordinates, and fetches the correct OSM graph segment geometry.

### 6.3 Real-Time Architecture

```
FastAPI WebSocket server
    │
    │  Every 5 seconds:
    │  { type: "feed_update", segments: [{id, name, speed, lat, lng}] }
    │
    │  On incident detection:
    │  { type: "incident_detected", location, severity, affected_segments }
    │
    │  On LLM output ready:
    │  { type: "llm_output", signal_retiming, diversions, alerts, narrative }
    │
    ▼
useWebSocket.ts hook
    │
    ├── feed_update    → feedStore.setSegments()
    ├── incident_detected → incidentStore.setIncident()
    └── llm_output     → incidentStore.setLLMOutputs()
                         (triggers Sidebar card re-renders)
```

### 6.4 Dependencies

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-leaflet": "^4.2.1",
    "leaflet": "^1.9.4",
    "zustand": "^4.5.2",
    "tailwindcss": "^3.4.0",
    "@radix-ui/react-tabs": "^1.1.0",
    "@radix-ui/react-scroll-area": "^1.1.0",
    "lucide-react": "^0.383.0",
    "clsx": "^2.1.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "@types/leaflet": "^1.9.8",
    "@types/react": "^18.3.0"
  }
}
```

---

## 7. Data Sources — Dual City Strategy

The project supports two cities. NYC uses fully structured real open data. Chandigarh uses synthetic data generated to mirror the exact schema of the NYC datasets, enabling the same pipeline to handle both cities without code changes.

### 7.1 City Comparison

| Dimension | NYC | Chandigarh |
|---|---|---|
| **Traffic speed data** | **Real — DOT Traffic Speeds NBE · `i4gi-tjb9`** | Synthetic — generated from NYC schema |
| **Collision data** | **Real — NYPD Motor Vehicle Collisions · `h9gi-nx95`** | Synthetic — generated to match collision schema |
| Road network + routing | OpenRouteService API (online, no download) | OpenRouteService API (online, covers India) |
| Signal baselines | NYC DOT ATSPM (or static fallback) | Synthetic — generated from typical Indian signal timings |
| Data cost | Free | Free |

---

### 7.2 NYC Data Sources

#### Dataset 1 — DOT Traffic Speeds NBE (NYC Open Data)

**Dataset URL:** `https://data.cityofnewyork.us/Transportation/DOT-Traffic-Speeds-NBE/i4gi-tjb9/about_data`

**What it is:** Real-time traffic speed and travel time per road segment across NYC, updated every 5 minutes by NYC DOT.

**Key fields:** `LINK_ID`, `LINK_NAME`, `SPEED`, `TRAVEL_TIME`, `STATUS`, `DATA_AS_OF`

**Used for:** Core feed simulator input — replayed at 5s intervals. Speed values drive map colours and trigger incident detection. Injected into LLM prompt context.

**API Endpoint:**
```
https://data.cityofnewyork.us/resource/i4gi-tjb9.json
```

**The 1,000 row default limit — how to fix it:**

NYC Open Data (Socrata SODA API) returns only 1,000 rows by default. There are two fixes — use both together:

**Fix 1 — Add `$limit` and `$offset` parameters:**
```
# Get up to 50,000 rows in one call
https://data.cityofnewyork.us/resource/i4gi-tjb9.json?$limit=50000&$offset=0

# Page 2 if needed
https://data.cityofnewyork.us/resource/i4gi-tjb9.json?$limit=50000&$offset=50000
```

**Fix 2 — Register a free app token (removes throttle entirely):**
1. Sign up at `data.cityofnewyork.us` (free)
2. Account → Developer Settings → Create New App Token
3. Append to every request:
```
https://data.cityofnewyork.us/resource/i4gi-tjb9.json
  ?$limit=50000
  &$$app_token=YOUR_APP_TOKEN
```

**Offline download for feed simulator (one-time, cache locally):**
```bash
curl "https://data.cityofnewyork.us/resource/i4gi-tjb9.csv\
?$limit=50000\
&$$app_token=YOUR_APP_TOKEN" \
-o nyc_link_speed.csv
```

**Python paginated fetch (if dataset exceeds 50k rows):**
```python
import requests
import pandas as pd

def fetch_nyc_link_speed(app_token: str) -> pd.DataFrame:
    base_url = "https://data.cityofnewyork.us/resource/i4gi-tjb9.json"
    all_records = []
    limit = 50000
    offset = 0

    while True:
        params = {
            "$limit":     limit,
            "$offset":    offset,
            "$$app_token": app_token
        }
        resp = requests.get(base_url, params=params)
        batch = resp.json()
        if not batch:
            break
        all_records.extend(batch)
        offset += limit
        if len(batch) < limit:
            break   # last page

    return pd.DataFrame(all_records)
```

**Cost: Free.** App token is free, no payment, no approval wait — just account registration.

---

#### NYPD Motor Vehicle Collisions — Crashes

**Dataset URL:** `https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95/about_data`

**What it is:** Every police-reported motor vehicle collision in NYC. Required to be filed when someone is injured/killed or damage exceeds $1,000. Updated daily. Over 2 million records going back to 2012 — the most detailed urban collision dataset publicly available anywhere.

**Key fields:** `crash_date`, `crash_time`, `borough`, `zip_code`, `latitude`, `longitude`, `on_street_name`, `cross_street_name`, `number_of_persons_injured`, `number_of_persons_killed`, `contributing_factor_vehicle_1`, `vehicle_type_code1`

**Used for:**
- Collision detection layer — query recent crashes (last 7 days) by bounding box coordinates, match to OSM road segments, surface on map as collision markers
- Demo scenario anchor — pick a real high-injury crash at a specific intersection, overlay with speed data from the same location to show congestion causation
- YOLO confirmation context — when YOLO flags an incident, cross-reference with NYPD collision records at that coordinate to enrich the officer alert
- LLM context injection — historical collision frequency at an intersection ("this location has had 8 crashes in the last 30 days") makes the LLM's signal re-timing reasoning more credible

**API Endpoint:**
```
https://data.cityofnewyork.us/resource/h9gi-nx95.json
```

**Useful queries:**

Recent crashes in NYC (last 7 days):
```
https://data.cityofnewyork.us/resource/h9gi-nx95.json
  ?$$app_token=YOUR_TOKEN
  &$where=crash_date > '2025-03-14T00:00:00'
  &$limit=5000
  &$order=crash_date DESC
```

Crashes near a specific coordinate (Manhattan demo area):
```python
import requests

def get_nearby_collisions(lat: float, lng: float, radius_deg: float = 0.005,
                           app_token: str = "") -> list:
    # radius_deg ≈ 500m at NYC latitude
    url = "https://data.cityofnewyork.us/resource/h9gi-nx95.json"
    params = {
        "$$app_token": app_token,
        "$where": f"latitude between {lat - radius_deg} and {lat + radius_deg} "
                  f"and longitude between {lng - radius_deg} and {lng + radius_deg} "
                  f"and crash_date > '2025-01-01T00:00:00'",
        "$limit": 500,
        "$order": "crash_date DESC"
    }
    return requests.get(url, params=params).json()
```

High-injury crashes for demo scenario selection:
```
https://data.cityofnewyork.us/resource/h9gi-nx95.json
  ?$$app_token=YOUR_TOKEN
  &$where=number_of_persons_injured > 2 and on_street_name='WEST 34 STREET'
  &$limit=10
```

**Cost: Free.** Same NYC Open Data app token covers this and the traffic speed endpoint.

---


#### OpenRouteService API — Road Network + Routing (Replaces offline OSMnx)

**What it is:** A fully hosted routing service built on OpenStreetMap data, maintained by HeiGIT (Heidelberg University). Provides directions, A* routing, matrix distances, isochrones, and geocoding — all via REST API calls. No graph download, no local files, no offline dependency. Works globally, including both NYC and Chandigarh.

**Why this replaces offline OSMnx:**
- OSMnx requires downloading the full road graph (~200–400MB for Manhattan alone) and storing it as a `.graphml` file
- OpenRouteService gives you the same OSM data on-demand via a simple API call
- Real street names and intersection data come back in the response geometry — same quality as OSMnx
- No startup download time, no cached file management, no demo-day network issues

**Used for:**
- Diversion route computation — POST a blocked origin + destination, receive GeoJSON route with street names
- Hospital routing for ambulance detection — fastest route from incident coordinates to nearest hospital
- Replacing NetworkX A* routing entirely — ORS handles this server-side

**Core Endpoint — Directions (replaces A*):**
```
POST https://api.openrouteservice.org/v2/directions/driving-car/geojson

Headers:
  Authorization: YOUR_ORS_KEY
  Content-Type: application/json

Body:
{
  "coordinates": [[origin_lng, origin_lat], [dest_lng, dest_lat]],
  "instructions": true,
  "extra_info": ["roadaccessrestrictions"],
  "options": {
    "avoid_features": ["tollways"]
  }
}
```

**Response includes:** Full GeoJSON LineString geometry (usable directly as a Leaflet polyline), step-by-step street names, total distance, total duration — everything needed for both the map overlay and the LLM diversion prompt.

**Python integration (FastAPI backend):**
```python
import httpx

ORS_KEY = os.getenv("ORS_API_KEY")   # Free at openrouteservice.org

async def get_diversion_route(origin: tuple, destination: tuple) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
            headers={"Authorization": ORS_KEY},
            json={"coordinates": [list(origin), list(destination)]}
        )
    return response.json()
    # Returns GeoJSON FeatureCollection — store in MongoDB diversion_routes
    # geometry.coordinates → Leaflet polyline
    # features[0].properties.segments[].steps[].name → street names for LLM prompt
```

**How to get the key:**
1. Sign up at `openrouteservice.org` (free)
2. Dashboard → Generate Token → copy key
3. Immediately active

**Free tier limits:**
- 2,000 direction requests per day
- 500 isochrone requests per day
- No credit card required

The demo needs at most 10–20 routing calls total (pre-computed on startup for the demo scenario). 2,000/day is effectively unlimited for hackathon use.

**Cost: Free.**

**Note on OSMnx:** OSMnx is still used in one place — generating the Chandigarh synthetic feed (extracting edge names and coordinates from the graph to build the CSV). It is not used for routing or live map data. The graphml file for Chandigarh is only needed during data generation, not during demo runtime.

---

**Used for:** Baseline signal phase durations so LLM outputs are numerically grounded.

**Hackathon fallback — static dict:**
```python
NYC_SIGNAL_BASELINES = {
    "W 34th St & 7th Ave":  {"ns_green": 45, "ew_green": 30},
    "Broadway & 34th St":   {"ns_green": 60, "ew_green": 25},
    "10th Ave & 42nd St":   {"ns_green": 40, "ew_green": 35},
}
```

**Cost: Free.**

---

### 7.3 Chandigarh Data Sources

#### OpenStreetMap (via OSMnx) — Chandigarh

OSM has solid coverage of Chandigarh's road network including sector roads, chowks, and the major arterials.

```python
G_chd = ox.graph_from_place("Chandigarh, India", network_type="drive")
ox.save_graphml(G_chd, filepath="chandigarh_graph.graphml")
```

This is the **only real data** needed for Chandigarh. Everything else is synthetic (see Section 8).

**Cost: Free.**

---

#### Synthetic Traffic Speed Data — Chandigarh

Fully described in Section 8. Generated using the NYC DOT Link Speed schema with Chandigarh road names from OSMnx.

#### Synthetic Incident Records — Chandigarh

Fully described in Section 8. Generated using the **NYPD Motor Vehicle Collisions schema** (`h9gi-nx95` field structure) with Chandigarh intersection coordinates from OSMnx.

#### Synthetic Signal Baselines — Chandigarh

```python
CHD_SIGNAL_BASELINES = {
    "Sector 17 Chowk":          {"ns_green": 40, "ew_green": 35},
    "Tribune Chowk":            {"ns_green": 50, "ew_green": 30},
    "PGI Chowk":                {"ns_green": 45, "ew_green": 40},
    "Madhya Marg & Sector 22":  {"ns_green": 35, "ew_green": 30},
}
```

---

### 7.4 Complete API Cost Summary

| Dataset | URL | Source | Free? |
|---|---|---|---|
| **DOT Traffic Speeds NBE** | `data.cityofnewyork.us/resource/i4gi-tjb9.json` | NYC Open Data (SODA) | ✅ Free |
| **NYPD Motor Vehicle Collisions** | `data.cityofnewyork.us/resource/h9gi-nx95.json` | NYC Open Data (SODA) | ✅ Free |
| OpenRouteService (Routing) | `api.openrouteservice.org/v2/directions` | ORS API (HeiGIT) | ✅ Free |
| NYC DOT ATSPM (Signal baselines) | NYC Open Data (SODA) | NYC Open Data | ✅ Free |
| OpenStreetMap Chandigarh | OSM Overpass via OSMnx | OpenStreetMap | ✅ Free |
| Chandigarh traffic + collision | Synthetic generation (local script) | — | ✅ Free |
| LLM (Groq) | `api.groq.com` | Groq API | ✅ Free (14,400 req/day) |

**Total external API cost: $0.**

**One app token covers both NYC Open Data endpoints.** Register at `data.cityofnewyork.us` → Account → Developer Settings → Create New App Token. No card, no approval, instant.

---

## 8. Synthetic Data Generation — Chandigarh

Since Chandigarh has no equivalent of NYC Open Data, synthetic data is generated that mirrors the NYC schema exactly. This means the feed simulator, incident detector, and LLM prompt builder require zero code changes between cities.

### 8.1 Schema Mirroring

The synthetic Chandigarh CSV uses the **exact same column names** as the NYC DOT Link Speed dataset:

```
LINK_ID, LINK_NAME, SPEED, TRAVEL_TIME, STATUS, DATA_AS_OF, LATITUDE, LONGITUDE
```

`LINK_NAME` values come from OSMnx edge names for Chandigarh. `LATITUDE` and `LONGITUDE` come from OSMnx node coordinates. `SPEED` and `TRAVEL_TIME` are generated (see below).

### 8.2 Speed Data Generation Method

```python
import osmnx as ox
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_chandigarh_feed(output_path: str, hours: int = 4):
    G = ox.load_graphml("chandigarh_graph.graphml")
    edges = ox.graph_to_gdfs(G, nodes=False).reset_index()

    # Use speed limits from OSM where available, default to 40 km/h
    edges["speed_limit"] = edges["maxspeed"].fillna(40).apply(
        lambda x: float(str(x).split()[0]) if isinstance(x, str) else float(x)
    )

    records = []
    base_time = datetime(2024, 3, 15, 8, 0, 0)   # Morning peak

    for minute in range(hours * 60):
        timestamp = base_time + timedelta(minutes=minute)
        hour = timestamp.hour

        for _, edge in edges.iterrows():
            # Base congestion pattern: morning peak 8-10am, evening peak 5-8pm
            if 8 <= hour <= 10 or 17 <= hour <= 20:
                congestion = np.random.uniform(0.3, 0.6)   # 30-60% of free flow
            elif 12 <= hour <= 14:
                congestion = np.random.uniform(0.5, 0.75)  # Lunch — moderate
            else:
                congestion = np.random.uniform(0.75, 1.0)  # Free flow

            speed = edge["speed_limit"] * congestion
            travel_time = (edge["length"] / 1000) / (speed / 60)  # minutes

            records.append({
                "LINK_ID":       str(edge["osmid"]) if isinstance(edge["osmid"], int)
                                  else str(edge["osmid"][0]),
                "LINK_NAME":     edge.get("name", f"Unnamed Rd {edge['osmid']}"),
                "SPEED":         round(speed, 1),
                "TRAVEL_TIME":   round(travel_time, 2),
                "STATUS":        "OK" if speed > 15 else "SLOW",
                "DATA_AS_OF":    timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
                "LATITUDE":      (edge["geometry"].interpolate(0.5, normalized=True).y),
                "LONGITUDE":     (edge["geometry"].interpolate(0.5, normalized=True).x),
            })

    pd.DataFrame(records).to_csv(output_path, index=False)
    print(f"Generated {len(records)} records for Chandigarh feed.")
```

### 8.3 Incident Injection Method

A synthetic incident is injected at a chosen Chandigarh intersection by dropping speed values on adjacent segments over a 3–5 minute window:

```python
def inject_incident(df: pd.DataFrame, incident_link_id: str,
                    incident_time: datetime, radius_links: list[str]) -> pd.DataFrame:
    """
    Drops speed values to simulate an accident.
    incident_link_id: the blocked segment
    radius_links: adjacent segments that get congested
    """
    df = df.copy()
    incident_mask = (
        (df["LINK_ID"] == incident_link_id) &
        (df["DATA_AS_OF"] >= incident_time.strftime("%Y-%m-%dT%H:%M:%S"))
    )
    df.loc[incident_mask, "SPEED"] = 0.0
    df.loc[incident_mask, "STATUS"] = "BLOCKED"

    for radius_link in radius_links:
        radius_mask = (
            (df["LINK_ID"] == radius_link) &
            (df["DATA_AS_OF"] >= incident_time.strftime("%Y-%m-%dT%H:%M:%S")) &
            (df["DATA_AS_OF"] <= (incident_time + timedelta(minutes=30))
             .strftime("%Y-%m-%dT%H:%M:%S"))
        )
        df.loc[radius_mask, "SPEED"] = df.loc[radius_mask, "SPEED"] * 0.25
        df.loc[radius_mask, "STATUS"] = "SLOW"

    return df
```

### 8.4 Synthetic Incident Record (Crash Schema)

One synthetic crash record is created per demo scenario to anchor the Chandigarh narrative:

```python
CHANDIGARH_DEMO_INCIDENT = {
    "crash_date":                 "2024-03-15",
    "crash_time":                 "09:15",
    "on_street_name":             "MADHYA MARG",
    "cross_street_name":          "SECTOR 22",
    "latitude":                   30.7333,
    "longitude":                  76.7794,
    "number_of_persons_injured":  3,
    "contributing_factor":        "Unsafe Speed",
    "city":                       "CHANDIGARH"
}
```

### 8.5 Why This Approach Is Valid

- The OSM road graph for Chandigarh is real — all street names, intersection coordinates, and road geometry are genuine
- Speed values are generated from real traffic engineering principles (congestion factors, time-of-day patterns, speed limits from OSM)
- The schema is identical to the NYC source, so no city-specific code exists anywhere in the pipeline
- The demo can credibly claim both cities are supported — the only difference is data origin

---

## 9. MongoDB Atlas — Database Design

All persistence goes through MongoDB Atlas. The schema is designed around the four core system events: feed ticks, incident detection, LLM output generation, and officer chat queries.

### 9.1 Collections

#### `incidents`

Stores one document per detected incident. Updated as the incident progresses.

```javascript
{
  _id: ObjectId,
  city: "nyc" | "chandigarh",
  status: "active" | "resolved",
  detected_at: ISODate,
  resolved_at: ISODate | null,
  severity: "minor" | "major" | "critical",
  location: {
    type: "Point",
    coordinates: [longitude, latitude]   // GeoJSON
  },
  on_street: "W 34th St",
  cross_street: "7th Ave",
  affected_segment_ids: ["seg_001", "seg_042"],
  source: "nyc_dot" | "synthetic_chandigarh",
  crash_record_id: "nyc_nypd_h9gi_nx95_rowid" | null
}
```

**Index:** `{ city: 1, status: 1 }`, `{ location: "2dsphere" }` (for geospatial queries)

---

#### `feed_snapshots`

Stores lightweight snapshots of the feed state at each tick. Used to reconstruct incident timeline and provide context to the LLM.

```javascript
{
  _id: ObjectId,
  city: "nyc" | "chandigarh",
  snapshot_time: ISODate,
  incident_id: ObjectId | null,
  segments: [
    {
      link_id: "12345",
      link_name: "W 34th St",
      speed: 8.4,
      status: "SLOW",
      lat: 40.7484,
      lng: -73.9967
    }
    // ...
  ]
}
```

**TTL Index:** `{ snapshot_time: 1 }` with `expireAfterSeconds: 7200` — auto-purge snapshots older than 2 hours to control Atlas storage usage.

---

#### `llm_outputs`

Stores every LLM-generated response. Keyed to the incident and feed snapshot it was generated from.

```javascript
{
  _id: ObjectId,
  incident_id: ObjectId,
  city: "nyc" | "chandigarh",
  generated_at: ISODate,
  feed_snapshot_id: ObjectId,
  model_used: "llama-3.3-70b-versatile",
  provider: "groq",
  prompt_tokens: 892,
  completion_tokens: 614,
  outputs: {
    signal_retiming: {
      intersections: [
        {
          name: "W 34th St & 7th Ave",
          current_ns_green: 45,
          recommended_ns_green: 90,
          current_ew_green: 30,
          recommended_ew_green: 20,
          reasoning: "Incident upstream — extend outflow green"
        }
      ],
      raw_text: "..."
    },
    diversions: {
      routes: [
        {
          priority: 1,
          name: "Diversion A",
          path: ["10th Ave", "W 42nd St", "9th Ave"],
          estimated_absorption_pct: 60,
          activate_condition: "immediate"
        }
      ],
      raw_text: "..."
    },
    alerts: {
      vms: "ACCIDENT W 34TH ST\nEXPECT DELAYS\nUSE 10TH AVE ALTERNATE",
      radio: "Drivers on West 34th Street...",
      social_media: "Traffic alert: Multi-vehicle accident..."
    },
    narrative_update: "At 14:37, the incident on W 34th St..."
  }
}
```

---

#### `chat_history`

Stores the full multi-turn conversation for each incident session. The entire document is fetched and passed to the LLM on each new officer query to maintain context.

```javascript
{
  _id: ObjectId,
  incident_id: ObjectId,
  city: "nyc" | "chandigarh",
  session_start: ISODate,
  messages: [
    {
      role: "system",
      content: "You are a traffic incident co-pilot...",
      timestamp: ISODate
    },
    {
      role: "user",
      content: "Is it safe to open the southbound lane now?",
      timestamp: ISODate
    },
    {
      role: "assistant",
      content: "Based on current feed data, southbound speed on...",
      timestamp: ISODate,
      model_used: "llama-3.3-70b-versatile"
    }
  ]
}
```

**Index:** `{ incident_id: 1 }` — one chat document per incident, always fetched whole.

---

#### `signal_baselines`

Stores per-intersection baseline phase durations. Pre-populated on startup for both cities.

```javascript
{
  _id: ObjectId,
  city: "nyc" | "chandigarh",
  intersection_name: "W 34th St & 7th Ave",
  osm_node_id: 42837291,
  lat: 40.7484,
  lng: -73.9967,
  ns_green_seconds: 45,
  ew_green_seconds: 30,
  cycle_length_seconds: 90,
  source: "nyc_atspm" | "synthetic"
}
```

---

#### `diversion_routes`

Stores pre-computed A* diversion routes per blocked segment. Computed once at startup using the OSM graph, stored in Atlas, served on demand.

```javascript
{
  _id: ObjectId,
  city: "nyc" | "chandigarh",
  blocked_segment_id: "seg_034",
  blocked_segment_name: "W 34th St (7th–9th Ave)",
  computed_at: ISODate,
  routes: [
    {
      priority: 1,
      name: "Diversion A",
      segment_names: ["10th Ave", "W 42nd St", "9th Ave"],
      geometry: {
        type: "LineString",
        coordinates: [[lng, lat], ...]   // GeoJSON for Leaflet overlay
      },
      total_length_km: 2.3,
      estimated_extra_minutes: 4
    }
  ]
}
```

**Index:** `{ city: 1, blocked_segment_id: 1 }` — fast lookup when incident is detected.

---

#### `cctv_events`

Stores every YOLO detection event from camera feeds. Each document corresponds to one detection result on one camera frame batch.

```javascript
{
  _id: ObjectId,
  city: "nyc" | "chandigarh",
  incident_id: ObjectId | null,         // linked incident if applicable
  camera_id: "cam_014",
  camera_location: {
    type: "Point",
    coordinates: [longitude, latitude]
  },
  detected_at: ISODate,
  frame_source: "simulated" | "live",   // simulated for hackathon demo
  detections: [
    {
      class: "person" | "car" | "ambulance" | "truck" | "motorcycle",
      confidence: 0.94,
      bbox: [x1, y1, x2, y2],
      is_stationary: true | false,
      is_on_carriageway: true | false
    }
  ],
  event_type: "incident_confirmed" | "incident_unconfirmed" | "injury_detected"
            | "ambulance_detected" | "anomaly_stopped_vehicle"
            | "anomaly_speed" | "anomaly_obstruction",
  priority_score: 87,                   // 0-100, used for multi-incident ranking
  injury_count: 2,                      // persons detected in non-standing position
  hospital_alert_sent: false,
  hospital_alert_confirmed_by_officer: false,
  nearest_hospital: {
    name: "Bellevue Hospital",
    lat: 40.7392,
    lng: -73.9759,
    recommended_route_id: ObjectId      // ref to diversion_routes
  }
}
```

**Index:** `{ city: 1, incident_id: 1 }`, `{ camera_location: "2dsphere" }`, `{ event_type: 1, detected_at: -1 }`

### 9.2 Atlas Configuration

```python
# backend/db.py
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient   # Async for FastAPI

MONGO_URI = "mongodb+srv://<user>:<pass>@cluster0.mongodb.net/?retryWrites=true&w=majority"

client = AsyncIOMotorClient(MONGO_URI)
db = client["traffic_copilot"]

incidents          = db["incidents"]
feed_snapshots     = db["feed_snapshots"]
llm_outputs        = db["llm_outputs"]
chat_history       = db["chat_history"]
signal_baselines   = db["signal_baselines"]
diversion_routes   = db["diversion_routes"]
cctv_events        = db["cctv_events"]
```

**Atlas Free Tier (M0):** 512MB storage — sufficient for a hackathon demo. TTL index on `feed_snapshots` prevents storage overflow.

---

## 10. LLM Provider Options — Free Alternatives

The PS references the Anthropic SDK (paid). The following free-tier providers are drop-in replacements.

### 10.1 Recommended: Groq

**Why it is the best choice:**
- Genuinely free — no credit card required
- LPU hardware provides the fastest free inference available — critical for sub-5s latency
- `llama-3.3-70b-versatile` is strong at structured multi-section output and multi-turn reasoning
- OpenAI-compatible API — minimal code changes

**Free tier:** 14,400 requests/day, 6,000 tokens/min. No hackathon scenario will approach these limits.

**Get key:** `console.groq.com` (free account)

```python
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": INCIDENT_SYSTEM_PROMPT},
        {"role": "user",   "content": build_incident_context(feed_snapshot, incident)}
    ],
    max_tokens=1500
)

raw_output = response.choices[0].message.content
```

### 10.2 Fallback: Google Gemini Flash

**Model:** `gemini-2.0-flash`
**Free tier:** 1,500 requests/day — no credit card
**Get key:** `aistudio.google.com`

```python
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

response = model.generate_content(
    INCIDENT_SYSTEM_PROMPT + "\n\n" + build_incident_context(feed_snapshot, incident)
)
output = response.text
```

### 10.3 Backup: OpenRouter (Free Models)

OpenAI-compatible router with permanently free model tiers.

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")   # Free at openrouter.ai
)

response = client.chat.completions.create(
    model="meta-llama/llama-3.3-70b-instruct:free",
    messages=[
        {"role": "system", "content": INCIDENT_SYSTEM_PROMPT},
        {"role": "user",   "content": build_incident_context(feed_snapshot, incident)}
    ]
)
```

### 10.4 Provider Comparison

| Provider | Best Free Model | Speed | Structured Output | Recommended |
|---|---|---|---|---|
| **Groq** | llama-3.3-70b-versatile | Fastest | Excellent | Primary |
| **Google Gemini** | gemini-2.0-flash | Fast | Excellent | Fallback |
| **OpenRouter** | llama-3.3-70b:free | Good | Good | Backup |

---

## 11. System Data Flow

```
FEED LAYER
  NYC CSV or Chandigarh Synthetic CSV
  pandas reader + Python threading → emit frame every 5s
  Output: List[{link_id, link_name, speed, lat, lng}]
          │
          ▼
INCIDENT DETECTION
  Rolling 5-frame baseline per segment
  Speed drop > 40% on 2+ adjacent segments → incident flagged
  Write to MongoDB: incidents collection
          │                     │
          ▼                     ▼
OSMnx ROAD GRAPH        WEBSOCKET BROADCAST
  Extract intersection    → React frontend
  names near incident     feedStore.setSegments()
  Fetch A* diversions     SpeedLayer re-colours map
  from MongoDB Atlas      IncidentMarker drops pin
          │
          ├─────────────────────────────────────────────┐
          │                                             │
          ▼                                             ▼
STRUCTURED PROMPT BUILDER               CCTV + YOLO PIPELINE
  Inject: affected segments,            YOLOv8 runs on nearest
  intersection names, diversions,       camera frame stream
  signal baselines, incident duration   Detects: vehicles, persons,
          │                             ambulances, stopped objects
          │                             ┌─────────────────────────┐
          │                             │ Event Classification:   │
          │                             │ incident_confirmed      │
          │                             │ injury_detected         │
          │                             │ ambulance_detected      │
          │                             │ anomaly_*               │
          │                             └────────┬────────────────┘
          │                                      │
          │                             Save to MongoDB
          │                             cctv_events collection
          │                                      │
          │              ┌───────────────────────┘
          ▼              ▼
STRUCTURED PROMPT BUILDER (with CCTV context injected)
  + YOLO event type, detection counts, confidence, injury flags
          │
          ▼
LLM LAYER (Groq llama-3.3-70b)
  → Five-section structured output
          │
    ┌─────┴──────────────┬───────────────┬────────────────┬──────────────┐
    ▼                    ▼               ▼                ▼              ▼
Signal Retiming     Diversions      Alert Drafts     Narrative     CCTV Summary
  + YOLO-confirmed    + Ambulance      + Injury          + Visual      for officer
  signal suggestions  green corridor   alert flag        context       chat queries
    │                    │               │                │              │
    └────────────────────┴───────────────┴────────────────┴──────────────┘
                         │
                  Save to MongoDB (llm_outputs)
                         │
                  WebSocket broadcast → React updates:
                  Sidebar cards, Diversion overlay,
                  CCTVEventCard, HospitalAlertModal (if injury)

OFFICER CHAT FLOW
  Officer types query → POST /chat (FastAPI)
  Fetch chat_history + latest cctv_events from MongoDB
  Append new user message with CCTV context
  Call Groq with full conversation + visual intelligence
  Save assistant response to MongoDB
  Stream response back via SSE → ChatPanel renders
```

---

## 12. Functional & Non-Functional Requirements

### 12.1 Functional Requirements

| ID | Requirement |
|---|---|
| FR1 | Ingest simulated live traffic speed feed at ≤ 5-second intervals for both NYC and Chandigarh |
| FR2 | Detect incident conditions from speed drop anomalies; persist to MongoDB `incidents` collection |
| FR3 | Generate signal re-timing recommendations naming specific OSM intersections with exact phase changes |
| FR4 | Compute diversion routes via A* on OSM graph; serve from MongoDB `diversion_routes`; overlay on Leaflet map |
| FR5 | Generate publish-ready alert drafts in three formats (VMS, radio, social media) on incident detection |
| FR6 | Maintain multi-turn conversational context in MongoDB `chat_history`; support at least 10 turns |
| FR7 | City toggle between NYC and Chandigarh resets all state and switches data source with no app restart |
| FR8 | React frontend receives live updates via WebSocket; no polling, no full-page refreshes |
| FR9 | YOLO pipeline confirms or rejects incident reports by running object detection on nearest camera feed frames |
| FR10 | When two or more incidents are active, YOLO priority scores are generated and surfaced to the officer as a ranked recommendation |
| FR11 | Anomaly detection runs continuously — detect stopped vehicles, abnormal speeds, and road obstructions even without a feed-triggered incident |
| FR12 | When an ambulance is detected by YOLO, generate a green-corridor signal re-timing recommendation and fastest hospital route |
| FR13 | When injured persons are detected (non-standing positions on carriageway), generate a hospital alert with route and surface for officer confirmation |
| FR14 | CCTV event data from MongoDB `cctv_events` is injected into LLM prompt context so officer chat queries can reference visual ground truth |

### 12.2 Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR1 | End-to-end LLM response under 5 seconds from incident detection to sidebar cards rendered |
| NFR2 | All intersection names in LLM outputs must be real OSM names — no hallucinated street names |
| NFR3 | Officer is never blocked — system is purely advisory, all outputs are suggestions |
| NFR4 | Demo reproducible offline using cached OSM graphs and CSV files — no live internet during demo |
| NFR5 | MongoDB TTL index ensures `feed_snapshots` collection does not exceed M0 free tier (512MB) |

### 12.3 Prompt Engineering Requirements

```
System prompt structure:

You are a traffic incident co-pilot for {city}.
Current incident: {severity} on {street} at {cross_street}.
Active for: {duration} minutes.

LIVE FEED STATE (last 5s tick):
{affected_segments_table}

AVAILABLE DIVERSION ROUTES (A* computed):
{diversion_candidates}

NEARBY INTERSECTIONS (OSM):
{intersection_list}

SIGNAL BASELINES:
{signal_baselines_table}

CCTV VISUAL INTELLIGENCE (YOLOv8, Camera #{camera_id}):
Confirmation status: {confirmed | unconfirmed | injury_detected | ambulance_present}
Detected objects: {detection_summary}
Injured persons detected: {injury_count}
Ambulance detected: {yes | no}, direction: {direction}
Priority score vs other active incidents: {priority_score}/100

Generate a response with exactly five sections:
[SIGNAL_RETIMING] — name intersections, give exact phase durations; if ambulance detected, include green-corridor suggestions
[DIVERSIONS] — activation sequence with load estimates; if ambulance, include fastest hospital route
[ALERTS] — VMS | RADIO | SOCIAL subsections; if injury confirmed, flag for hospital alert
[NARRATIVE_UPDATE] — plain English incident status incorporating visual confirmation
[CCTV_SUMMARY] — one paragraph summarising what the camera confirms, any injuries, any ambulance routing, anomalies

Use ONLY the intersection names provided above. Do not generate street names.
Professional emergency operations tone.
```

---

## 13. Demo Strategy

### 13.1 NYC Scenario

Pick a real NYPD multi-vehicle crash on W 34th St (cross-reference with Link Speed timestamp). Feed replays the speed data from 5 minutes before the crash through clearance. This makes the incident progression authentic and the demo narrative credible.

### 13.2 Chandigarh Scenario

Synthetic incident injected at Madhya Marg & Sector 22 during the morning peak window in the generated CSV. Demonstrates geographic portability with a completely different road network and city scale.

### 13.3 Demo Run Script

1. App loads on city selector → officer picks NYC
2. Leaflet map centres on Manhattan, all segments render green
3. Feed replay starts → incident zone yellows and reds over 30s
4. Incident auto-detected → sidebar populates with all four LLM cards
5. Blue diversion polyline draws on map
6. **CCTV panel activates** — YOLOv8 runs on simulated camera frame → `CONFIRMED` badge appears on incident marker
7. If injury scenario: `HospitalAlertModal` pops — officer clicks confirm to dispatch
8. Judge asks: *"Is it safe to open the southbound lane now?"* → co-pilot answers using both feed data and YOLO visual confirmation
9. Officer switches to Chandigarh → map re-centres, new feed + CCTV pipeline starts, same flow

### 13.4 Minutes Saved Panel

| Action | Manual Baseline | AI Co-Pilot |
|---|---|---|
| Signal re-timing decision | 8–12 minutes | Under 30 seconds |
| Diversion route identified | 5–10 minutes | Under 30 seconds |
| VMS alert drafted | 3–5 minutes | Instant |
| Radio bulletin drafted | 5 minutes | Instant |
| Incident confirmation (real vs fake) | Officer physically attends | YOLO confirms in < 10 seconds |
| Injury detection + hospital alert | Waits for bystander 112 call (5–15 min) | Auto-detected + alert ready in < 15 seconds |
| Ambulance green corridor | Manual radio coordination (3–7 min) | Route + signal suggestions in < 30 seconds |
| Multi-incident prioritisation | Officer judgment under pressure | YOLO-scored priority in < 10 seconds |
| **First public alert out** | **20–30 minutes** | **Under 2 minutes** |

---

## 14. Scope Boundaries

### In Scope
- Two cities: NYC (real data) and Chandigarh (synthetic, same schema)
- Single active incident per session per city
- Four LLM output types (signal, diversions, alerts, narrative) + CCTV summary section
- CCTV + YOLO visual intelligence: incident confirmation, injury detection, ambulance detection, anomaly detection, multi-incident prioritisation, hospital alert dispatch
- Multi-turn conversational chat with MongoDB persistence and CCTV context injection
- React + TypeScript frontend with Leaflet map
- FastAPI backend with WebSocket real-time updates
- MongoDB Atlas for all persistence including `cctv_events` collection
- Free LLM provider (Groq primary)

### Out of Scope
- Real-time API integration with live traffic sensors
- Autonomous signal actuation
- Multi-incident simultaneous management
- User authentication or role-based access
- Historical analytics or post-incident dashboards
- Mobile-responsive design

---

## 15. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM hallucinating street names | Medium | High | Pass OSM intersection names explicitly in prompt; instruct model to use only provided names |
| OSMnx graph download fails during demo | Low | High | Pre-cache `nyc_graph.graphml` and `chandigarh_graph.graphml` before demo day |
| Groq API down during demo | Low | High | Gemini Flash as fallback; switching is a one-line model change |
| Chandigarh synthetic data looks implausible | Medium | Medium | Use real OSM speed limits and real traffic engineering congestion factors in generator |
| MongoDB Atlas M0 storage overflow | Low | Medium | TTL index on `feed_snapshots` (2h expiry); only store last 3 full snapshots |
| react-leaflet polyline flicker on fast updates | Medium | Low | Diff segment IDs before re-rendering; only update changed polylines, not full layer |
| WebSocket disconnects during demo | Low | Medium | Auto-reconnect logic in `useWebSocket.ts` with 3s backoff |

---

*Report compiled for Smart Transportation Hackathon — Problem Statement 3*
*LLM Co-Pilot for Traffic Incident Command — Dual City: NYC + Chandigarh*
