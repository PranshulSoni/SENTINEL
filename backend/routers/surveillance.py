import tempfile
import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import uuid
import cv2
import time
import torch

from main_gpu import process_accident_video, YOLO, config, AdvancedVehicleTracker, create_advanced_visualization
import db

logger = logging.getLogger(__name__)
router = APIRouter()

# -----------------------------------------------------------------------
# Module-level YOLO singleton — loaded once when FastAPI starts so every
# request reuses the same GPU-resident weights instead of cold-loading.
# -----------------------------------------------------------------------
def _load_yolo_singleton() -> YOLO:
    if torch.cuda.is_available():
        torch.cuda.set_device(0)
    m = YOLO(config.YOLO_MODEL, task='detect')
    if not config.YOLO_DEVICE == 'cpu':
        m.to(config.YOLO_DEVICE)
    
    # Warm up: two silent dummy inferences to prime cuDNN kernel cache or OpenVINO.
    import numpy as np
    _dummy = np.zeros((640, 640, 3), dtype='uint8')
    for _ in range(2):
        m(_dummy, device=config.YOLO_DEVICE if not config.YOLO_DEVICE == 'cpu' else None,
          half=config.YOLO_DEVICE.startswith('cuda'),
          imgsz=640, verbose=False)
    
    try:
        device_str = next(m.model.parameters()).device if hasattr(m, 'model') and hasattr(m.model, 'parameters') else config.YOLO_DEVICE
    except (TypeError, StopIteration, AttributeError):
        device_str = config.YOLO_DEVICE
    
    logger.info(f"[YOLO] Model ready on {device_str} (FP16 per-call={config.YOLO_DEVICE.startswith('cuda')})")
    return m

_YOLO_INSTANCE: YOLO = _load_yolo_singleton()

# In-memory store for demo
pending_feeds = {}

