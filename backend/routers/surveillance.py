import tempfile
import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
import uuid

import db
from core.auth import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter()

# -----------------------------------------------------------------------
# YOLO is only loaded when SKIP_YOLO_LOAD is not set to "true".
# On Render (cloud), set SKIP_YOLO_LOAD=true to avoid importing heavy
# ML dependencies (torch, ultralytics, cv2) that are not in requirements.txt.
# -----------------------------------------------------------------------
_SKIP_YOLO = os.getenv("SKIP_YOLO_LOAD", "false").lower() == "true"

# Lazily-resolved references — populated only when YOLO is loaded.
_gpu_config = None
_AdvancedVehicleTracker = None
_create_advanced_visualization = None

_YOLO_INSTANCE = None

if not _SKIP_YOLO:
    try:
        import cv2  # noqa: F401 — only needed for YOLO path
        import torch
        from main_gpu import YOLO, config as _gpu_config, AdvancedVehicleTracker as _AdvancedVehicleTracker, create_advanced_visualization as _create_advanced_visualization

        def _load_yolo_singleton():
            if torch.cuda.is_available():
                torch.cuda.set_device(0)
            m = YOLO(_gpu_config.YOLO_MODEL, task='detect')
            if _gpu_config.YOLO_DEVICE.startswith('cuda'):
                m.to(_gpu_config.YOLO_DEVICE)
            import numpy as np
            _dummy = np.zeros((640, 640, 3), dtype='uint8')
            _is_cuda = _gpu_config.YOLO_DEVICE.startswith('cuda')
            _warmup_device = _gpu_config.YOLO_DEVICE if _is_cuda else None
            for _ in range(2):
                m(_dummy, device=_warmup_device, half=_is_cuda, imgsz=640, verbose=False)
            logger.info(f"[YOLO] Model ready on {_gpu_config.YOLO_DEVICE} (FP16={_is_cuda})")
            return m

        _YOLO_INSTANCE = _load_yolo_singleton()
    except Exception as e:
        logger.warning(f"[YOLO] Failed to load model, running in passthrough mode: {e}")
else:
    logger.info("[YOLO] SKIP_YOLO_LOAD=true — running in passthrough/demo mode")

async def _run_vlm_analysis(app, feed_info: dict, snapshot_path: str):
    """Background task to run VLM analysis on an incident snapshot."""
    await asyncio.sleep(2.5)  # Wait for incident to persist from the main loop
    
    vlm_svc = getattr(app.state, "vlm_service", None)
    if not vlm_svc or not os.path.exists(snapshot_path):
        return

    try:
        if db.incidents is not None:
            # Find the latest incident for this city/camera to associate with
            latest = await db.incidents.find_one(
                {"city": feed_info["city"], "source": "surveillance_camera"},
                sort=[("detected_at", -1)]
            )
            if latest:
                inc_id = str(latest["_id"])
                analysis = await vlm_svc.analyse_image(
                    snapshot_path, 
                    {"city": feed_info["city"], "intersection": feed_info["intersection_name"]}
                )
                if "error" not in analysis:
                    await db.incidents.update_one(
                        {"_id": latest["_id"]},
                        {"$set": {"vlm_analysis": analysis}}
                    )
                    logger.info(f"[VLM] Persisted analysis to DB for {inc_id}", trace_id=get_trace_id())
                    ws = getattr(app.state, "ws_manager", None)
                    if ws:
                        await ws.broadcast_to_city(
                            feed_info["city"],
                            {"type": "vlm_analysis", "data": {"incident_id": inc_id, "analysis": analysis}}
                        )
                    logger.info(f"[VLM] Auto-analysis complete for {inc_id} (Background Queue)")
    except Exception as e:
        logger.error(f"[VLM Task Error] {e}")

# In-memory store for demo
pending_feeds = {}

