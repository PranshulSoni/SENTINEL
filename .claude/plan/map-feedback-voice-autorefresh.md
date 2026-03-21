# Implementation Plan: Map Enhancement + Officer Feedback + Voice + Auto-Refresh

## Problem Statement
5 features needed to bring SENTINEL to production quality:
1. Map lacks street names/labels (uses `dark_nolabels` tile)
2. No approve/reject UI for individual LLM suggestions
3. Need best Gemini model for voice assistant integration
4. LLM analysis runs ONCE — never refreshes as incident evolves
5. Everything must be committed and pushed

## Technical Solution

### Feature 1: Map Street Labels
**Current**: `https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png`
**Fix**: Switch to CartoDB Dark Matter WITH labels: `dark_all` variant (keeps dark theme, adds street names, POIs, building labels)
**Alternative**: CartoDB Voyager for full-color labels if dark theme isn't required

**Files**: `frontend/src/components/map/TrafficMap.tsx` — change TileLayer URL only

---

### Feature 2: Officer Approve/Reject per LLM Suggestion
**Current**: Only "APPLY ALL TIMINGS" button + "REGENERATE" button. No individual feedback.
**Fix**:
- Add Accept ✓ / Reject ✗ buttons next to EACH:
  - Signal retiming recommendation (per intersection)
  - Diversion route (per route)
  - Public alert draft (per channel: VMS, Radio, Social)
- Track feedback in Zustand store + persist to MongoDB `llm_feedback` collection
- When "REGENERATE" is clicked, include rejected items in the LLM prompt as context
- Backend: new `/api/incidents/{id}/llm-feedback` endpoint
- Backend: `prompt_builder.py` adds rejected suggestions section to prompt

**Data Model**:
```python
# MongoDB: llm_feedback collection
{
  incident_id: str,
  category: "signal" | "diversion" | "alert",
  item_name: str,  # e.g., "W 34th St & 7th Ave" or "Route #1"
  action: "accepted" | "rejected",
  operator: str,
  reason: str | None,  # Optional rejection reason
  timestamp: datetime
}
```

**Frontend Component Changes**:
- Each signal recommendation row gets ✓/✗ buttons
- Each diversion route gets ✓/✗ buttons
- Each alert section gets ✓/✗ buttons
- Visual states: pending (default), accepted (green), rejected (red strikethrough)
- Rejected items feed into regeneration context

---

### Feature 3: Best Gemini Model for Voice
**Current**: `gemini-2.0-flash` in llm_service.py, `gemini-2.5-flash` in gemini_query.py
**Analysis**: The voice pipeline already exists:
  - Frontend records audio via MediaRecorder API
  - Sends base64 audio to backend
  - `gemini_query.py` uses `gemini-2.5-flash` for multimodal (audio+text)
**Fix**:
  - Use `gemini-2.5-flash` for voice transcription (already multimodal-capable, fastest for audio)
  - Update `chat.py` to detect audio messages and route to Gemini multimodal
  - Ensure the transcribed text is written to chat AND processed as a command
  - Add visual feedback: "Transcribing..." state while processing voice

**Best Gemini Models by Use Case**:
| Use Case | Model | Why |
|----------|-------|-----|
| Voice transcription | `gemini-2.5-flash` | Native audio understanding, fastest |
| Incident analysis | `gemini-2.0-flash` | Good enough for text, cheaper |
| Complex reasoning | `gemini-2.5-pro` | Best quality but slower/expensive |

**Recommendation**: Keep `gemini-2.5-flash` for voice (already configured in gemini_query.py), ensure chat router uses it for audio messages.

---

### Feature 4: Auto-Refresh LLM Analysis
**Current**: LLM called ONCE per incident in `_on_incident()`. No re-analysis.
**Fix**:
- Add tick counter in `_on_frame()` callback
- Every N ticks (configurable, default 12 = ~60s at 5s intervals), check:
  - Is there an active incident?
  - Has traffic state changed significantly? (compare avg speed of segments near incident)
- If significant change detected: re-trigger LLM analysis with updated segments
- Broadcast updated `llm_output` via WebSocket (frontend already handles this)
- Cap max re-analyses per incident (e.g., 5) to avoid API cost explosion

