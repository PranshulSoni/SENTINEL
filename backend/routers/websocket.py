"""WebSocket broadcast endpoint."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("")
async def websocket_endpoint(websocket: WebSocket):
    """Accept a WebSocket connection and keep it alive for broadcasts."""
    manager = websocket.app.state.ws_manager
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; received messages reserved for future chat
            data = await websocket.receive_text()
            logger.debug(f"WS received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
