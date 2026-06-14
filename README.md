# SENTINEL - Smart Traffic Co-Pilot

SENTINEL is an AI-driven command center for real-time traffic incident management and emergency response. It combines Large Language Models (LLMs), computer vision (YOLOv8), and real-time data streaming to provide traffic authorities with actionable intelligence, automated signal retiming suggestions, diversion routing, and visual incident confirmation.

The system was built for the Smart Transport PS3 Hackathon and supports dual-city operation with New York City (real-world open data) and Chandigarh (synthetic digital twin).

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Usage Guide](#usage-guide)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Team](#team)

---

## Overview

Urban traffic management faces three core challenges: detecting incidents in real time, assessing their severity quickly, and coordinating an effective response. SENTINEL addresses these by integrating multiple data sources into a unified command dashboard.

The system ingests live traffic speed data and collision records, runs them through an AI pipeline that detects anomalies and generates natural-language incident summaries, and presents everything on an interactive map interface. Traffic officers can query the system via a chat interface, inject simulated incidents for training or demonstration, and receive automated dispatch recommendations.

Two applications are provided: an **Officer Dashboard** (admin command center with map, chat, and controls) and a **Citizen Portal** (public-facing traffic alert view).

---

## Key Features

### AI-Powered Co-Pilot

- **Automated Decision Support:** Generates real-time suggestions for signal retiming, diversion routes, and emergency alerts based on detected incidents.
- **Incident Narratives:** Produces structured summaries of traffic conditions, contributing factors, and impact assessments using LLM inference.
- **Conversational Interface:** A context-aware chatbot that allows officers to query incident status, CCTV events, and historical data using natural language.

### Computer Vision Pipeline (CCTV + YOLOv8)

- **Incident Confirmation:** Automatically routes nearest camera feeds to a YOLOv8 inference pipeline to verify speed-drop incidents.
- **Injury and Ambulance Detection:** Identifies persons in distress and emergency vehicles to trigger priority "Green Corridor" routing.
- **Anomaly Detection:** Flags stationary vehicles on main carriageways, unusual speed patterns, and debris on road surfaces.

### Real-Time Command Dashboard

- **Interactive Traffic Map:** Live Leaflet-based visualization of road segments color-coded by speed, using NYC DOT and Chandigarh data feeds.
- **Collision Overlay:** Visualizes recent collision records to enrich incident context.
- **Multi-City Toggle:** Seamlessly switch between New York City and Chandigarh data sources.

### Emergency Dispatch

- **Hospital Alerting:** Automatically identifies the nearest hospital and generates dispatch alerts for confirmed injuries.
- **Priority Routing:** Computes optimal diversion routes and fastest-path guidance for first responders using A* search and OpenRouteService.

---

## System Architecture

### Data Ingestion Layer
- **NYC Open Data:** Fetches real-time DOT speed data and NYPD collision records.
- **Chandigarh Digital Twin:** Uses synthetic road segment data and collision records for simulation.
- **Feed Simulator:** Continuously processes incoming data and publishes updates via WebSocket.

### AI and Processing Layer
- **Incident Detector:** Analyzes speed drops and anomaly patterns to detect potential incidents.
- **LLM Co-Pilot:** Uses Groq (Llama 3) or alternate providers to generate incident narratives and chat responses.
- **VLM Service:** Routes CCTV frames to YOLOv8 for visual confirmation and object detection.

### Storage Layer
- **MongoDB Atlas:** Persistent storage for incidents, chat history, congestion zones, and social alerts.

### Presentation Layer
- **Officer Dashboard (frontend):** React + Leaflet admin interface with map, chat, and incident management.
- **Citizen Portal (user-app):** Public-facing React application with Mapbox for traffic alerts.

```
Data Sources (NYC OpenData / Chandigarh Synthetic)
    |
    v
Feed Simulator --> Incident Detector --> LLM Co-Pilot (Groq/Llama 3)
    |                                       |
    |                                       v
    |                                  MongoDB Atlas
    |                                       |
    v                                       v
Officer Dashboard (React + Leaflet)    AI Chat Interface
    |
    v
Citizen Portal (React + Mapbox)
```

---

## Tech Stack

- **Frontend (Admin):** React 19, TypeScript, Vite, Leaflet.js, Tailwind CSS 4, Zustand
- **Frontend (Citizen):** React 19, TypeScript, Vite, Mapbox GL, Tailwind CSS 4, Zustand
- **Backend:** Python 3.11, FastAPI, Motor (async MongoDB driver), uvicorn
- **AI/ML:** YOLOv8 (Ultralytics), Groq API (Llama 3.1), Gemini API, OpenRouter
- **Routing:** OpenRouteService, Mapbox Directions API
- **Database:** MongoDB Atlas
- **Observability:** Prometheus metrics, structured logging (structlog), distributed tracing
- **Infrastructure:** Circuit breakers, task queues, event bus, rate limiting (slowapi)

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- MongoDB Atlas cluster (recommended) or local MongoDB instance
- API keys for Groq (or alternate LLM provider), OpenRouteService, and optional services

### Installation

1. Clone the repository.

2. Create a Python virtual environment and install backend dependencies:

   ```bash
   cd backend
   python -m venv venv
   venv\Scripts\pip install -r requirements.txt
   ```

3. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

4. Install user-app dependencies:

   ```bash
   cd user-app
   npm install
   ```

5. Configure environment variables by creating `backend/.env`:

   ```env
   GROQ_API_KEY=your_groq_api_key
   ORS_API_KEY=your_openrouteservice_key
   MONGODB_URI=your_mongodb_atlas_connection_string
   NYC_APP_TOKEN=your_nyc_open_data_token
   ACTIVE_CITY=nyc
   ```

### Running the System

**Start all services:**

Run `start.bat` from the project root. This launches three services:

- **Backend API** on `http://localhost:8000`
- **Officer Dashboard** on `http://localhost:5173`
- **Citizen Portal** on `http://localhost:5174`

**Stop all services:**

Run `stop.bat` from the project root to terminate all processes.

---

## Usage Guide

### For Traffic Officers (Dashboard)

1. Open `http://localhost:5173` in a browser.
2. The main map displays road segments color-coded by current speed (green = normal, yellow = slow, red = congested).
3. Active incidents appear as markers on the map. Click a marker to view incident details, severity assessment, and AI-generated narrative.
4. Use the chat panel on the right to ask natural-language questions, for example:
   - "What incidents are active right now?"
   - "Show me the nearest hospital to the accident on NH-5."
   - "Suggest a diversion route for the blocked lane."
5. The congestion panel lists current congestion zones with severity levels.
6. Use the demo injection endpoint (`POST /api/demo/inject`) to simulate incidents for training or testing.

### For Citizens (Public Portal)

1. Open `http://localhost:5174` in a browser.
2. View nearby traffic alerts and incidents on a Mapbox-powered map.
3. Receive real-time notifications about incidents in your area.

### For Developers (API)

Refer to the API Reference section for available endpoints. The WebSocket endpoint at `ws://localhost:8000/ws/nyc` provides real-time traffic feed updates.

---

## API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/incidents` | GET | List all active traffic incidents |
| `/api/incidents/{id}` | GET | Get details of a specific incident |
| `/api/feed/current` | GET | Fetch current road segment speed data |
| `/api/collisions` | GET | List recent collision records |
| `/api/chat` | POST | Send a message to the AI co-pilot chat |
| `/api/llm/narrative` | POST | Generate an incident narrative for given context |
| `/api/demo/inject` | POST | Inject a simulated incident for testing |
| `/api/congestion/zones` | GET | List active congestion zones |
| `/api/social/alerts` | GET | Fetch social-media-sourced traffic alerts |
| `/ws/nyc` | WS | Real-time WebSocket stream for traffic updates |

---

## Project Structure

```
.
├── backend/                 FastAPI server and AI pipeline
│   ├── app.py               Main entry point and lifespan management
│   ├── config.py            Environment-based configuration
│   ├── db.py                MongoDB connection management
│   ├── core/                Infrastructure: logging, tracing, circuit breaker, task queue, event bus
│   ├── domain/              Domain logic: priority calculation, incident rules
│   ├── routers/             API route handlers (incidents, feed, chat, collisions, etc.)
│   ├── services/            Business logic: feed simulator, incident detector, LLM service, VLM, routing
│   ├── data/                Data files: road segments, intersections, congestion zones, signal baselines
│   ├── models/              ML schemas and model definitions
│   ├── tests/               Backend tests
│   └── static/              Static files served by FastAPI
├── frontend/                Officer Dashboard (React + TypeScript + Leaflet)
├── user-app/                Citizen Portal (React + TypeScript + Mapbox)
└── start.bat / stop.bat     Service launcher and shutdown scripts
```

---

## Team

- **Pranshul Soni** -- Backend Architect and API Lead
- **Dweep Desai** -- Frontend Developer and UI Lead
- **Mitansh Prajapati** -- AI and Computer Vision Engineer
- **Muskan Sharma** -- Chatbot and Data Preparation

Built for the Smart Transport PS3 Hackathon.
