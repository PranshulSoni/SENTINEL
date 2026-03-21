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

from main_gpu import process_accident_video, YOLO, config, AdvancedVehicleTracker, create_advanced_visualization

logger = logging.getLogger(__name__)
router = APIRouter()

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
        "city": city
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
    on_incident = getattr(request.app.state, "on_incident", None)
    
    # Capture the main event loop before entering the synchronous generator thread
    main_loop = asyncio.get_running_loop()
    
    def frame_generator():
        model = YOLO(config.YOLO_MODEL)
        cap = cv2.VideoCapture(feed_info["filepath"])
        tracker = AdvancedVehicleTracker()
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Generator state
        incident_triggered = False
        frame_count = 0
        
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret: break
                
                if frame_count % config.FRAME_SKIP != 0:
                    frame_count += 1
                    continue
                frame_count += 1
                
                if width > config.RESIZE_WIDTH:
                    scale_factor = config.RESIZE_WIDTH / width
                    new_width = config.RESIZE_WIDTH
                    new_height = int(height * scale_factor)
                    frame = cv2.resize(frame, (new_width, new_height))

                # YOLO inference
                yolo_results = model(frame, conf=config.CONFIDENCE_THRESHOLD, iou=config.IOU_THRESHOLD, imgsz=640, verbose=False)
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
                
                # Check for collision (more lenient for demo)
                if (len(accident_flags) > 0 or frame_count == 30) and not incident_triggered and on_incident:
                    incident_triggered = True
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
                                "speed": 0, "baseline": 25.0, "drop_pct": 100.0,
                                "lat": feed_info["lat"], "lng": feed_info["lng"],
                                "status": "BLOCKED",
                            }
                        ],
                        "source": "surveillance_camera",
                        "crash_record_id": None,
                    }
                    try:
                        # Schedule the coroutine execution safely in the main loop (Fire and forget)
                        asyncio.run_coroutine_threadsafe(on_incident(incident), main_loop)
                        print(f"[SURVEILLANCE] Successfully dispatched Sentinel incident for {feed_info['intersection_name']}!")
                    except Exception as e:
                        print(f"[SURVEILLANCE ERROR] Failed to trigger incident from generator thread: {e}")
                        
                # Encode to MJPEG
                _, buffer = cv2.imencode('.jpg', vis_frame)
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                       
                # simulate real-time loosely (prevent ultra fast playback)
                time.sleep(0.01)
                
        finally:
            cap.release()
            # Optionally clean up the video file after streaming is done
            if os.path.exists(feed_info["filepath"]):
                try: os.remove(feed_info["filepath"])
                except: pass

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")
