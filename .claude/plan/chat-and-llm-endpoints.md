# Implementation Plan: Chat & LLM Intelligence Endpoints

## Problem
The chat panel says "Chat endpoint not yet implemented on backend." The backend is missing:
1. **Chat API** — no `POST /api/chat` endpoint for conversational LLM interaction
2. **Manual LLM trigger** — LLM pipeline only fires on auto-detected incidents, no manual re-trigger
3. **Chat history** — `chat_history` collection defined in db.py but never written to

## Solution

### Backend Changes (3 files)

#### 1. CREATE `backend/routers/chat.py`
- `POST /api/chat` — Accepts `{message, incident_id?}`, builds chat context (current incident + segments + collision history), calls LLM, saves to chat_history collection, returns response
- `GET /api/chat/history/{incident_id}` — Retrieves chat history for an incident
- `DELETE /api/chat/history/{incident_id}` — Clears chat history

#### 2. MODIFY `backend/app.py`
- Import and include chat router: `app.include_router(chat.router, prefix="/api/chat", tags=["chat"])`

#### 3. CREATE `backend/routers/llm.py` (optional but useful)
- `POST /api/llm/regenerate/{incident_id}` — Manually re-trigger the full LLM pipeline for an existing incident

### Frontend Changes (1 file)

#### 4. MODIFY `frontend/src/services/api.ts`
- Replace placeholder `sendChat` with real `POST /api/chat` call
- Add `getChatHistory(incidentId)` and `clearChatHistory(incidentId)`

## Implementation Steps
1. Create `backend/routers/chat.py` with full chat endpoint
2. Create `backend/routers/llm.py` with regenerate endpoint  
3. Update `backend/app.py` to include both new routers
4. Update `frontend/src/services/api.ts` to call real endpoints
5. Verify server starts and test endpoints
