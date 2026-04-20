# SENTINEL

SENTINEL is a traffic incident response and traffic-operations platform built around three running surfaces:

- a FastAPI backend
- an operator dashboard
- a citizen-facing app

The current implementation supports two city contexts, `nyc` and `chandigarh`. It ingests live or cached traffic data, detects congestion, accepts incident reports, processes surveillance uploads, computes blocked and alternate routes, generates operator guidance, and pushes live updates to both frontends over city-scoped WebSockets.

## What SENTINEL Does

SENTINEL is designed to help operators respond to road incidents while keeping public-facing traffic information in sync.

In the current codebase, the live system handles:

- traffic-feed replay and city switching
- congestion detection from sustained low-speed traffic clusters
- incident intake from citizen reports, demo injection, and surveillance uploads
- blocked-route and safe-route generation
- operator assignment and queue management
- police-dispatch, resolve, dismiss, and alert-publish workflows
- incident-aware copilot chat with persisted history
- city-specific public alert delivery to the citizen app

## How The System Works

### 1. Traffic Feed

`backend/services/feed_simulator.py` loads traffic data for the selected city. Depending on availability, it uses live API data, cached CSV data, or synthetic demo frames. The backend processes frames on a timed loop and broadcasts the latest feed state to connected clients.

### 2. Congestion Detection

`backend/services/congestion_detector.py` watches for sustained low-speed clusters across nearby segments. When a zone is classified as congested, the backend stores it, computes alternates where needed, and broadcasts the updated zone to the relevant city room.

### 3. Incident Handling

The active incident entry points in the running app are:

- `POST /api/demo/inject-incident`
- `POST /api/incidents/report`
- surveillance processing under `/api/surveillance/*`

All of them feed into the shared backend incident pipeline. That flow persists the incident, assigns or queues an operator, computes blocked and alternate routes, generates LLM output, stores the result, and broadcasts updates to connected clients.

### 4. Routing

Routing is handled in `backend/services/routing_service.py`. The service uses OpenRouteService first, prefers local ORS containers when available, and falls back to internal graph-based logic when external routing is not usable. The result is route guidance that can still degrade gracefully in demo or failure scenarios.

### 5. Operator And Citizen Clients

Both frontends connect to the backend WebSocket endpoint at `/ws` and subscribe by city.

- The operator dashboard is the control console. It shows incidents, congestion, routes, CCTV upload controls, operator actions, LLM outputs, and public alert publishing.
- The citizen app is the public-facing client. It supports incident reporting, route viewing, social alert intake, and a simplified copilot experience.

## System Layout

```text
Operator Dashboard / Citizen App
              | 
         HTTP + WebSocket
              |
         FastAPI Backend
              |
   +----------+----------+----------+----------+
   |                     |                     |
 MongoDB             Routing                External Services
   |                 ORS / local fallback   NYC feed / LLM providers
   |
 Surveillance + incident + congestion state
```

## Main Components

### Backend

The backend contains the operational logic for incidents, routing, feed replay, congestion, surveillance, chat, and social alerting.

Key areas:

- `backend/app.py`: app startup, service wiring, shared incident pipeline, background feed loop, WebSocket coordination
- `backend/routers/`: mounted API routes for incidents, feed, collisions, chat, demo, congestion, surveillance, social, and WebSocket access
- `backend/services/`: feed replay, routing, congestion detection, collision lookups, operator queueing, prompt building, and LLM orchestration
- `backend/db.py`: MongoDB connection setup, collection handles, and indexes
- `backend/data/`: local seed data and cached datasets used for replay, routing context, and demo scenarios

### Operator Dashboard

The operator dashboard in `frontend/` is a React/Vite app used as the operations console.

It includes:

- a live map built with Leaflet
- incident action controls
- operator session switching
- congestion and route overlays
- police-dispatch actions
- copilot chat
- CCTV upload and feed viewing
- social alert publishing

### Citizen App

The citizen app in `user-app/` is a separate React/Vite client with a mobile-style layout.

It includes:

- incident reporting
- route viewing
- live incident updates
- social alert intake
- copilot chat
- a public map built with Mapbox GL

### Routing Infrastructure

The `routing/` directory contains Docker Compose configuration for two local ORS deployments:

- Chandigarh on `8081`
- NYC on `8082`

These containers allow local route generation during demos and development, while the backend still maintains fallback behavior when routing services are unavailable.

## Technology Stack

### Backend stack

- FastAPI and Uvicorn for the API and WebSocket server
- MongoDB with Motor/PyMongo for persistence
- Pydantic and `pydantic-settings` for schema and configuration handling
- HTTPX for external API calls
- Pandas and NumPy for feed replay/data processing

### Frontend stack

- React 19 with TypeScript and Vite in both frontends
- Zustand for client state
- Leaflet in the operator dashboard
- Mapbox GL in the citizen app
- Tailwind CSS v4 for styling

### AI and vision stack

- Groq, Gemini, and OpenRouter as the LLM fallback chain
- PyTorch, Ultralytics YOLOv8, and OpenVINO for surveillance inference paths

## Repository Structure

| Path | Purpose |
| --- | --- |
| `backend/` | FastAPI backend, routers, services, models, and data logic |
| `backend/data/` | Seeded road data, congestion zones, cached traffic data, collision data |
| `backend/routers/` | Mounted API surface |
| `backend/services/` | Feed, routing, congestion, queueing, LLM, and surveillance support logic |
| `frontend/` | Operator dashboard |
| `user-app/` | Citizen-facing application |
| `routing/` | Local ORS setup |
| `run.bat`, `start.bat`, `stop.bat` | Windows launch and stop scripts |

## Running Locally

The repo already includes Windows scripts for local development and demos.

### Expected ports

- Backend API: `http://localhost:8000`
- Operator dashboard: `http://localhost:5173`
- Citizen app: `http://localhost:5174`
- Local ORS Chandigarh: `http://localhost:8081`
- Local ORS NYC: `http://localhost:8082`

### Scripts

- `run.bat`: starts backend, both frontends, and can start local ORS containers
- `start.bat`: similar startup flow with the frontend kept in the active terminal
- `stop.bat`: stops backend windows and local ORS containers

## Current Runtime Scope

The README above describes the live mounted flows in the app. There are also prototype or partially wired modules in the repository, but they are not the main runtime path. For interview preparation or a deeper module-by-module breakdown, see [`explanation.md`](./explanation.md).
