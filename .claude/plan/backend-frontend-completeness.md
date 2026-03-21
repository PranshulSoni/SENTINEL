# Implementation Plan: Backend + Frontend Completeness Audit

## Problem Statement
Cross-referencing the project report (`smart_transport_ps3_report (5).md`) against the current codebase reveals several gaps in backend logic, frontend UI, and backend↔frontend integration. CCTV/YOLO features are **excluded** from this plan per user request.

## Approach
Fix gaps in 3 waves of parallel agents, prioritized by impact on demo functionality.

---

## Gap Analysis Summary

### 🔴 P0 — Critical (Breaks Core Demo)

| # | Gap | Location | Issue |
|---|-----|----------|-------|
| 1 | **LLM output format mismatch** | `backend/services/llm_service.py` → `parse_structured_output()` | Returns raw strings for `signal_retiming` and `diversions`, but frontend expects `{intersections: [...]}` and `{routes: [...]}` objects. Sidebar shows "Awaiting LLM intelligence..." permanently even when LLM output exists. |
| 2 | **Diversion route geometry not broadcast** | `backend/app.py` → `_on_incident()` | Routing service computes diversions but geometry is only passed to the LLM prompt — the frontend never receives GeoJSON coordinates for map overlay. |

### 🟡 P1 — Important (Demo Quality)

| # | Gap | Location | Issue |
|---|-----|----------|-------|
| 3 | **DiversionOverlay missing** | `frontend/src/components/map/` | Report specifies blue polyline overlay for diversion routes on the Leaflet map. Component doesn't exist. |
| 4 | **Social media alert not rendered** | `frontend/src/components/outputs/Sidebar.tsx` | `alerts.social_media` is parsed by backend and defined in types but not shown in UI. |
| 5 | **Collision markers not on map** | `frontend/src/components/map/TrafficMap.tsx` | `api.getNearbyCollisions()` is defined but never called. No collision data shown on map. |
| 6 | **No resolve incident UI** | Sidebar.tsx | `api.resolveIncident()` exists but no button to call it. |
| 7 | **No regenerate LLM button** | Sidebar.tsx | `api.regenerateLLM()` exists but no UI trigger. |
| 8 | **Feed snapshots not persisted** | `backend/app.py` → `_on_frame()` | Report says save to `feed_snapshots` collection for timeline reconstruction. Currently only broadcasts. |
| 9 | **Diversion routes not persisted** | `backend/app.py` → `_on_incident()` | Report says save to `diversion_routes` collection. Currently discarded after LLM prompt. |

### 🟢 P2 — Nice to Have

| # | Gap | Location | Issue |
|---|-----|----------|-------|
| 10 | **Chat history not loaded on mount** | `frontend/src/components/layout/ChatPanel.tsx` | Only session messages shown; should load from DB. |
| 11 | **APPLY ALL TIMINGS / ACTIVATE ROUTE buttons** | Sidebar.tsx | Buttons have no click handlers. Add visual feedback (toast/confirmation). |

---

## Implementation Steps

### Wave 1 — Backend Fixes (2 parallel agents)

#### Agent A: LLM Output Parser Enhancement
**Files:** `backend/services/llm_service.py`

Enhance `parse_structured_output()` to produce structured objects:

```python
# signal_retiming: Parse intersection names + timing numbers from LLM text
{
  "signal_retiming": {
    "intersections": [
      {
        "name": "W 34th St & 7th Ave",
        "current_ns_green": 45,
        "recommended_ns_green": 90,
        "current_ew_green": 30,
        "recommended_ew_green": 20,
        "reasoning": "Extend outflow green..."
      }
    ],
    "raw_text": "original text..."
  }
}

# diversions: Parse route names + paths from LLM text
{
  "diversions": {
    "routes": [
      {
        "priority": 1,
        "name": "Diversion A",
        "path": ["10th Ave", "W 42nd St", "9th Ave"],
        "estimated_absorption_pct": 60,
        "activate_condition": "immediate"
      }
    ],
    "raw_text": "original text..."
  }
}

# alerts: Already structured correctly (vms, radio, social_media)
```

Use regex to extract intersections with timing values and route sequences from the LLM's natural language. If parsing fails, wrap raw text in the structured format with fallback values.

#### Agent B: App Pipeline + Persistence Fixes
**Files:** `backend/app.py`

1. **Save feed snapshots to DB** — In `_on_frame()`, save every Nth frame (every 6th = once per 30s) to `feed_snapshots` collection
2. **Save diversion routes to DB** — In `_on_incident()`, save computed diversions to `diversion_routes` collection
3. **Broadcast diversion geometry** — Add a new WebSocket message type `diversion_routes` with GeoJSON coordinates for map overlay
4. **Include diversion data in llm_output broadcast** — Add `diversion_geometry` field

### Wave 2 — Frontend Fixes (2 parallel agents)

#### Agent C: Map Enhancements (DiversionOverlay + Collisions)
**Files:** 
- `frontend/src/components/map/TrafficMap.tsx` — Add DiversionOverlay + collision markers inline
- `frontend/src/store/index.ts` — Add diversionRoutes state + collisions state
- `frontend/src/hooks/useWebSocket.ts` — Handle `diversion_routes` message type

Add:
- Blue polyline overlay when diversion routes arrive via WebSocket
- Small orange markers for nearby collisions (fetched on incident detection)
- Store fields for diversion geometry and collision data

#### Agent D: Sidebar + ChatPanel Enhancements  
**Files:**
- `frontend/src/components/outputs/Sidebar.tsx` — Add social media alert, resolve button, regenerate button
- `frontend/src/components/layout/ChatPanel.tsx` — Load chat history on mount
- `frontend/src/types/index.ts` — Add any missing types

Add:
- Social media alert section (same style as VMS/Radio)
- "RESOLVE INCIDENT" button calling `api.resolveIncident()`
- "REGENERATE ANALYSIS" button calling `api.regenerateLLM()`
- Load chat history from backend on component mount
- Visual feedback on button clicks (brief state change)

### Wave 3 — Integration Verification
- Start backend, verify LLM output format
- Start frontend, verify sidebar renders structured data
- Test full pipeline: feed → incident → LLM → sidebar + map

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/services/llm_service.py` | Modify | Enhance parse_structured_output() to produce typed objects |
| `backend/app.py` | Modify | Add feed snapshot persistence, diversion persistence + broadcast |
| `frontend/src/components/map/TrafficMap.tsx` | Modify | Add diversion polylines + collision markers |
| `frontend/src/components/outputs/Sidebar.tsx` | Modify | Add social media, resolve, regenerate buttons |
| `frontend/src/components/layout/ChatPanel.tsx` | Modify | Load chat history on mount |
| `frontend/src/store/index.ts` | Modify | Add diversionRoutes + collisions state |
| `frontend/src/hooks/useWebSocket.ts` | Modify | Handle diversion_routes message |
| `frontend/src/types/index.ts` | Modify | Add DiversionGeometry type |

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| LLM text parsing unreliable | Wrap in try/catch; fallback to raw_text in structured envelope |
| Diversion GeoJSON too large for WebSocket | Simplify coordinates (reduce precision to 5 decimals) |
| Feed snapshot DB writes slow down feed loop | Only persist every 6th frame (30s interval) |