**Change Detection Logic**:
```python
# In _on_frame:
if active_incident and ticks_since_last_llm >= LLM_REFRESH_INTERVAL:
    current_avg_speed = mean(seg["speed"] for seg in nearby_segments)
    if abs(current_avg_speed - last_llm_avg_speed) > SPEED_CHANGE_THRESHOLD:
        asyncio.create_task(_refresh_llm_analysis(active_incident, segments))
        ticks_since_last_llm = 0
        last_llm_avg_speed = current_avg_speed
```

**Frontend**: No changes needed — store already handles `llm_output` WebSocket messages and updates UI automatically.

---

## Implementation Steps

### Step 1: Map Tile Upgrade
- File: `frontend/src/components/map/TrafficMap.tsx`
- Change TileLayer URL from `dark_nolabels` to `dark_all`
- Update attribution if needed
- **Deliverable**: Street names, building labels, POIs visible on map

### Step 2: Backend — LLM Feedback System
- File: `backend/db.py` — Add `llm_feedback` collection + index
- File: `backend/routers/incidents.py` — Add `POST /{id}/llm-feedback` endpoint
- File: `backend/services/prompt_builder.py` — Add rejected suggestions section to prompts
- File: `backend/app.py` — Seed `llm_feedback` collection in lifespan
- **Deliverable**: Feedback stored in DB, rejections included in regeneration prompts

### Step 3: Frontend — Approve/Reject UI
- File: `frontend/src/services/api.ts` — Add `submitLLMFeedback()` method
- File: `frontend/src/store/index.ts` — Add feedback tracking state
- File: `frontend/src/components/outputs/Sidebar.tsx` — Add ✓/✗ buttons per suggestion
- **Deliverable**: Officers can accept/reject individual suggestions

### Step 4: Voice Assistant Enhancement
- File: `backend/routers/chat.py` — Detect audio messages, route to Gemini multimodal
- File: `backend/services/llm_service.py` — Add voice transcription method using gemini-2.5-flash
- File: `frontend/src/components/layout/ChatPanel.tsx` — Add "Transcribing..." state
- **Deliverable**: Voice → text → chatbot response, fully working

### Step 5: Auto-Refresh LLM Analysis
- File: `backend/app.py` — Add tick counter + change detection in `_on_frame`
- File: `backend/app.py` — Add `_refresh_llm_analysis()` function
- File: `backend/services/prompt_builder.py` — Add "progressive update" context to prompt
- **Deliverable**: LLM re-analyzes every ~60s when traffic changes significantly

### Step 6: Verify + Commit + Push
- Run Python syntax check on all modified backend files
- Run TypeScript type check on frontend
- Git add, commit with descriptive message, push

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `frontend/src/components/map/TrafficMap.tsx` | Modify | Switch tile to `dark_all` for street labels |
| `frontend/src/components/outputs/Sidebar.tsx` | Modify | Add ✓/✗ buttons per LLM suggestion |
| `frontend/src/store/index.ts` | Modify | Add feedback state tracking |
| `frontend/src/services/api.ts` | Modify | Add `submitLLMFeedback()` API method |
| `frontend/src/components/layout/ChatPanel.tsx` | Modify | Add transcription loading state |
| `backend/routers/incidents.py` | Modify | Add LLM feedback endpoint |
| `backend/routers/chat.py` | Modify | Route audio to Gemini multimodal |
| `backend/services/llm_service.py` | Modify | Add voice transcription via gemini-2.5-flash |
| `backend/services/prompt_builder.py` | Modify | Add rejected suggestions + progressive update context |
| `backend/app.py` | Modify | Add tick counter + auto-refresh logic |
| `backend/db.py` | Modify | Add `llm_feedback` collection |

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Auto-refresh LLM costs | Cap at 5 re-analyses per incident, 60s minimum interval |
| Gemini audio API rate limits | Fallback: save audio, return "transcription unavailable" |
| Rejected feedback overloading prompt | Limit to last 5 rejections in prompt context |
| Voice latency | Show "Transcribing..." spinner, don't block UI |
| TypeScript type errors from new state | Use proper type definitions with `import type` |

## SESSION_ID (for /ccg:execute use)
- CODEX_SESSION: N/A (codeagent-wrapper not available)
- GEMINI_SESSION: N/A (codeagent-wrapper not available)