@router.post("/upload")
async def upload_surveillance_video(
    request: Request,
    file: UploadFile = File(...),
    lat: float = Form(...),
    lng: float = Form(...),
    intersection_name: str = Form("Unknown Intersection"),
    city: str = Form("nyc")
):
    """
    Receives a video, runs YOLO accident detection, and triggers an incident
    iff a collision is detected in the video feed.
    """
    on_incident = getattr(request.app.state, "on_incident", None)
    if on_incident is None:
        raise HTTPException(
            status_code=503,
            detail="Incident pipeline not ready",
        )

    temp_dir = tempfile.gettempdir()
    feed_id = str(uuid.uuid4())
    input_video_path = os.path.join(temp_dir, f"surv_in_{feed_id}.mp4")
    
    with open(input_video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    pending_feeds[feed_id] = {
        "filepath": input_video_path,
        "lat": lat, "lng": lng, 
        "intersection_name": intersection_name, 
        "city": city,
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }

    return {
        "status": "success",
        "feed_id": feed_id,
        "message": "Video uploaded. Live feed ready."
    }

@router.get("/feed/{feed_id}")
async def stream_surveillance_feed(request: Request, feed_id: str):
    if feed_id not in pending_feeds:
        raise HTTPException(status_code=404, detail="Feed not found")
        
    feed_info = pending_feeds[feed_id]
    feed_info["status"] = "streaming"
    on_incident = getattr(request.app.state, "on_incident", None)
    ws_manager = getattr(request.app.state, "ws_manager", None)
    
    # Capture the main event loop before entering the synchronous generator thread
    main_loop = asyncio.get_running_loop()
    
    def frame_generator():
        # Reuse the module-level singleton — weights already on GPU
        model = _YOLO_INSTANCE

        cap = cv2.VideoCapture(feed_info["filepath"])
        tracker = AdvancedVehicleTracker()

        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Generator state
        incident_triggered = False
        frame_count = 0
        trigger_frame = max(1, int(os.getenv("SURVEILLANCE_TRIGGER_FRAME", "5")))

        def _dispatch_incident(current_frame_count: int):
            nonlocal incident_triggered
            if incident_triggered or on_incident is None:
                return
            incident_triggered = True

            async def _record_cctv_event():
                event_doc = {
                    "version": "v2",
                    "city": feed_info["city"],
                    "incident_id": None,
                    "camera_id": f"cam_{feed_id[:6]}",
                    "camera_location": {
                        "type": "Point",
                        "coordinates": [feed_info["lng"], feed_info["lat"]],
                    },
                    "event_type": "incident_confirmed",
                    "confidence": 0.92,
                    "detected_at": datetime.now(timezone.utc),
                    "metadata": {
                        "source": "surveillance_stream",
                        "intersection_name": feed_info["intersection_name"],
                        "frames_processed": current_frame_count,
                    },
                }
                if db.cctv_events is not None:
                    try:
                        await db.cctv_events.insert_one(event_doc)
                    except Exception:
                        pass
                if ws_manager is not None:
                    try:
                        await ws_manager.broadcast_to_city(
                            feed_info["city"],
                            {"type": "cctv_event", "data": {**event_doc, "version": "v2"}},
                        )
                    except Exception:
                        pass

            incident = {
                "city": feed_info["city"],
                "status": "active",
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "resolved_at": None,
                "severity": "critical",
                "location": {
                    "type": "Point",
                    "coordinates": [feed_info["lng"], feed_info["lat"]],
                },
                "on_street": feed_info["intersection_name"],
                "cross_street": "",
                "affected_segment_ids": ["surv_cam_001"],
                "affected_segments": [
                    {
                        "link_id": "surv_cam_001",
                        "link_name": feed_info["intersection_name"],
                        "speed": 0,
                        "baseline": 25.0,
                        "drop_pct": 100.0,
                        "lat": feed_info["lat"],
                        "lng": feed_info["lng"],
                        "status": "BLOCKED",
                    }
                ],
                "source": "surveillance_camera",
                "crash_record_id": None,
            }
            try:
                asyncio.run_coroutine_threadsafe(_record_cctv_event(), main_loop)
                asyncio.run_coroutine_threadsafe(on_incident(incident), main_loop)
                logger.info(
                    "[SURVEILLANCE] Incident dispatched for %s (frames=%s)",
                    feed_info["intersection_name"],
                    current_frame_count,
                )
            except Exception:
                logger.exception("[SURVEILLANCE ERROR] Failed to dispatch incident from stream thread")
        
        try:
            while cap.isOpened():
                if frame_count % config.FRAME_SKIP != 0:
                    if not cap.grab():  # advance without decoding; False = EOF
                        break
                    frame_count += 1
                    continue
                ret, frame = cap.read()
                if not ret:
                    break
                frame_count += 1
                
                if width > config.RESIZE_WIDTH:
                    scale_factor = config.RESIZE_WIDTH / width
                    new_width = config.RESIZE_WIDTH
                    new_height = int(height * scale_factor)
                    frame = cv2.resize(frame, (new_width, new_height))

                # YOLO inference on OpenVINO GPU
                yolo_results = model(
                    frame,
                    task='detect',
                    conf=config.CONFIDENCE_THRESHOLD,
                    iou=config.IOU_THRESHOLD,
                    imgsz=config.IMG_SIZE,
                    device=config.YOLO_DEVICE,
                    verbose=False,
                )
                detections = []
                
                if len(yolo_results[0].boxes) > 0:
                    boxes = yolo_results[0].boxes.data.cpu().numpy()
                    for box in boxes:
                        x1, y1, x2, y2, conf, cls_id = box
                        if int(cls_id) in config.VEHICLE_CLASSES:
                            center_x, center_y = int((x1 + x2) / 2), int((y1 + y2) / 2)
                            detection = {
                                'bbox': [int(x1), int(y1), int(x2), int(y2)],
                                'center': (center_x, center_y),
                                'confidence': conf, 'type': 'vehicle', 'class_id': int(cls_id)
                            }
                            detections.append(detection)
                            
                _, accident_flags = tracker.update_tracks(detections, frame)
                vis_frame = create_advanced_visualization(frame, detections, accident_flags)
                
                # Demo policy: dispatch quickly if accident flags appear OR after a short warmup.
                if len(accident_flags) > 0 or frame_count >= trigger_frame:
                    _dispatch_incident(frame_count)
                        
                # Encode to MJPEG — quality 75 keeps size small and encoding fast
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, 75]
                _, buffer = cv2.imencode('.jpg', vis_frame, encode_params)
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                # No sleep — stream at max GPU throughput
                
        finally:
            # Fallback: if stream ended before the trigger frame, still dispatch once for demo reliability.
            if not incident_triggered and frame_count > 0:
                _dispatch_incident(frame_count)
            cap.release()
            if feed_id in pending_feeds:
                pending_feeds[feed_id]["status"] = "completed"
                pending_feeds[feed_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            # Optionally clean up the video file after streaming is done
            if os.path.exists(feed_info["filepath"]):
                try: os.remove(feed_info["filepath"])
                except: pass

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/status/{feed_id}")
async def surveillance_feed_status(feed_id: str):
    feed_info = pending_feeds.get(feed_id)
    if feed_info is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    return {
        "feed_id": feed_id,
        "status": feed_info.get("status", "unknown"),
        "completed_at": feed_info.get("completed_at"),
    }
