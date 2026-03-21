"""WebSocket broadcast endpoint."""

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("")
async def websocket_endpoint(websocket: WebSocket, city: str = Query("nyc")):
    """Accept a WebSocket connection and keep it alive for broadcasts."""
    manager = websocket.app.state.ws_manager
    await manager.connect(websocket, city=city)
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"WS received: {data}")
            try:
                msg = json.loads(data)
                # Handle city switch messages from frontend
                if msg.get("type") == "switch_city":
                    new_city = msg.get("city", "nyc")
                    manager.switch_city(websocket, new_city)
                    logger.info(f"WebSocket switched to city: {new_city}")
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