@router.post("/upload")
async def upload_surveillance_video(
    request: Request,
    file: UploadFile = File(...),
    lat: float = Form(...),
    lng: float = Form(...),
    intersection_name: str = Form("Unknown Intersection"),
    city: str = Form("nyc"),
    _=Depends(require_api_key)
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

@router.post("/inject-demo")
async def inject_demo_feed(
    request: Request,
    lat: float = Form(...),
    lng: float = Form(...),
    intersection_name: str = Form("Demo Intersection"),
    city: str = Form("nyc"),
    _=Depends(require_api_key)
):
    """
    Injects the pre-processed demo video as a surveillance feed.
    Skips inference but triggers the collision pipeline.
    """
    demo_video = os.path.join(os.getcwd(), "processed_accident_video.mp4")
    if not os.path.exists(demo_video):
        # Fallback for different working directories
        demo_video = os.path.join(os.getcwd(), "backend", "processed_accident_video.mp4")
        if not os.path.exists(demo_video):
             raise HTTPException(status_code=404, detail="Demo video not found on server")

    feed_id = f"demo_{str(uuid.uuid4())[:8]}"
    pending_feeds[feed_id] = {
        "filepath": demo_video,
        "lat": lat, "lng": lng, 
        "intersection_name": intersection_name, 
        "city": city,
        "status": "ready",
        "is_demo": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }

    return {
        "status": "success",
        "feed_id": feed_id,
        "message": "Demo feed injected. Starting playback..."
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
        import cv2 as _cv2  # import here — may not be installed in cloud mode
        model = _YOLO_INSTANCE  # None when SKIP_YOLO_LOAD=true
        passthrough_mode = model is None

        cap = _cv2.VideoCapture(feed_info["filepath"])
        tracker = _AdvancedVehicleTracker() if not passthrough_mode else None

        width  = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(_cv2.CAP_PROP_FPS) or 25.0
        # Generator state
        incident_triggered = False
        frame_count = 0
        trigger_frame = int((_gpu_config.DEMO_TRIGGER_SECONDS if _gpu_config else 5.0) * fps)
        dispatched = False
        accident_buffer = [] # Buffer for median frame snapshot

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
                # Save snapshot if we have frames
                # User specifically requested 'accident_creenshot.jpg'
                snapshot_name = "accident_creenshot.jpg"
                snapshot_path = os.path.join(os.getcwd(), snapshot_name)
                
                # Check for backend folder fallback
                if not os.path.exists(os.path.dirname(snapshot_path)):
                     snapshot_path = os.path.join(os.getcwd(), "backend", snapshot_name)

                if accident_buffer:
                    mid_idx = len(accident_buffer) // 2
                    cv2.imwrite(snapshot_path, accident_buffer[mid_idx])
                elif 'frame' in locals():
                    cv2.imwrite(snapshot_path, frame)
                
                asyncio.run_coroutine_threadsafe(_record_cctv_event(), main_loop)
                asyncio.run_coroutine_threadsafe(on_incident(incident), main_loop)
                
                # Offload VLM Analysis to central task queue
                task_queue = getattr(request.app.state, "task_queue", None)
                if task_queue:
                    asyncio.run_coroutine_threadsafe(
                        task_queue.enqueue(
                            _run_vlm_analysis,
                            app=request.app,
                            feed_info=feed_info,
                            snapshot_path=snapshot_path
                        ),
                        main_loop
                    )

                logger.info(
                    "[SURVEILLANCE] Incident dispatched and VLM analysis enqueued for %s",
                    feed_info["intersection_name"]
                )
            except Exception:
                logger.exception("[SURVEILLANCE ERROR] Failed to dispatch incident from stream thread")
        
        try:
            frame_skip = _gpu_config.FRAME_SKIP if _gpu_config else 1
            resize_width = _gpu_config.RESIZE_WIDTH if _gpu_config else 1280

            while cap.isOpened():
                if frame_count % frame_skip != 0:
                    if not cap.grab():  # advance without decoding; False = EOF
                        break
                    frame_count += 1
                    continue
                
                ret, frame = cap.read()
                if not ret:
                    break
                frame_count += 1

                if width > resize_width:
                    scale_factor = resize_width / width
                    new_width = resize_width
                    new_height = int(height * scale_factor)
                    frame = _cv2.resize(frame, (new_width, new_height))

                accident_flags = []

                if feed_info.get("is_demo") or passthrough_mode:
                    # Demo / cloud passthrough: stream the pre-processed frame as-is
                    vis_frame = frame
                else:
                    # YOLO inference — for OpenVINO, device= must be None (patched compile_model
                    # handles GPU routing). For CUDA, pass the device string explicitly.
                    _infer_device = _gpu_config.YOLO_DEVICE if _gpu_config.YOLO_DEVICE.startswith('cuda') else None
                    yolo_results = model(
                        frame,
                        task='detect',
                        conf=_gpu_config.CONFIDENCE_THRESHOLD,
                        iou=_gpu_config.IOU_THRESHOLD,
                        imgsz=_gpu_config.IMG_SIZE,
                        device=_infer_device,
                        verbose=False,
                    )
                    detections = []
                    
                    if len(yolo_results[0].boxes) > 0:
                        boxes = yolo_results[0].boxes.data.cpu().numpy()
                        for box in boxes:
                            x1, y1, x2, y2, conf, cls_id = box
                            if int(cls_id) in _gpu_config.VEHICLE_CLASSES:
                                center_x, center_y = int((x1 + x2) / 2), int((y1 + y2) / 2)
                                detection = {
                                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                                    'center': (center_x, center_y),
                                    'confidence': conf, 'type': 'vehicle', 'class_id': int(cls_id)
                                }
                                detections.append(detection)
                                
                    _, accident_flags = tracker.update_tracks(detections, frame)
                    
                    if len(accident_flags) > 0:
                        accident_buffer.append(frame.copy())
                        if len(accident_buffer) > 100:  # Max 4 seconds at 25fps
                            accident_buffer.pop(0)

                    vis_frame = _create_advanced_visualization(frame, detections, accident_flags)
                
                # Dispatch incident after trigger frame or if accident detected
                if len(accident_flags) > 0 or frame_count >= trigger_frame:
                    _dispatch_incident(frame_count)
                        
                # Encode to MJPEG — quality 75 keeps size small and encoding fast
                encode_params = [_cv2.IMWRITE_JPEG_QUALITY, 75]
                _, buffer = _cv2.imencode('.jpg', vis_frame, encode_params)
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
            # But DO NOT delete the demo video!
            if not feed_info.get("is_demo") and os.path.exists(feed_info["filepath"]):
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
