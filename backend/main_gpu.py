import os
import cv2
import numpy as np
import time
from datetime import datetime
from collections import deque
from ultralytics import YOLO

import warnings
import torch

warnings.filterwarnings('ignore')

# Force PyTorch to use the RTX 4050 exclusively and enable cuDNN auto-tuner
# (benchmark=True caches the fastest kernel for fixed 640×640 inputs)
os.environ.setdefault('CUDA_VISIBLE_DEVICES', '0')
torch.backends.cudnn.benchmark = True
torch.backends.cudnn.deterministic = False

# =====================================================================
# GPU TOGGLE: Set to True for Intel/OpenVINO GPU, False for NVIDIA CUDA
# =====================================================================
openvinoGPU = True  # Toggle this to switch between OpenVINO and CUDA
# =====================================================================

if openvinoGPU:
    # -----------------------------------------------------------------
    # OPTIMIZED OPENVINO GPU MODE
    # -----------------------------------------------------------------
    import openvino as ov
    print("\n[INIT] OpenVINO Mode Selected. Applying Hardware Acceleration Patch...")
    
    original_compile = ov.Core.compile_model
    def patched_compile(self, model, device_name=None, config=None):
        print(">> Intercepted AutoBackend. Forcing compile_model on 'GPU' <<")
        return original_compile(self, model, "GPU", config)
    
    # Apply runtime patch for Ultralytics OpenVINO backend
    ov.Core.compile_model = patched_compile
else:
    # -----------------------------------------------------------------
    # OPTIMIZED NVIDIA CUDA GPU MODE
    # -----------------------------------------------------------------
    # Force PyTorch to use the primary GPU and enable cuDNN auto-tuner
    os.environ.setdefault('CUDA_VISIBLE_DEVICES', '0')
    torch.backends.cudnn.benchmark = True
    torch.backends.cudnn.deterministic = False
    
    try:
        if torch.cuda.is_available():
            torch.cuda.init()
            _ = torch.zeros(1, device='cuda')  # Establish CUDA context immediately
            _gpu_name = torch.cuda.get_device_name(0)
            print(f"\n[INIT] CUDA Mode Selected! Using NVIDIA GPU: {_gpu_name}")
            _CUDA_READY = True
        else:
            print("\n[INIT] CUDA selected but not available. Falling back to CPU.")
            _CUDA_READY = False
    except Exception as e:
        print(f"\n[INIT] CUDA initialization failed: {e}. Falling back to CPU.")
        _CUDA_READY = False

class AdvancedAccidentConfig:
    """Advanced configuration for accident detection system."""

    if openvinoGPU:
        YOLO_MODEL = 'yolov8m_openvino_model/'
        YOLO_DEVICE = 'GPU'
    else:
        YOLO_MODEL = 'yolov8m.pt'
        YOLO_DEVICE = 'cuda:0' if torch.cuda.is_available() else 'cpu'

    ACCIDENT_MODEL_PATH = 'accident_detection_model.h5'

    VEHICLE_CLASSES = [2, 3, 5, 7]  # Car, motorcycle, bus, truck
    CONFIDENCE_THRESHOLD = 0.6
    IOU_THRESHOLD = 0.5

    SPEED_CHANGE_THRESHOLD = 0.7
    DIRECTION_CHANGE_THRESHOLD = 45
    COLLISION_DISTANCE = 50
    ACCIDENT_FRAMES_THRESHOLD = 10

    TRACKING_HISTORY = 30
    OPTICAL_FLOW_WINDOW = 5

    COLORS = {
        'normal': (0, 255, 0),
        'warning': (0, 255, 255),
        'accident': (0, 0, 255),
        'vehicle': (255, 0, 0)
    }
    FRAME_SKIP = 4   # process every 4th frame → ~7.5 frames/s at 30fps source, max GPU throughput
    RESIZE_WIDTH = 640
    IMG_SIZE = 640

config = AdvancedAccidentConfig()

class AdvancedVehicleTracker:
    """Advanced vehicle tracking with accident detection features."""
    def __init__(self):
        self.vehicles = {}
        self.track_history = {}
        self.accident_candidates = {}
        self.frame_count = 0
        
    def update_tracks(self, detections, frame):
        current_vehicles = {}
        accident_flags = []
        
        for det in detections:
            vehicle_id = self._assign_vehicle_id(det)
            
            if vehicle_id not in self.track_history:
                self.track_history[vehicle_id] = deque(maxlen=config.TRACKING_HISTORY)
            
            current_data = {
                'bbox': det['bbox'],
                'center': det['center'],
                'frame': self.frame_count,
                'speed': self._calculate_speed(vehicle_id, det['center']),
                'area': self._calculate_area(det['bbox'])
            }
            
            self.track_history[vehicle_id].append(current_data)
            current_vehicles[vehicle_id] = current_data
            
            accident_probability = self._assess_accident_risk(vehicle_id)
            if accident_probability > 0.7:
                accident_flags.append((vehicle_id, accident_probability))
        
        self.frame_count += 1
        return current_vehicles, accident_flags
    
    def _assign_vehicle_id(self, detection):
        center_x, center_y = detection['center']
        area = self._calculate_area(detection['bbox'])
        potential_id = f"{detection['type']}{int(center_x//50)}{int(center_y//50)}_{int(area//100)}"
        
        for vid, history in self.track_history.items():
            if len(history) > 0:
                last_pos = history[-1]['center']
                distance = np.sqrt((center_x - last_pos[0])**2 + (center_y - last_pos[1])**2)
                if distance < 100:  
                    return vid
        return potential_id
    
    def _calculate_speed(self, vehicle_id, current_center):
        if vehicle_id not in self.track_history or len(self.track_history[vehicle_id]) < 2:
            return 0
        history = list(self.track_history[vehicle_id])
        prev_center = history[-1]['center']
        distance = np.sqrt((current_center[0] - prev_center[0])**2 + 
                          (current_center[1] - prev_center[1])**2)
        return distance
    
    def _calculate_area(self, bbox):
        x1, y1, x2, y2 = bbox
        return (x2 - x1) * (y2 - y1)
    
    def _assess_accident_risk(self, vehicle_id):
        if vehicle_id not in self.track_history or len(self.track_history[vehicle_id]) < 5:
            return 0.0
        
        history = list(self.track_history[vehicle_id])
        risk_score = 0.0
        
        # Factor 1: Sudden speed reduction
        speeds = [entry['speed'] for entry in history]
        if len(speeds) >= 3:
            recent_speed = np.mean(speeds[-3:])
            older_speed = np.mean(speeds[:-3])
            if older_speed > 0 and recent_speed / older_speed < config.SPEED_CHANGE_THRESHOLD:
                risk_score += 0.4
        
        # Factor 2: Erratic movement
        if len(history) >= 3:
            directions = []
            for i in range(1, len(history)):
                dx = history[i]['center'][0] - history[i-1]['center'][0]
                dy = history[i]['center'][1] - history[i-1]['center'][1]
                if dx != 0:
                    angle = np.degrees(np.arctan2(dy, dx))
                    directions.append(angle)
            
            if len(directions) >= 2:
                direction_changes = np.abs(np.diff(directions))
                large_changes = np.sum(direction_changes > config.DIRECTION_CHANGE_THRESHOLD)
                if large_changes / len(direction_changes) > 0.3:
                    risk_score += 0.3
        
        # Factor 3: Proximity to other vehicles
        current_vehicle = history[-1]
        for other_id, other_history in self.track_history.items():
            if other_id != vehicle_id and len(other_history) > 0:
                other_current = other_history[-1] if isinstance(other_history, deque) else other_history[-1]
                distance = np.sqrt((current_vehicle['center'][0] - other_current['center'][0])**2 +
                                 (current_vehicle['center'][1] - other_current['center'][1])**2)
                if distance < config.COLLISION_DISTANCE:
                    risk_score += 0.3
                    break
        
        return min(risk_score, 1.0)


def create_advanced_visualization(frame, detections, accident_flags):
    """Create a modern, SCADA-style HUD for accident alerts."""
    display_frame = frame.copy()
    h, w = display_frame.shape[:2]
    
    # 1. Subtle 'Sentinel' scanline overlay (optional effect)
    # -----------------------------------------------------
    
    # 2. Draw Vehicles with modern 'corner-only' bounding boxes
    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        color = config.COLORS['vehicle']
        
        # Sleek corners instead of full box
        length = min(15, int((x2-x1)*0.2))
        t = 2
        # Top-left
        cv2.line(display_frame, (x1, y1), (x1 + length, y1), color, t)
        cv2.line(display_frame, (x1, y1), (x1, y1 + length), color, t)
        # Top-right
        cv2.line(display_frame, (x2, y1), (x2 - length, y1), color, t)
        cv2.line(display_frame, (x2, y1), (x2, y1 + length), color, t)
        # Bottom-left
        cv2.line(display_frame, (x1, y2), (x1 + length, y2), color, t)
        cv2.line(display_frame, (x1, y2), (x1, y2 - length), color, t)
        # Bottom-right
        cv2.line(display_frame, (x2, y2), (x2 - length, y2), color, t)
        cv2.line(display_frame, (x2, y2), (x2, y2 - length), color, t)
        
        # Minimalist Label with semi-transparent background
        label = f"V_{detections.index(det):02d}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.rectangle(display_frame, (x1, y1 - th - 10), (x1 + tw + 10, y1), (0,0,0), -1)
        cv2.putText(display_frame, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # 3. Handle Accident Alerts with a Premium HUD
    if accident_flags:
        # PULSING BORDER (Red Vignette)
        # Use time for pulse effect
        pulse = int(abs(np.sin(time.time() * 5)) * 10)
        overlay = display_frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 255), 15 + pulse)
        cv2.addWeighted(overlay, 0.3, display_frame, 0.7, 0, display_frame)

        # TOP BAR BANNER
        banner_h = 60
        banner_overlay = display_frame.copy()
        cv2.rectangle(banner_overlay, (0, 0), (w, banner_h), (0, 0, 0), -1)
        cv2.addWeighted(banner_overlay, 0.6, display_frame, 0.4, 0, display_frame)
        
        # Warning Icon (Triangle)
        pts = np.array([[30, 15], [15, 45], [45, 45]], np.int32)
        cv2.fillPoly(display_frame, [pts], (0, 0, 255))
        cv2.putText(display_frame, "!", (27, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Main Alert Text
        cv2.putText(display_frame, "SYSTEM ALERT: COLLISION DETECTED", (70, 32), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(display_frame, f"CRITICALITY: HIGH | {len(accident_flags)} VEHICLES INVOLVED", (70, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        # Probabilities Sidebar
        for i, (vehicle_id, probability) in enumerate(accident_flags):
            y_offset = 80 + i*35
            # Small background for each prob
            cv2.rectangle(display_frame, (10, y_offset), (200, y_offset + 25), (0, 0, 0), -1)
            cv2.rectangle(display_frame, (10, y_offset), (int(10 + 190*probability), y_offset + 25), (0, 0, 255), -1)
            cv2.putText(display_frame, f"DETECTION {i}: {probability*100:.1f}%", (15, y_offset + 18),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # 4. Bottom Telemetry
    cv2.putText(display_frame, f"SENTINEL LIVE FEED | {datetime.now().strftime('%H:%M:%S')}", 
               (15, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    cv2.putText(display_frame, f"SENSORS: {len(detections)} OBJECTS ACTIVE", 
               (15, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    return display_frame


def process_accident_video(video_path, output_path="output_analysis.mp4", max_frames=3000, show_window=True):
    """Advanced video processing pipeline."""

    print(f"\n[INFO] Starting video pipeline: {os.path.basename(video_path)}")
    print(f"[INFO] Inference device: {config.YOLO_DEVICE}")
    
    model = YOLO(config.YOLO_MODEL, task='detect')
    if not openvinoGPU and torch.cuda.is_available():
        model.to(config.YOLO_DEVICE)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Could not open video: {video_path}")
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Use mp4v for better out-of-the-box compatibility on Windows/OpenCV
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    advanced_tracker = AdvancedVehicleTracker()

    results = {'frames_processed': 0, 'vehicles_detected': 0, 'accident_alerts': []}
    accident_buffer = []  # To store vis_frames for median snapshot
    frame_count = 0
    start_time = time.time()

    print("[INFO] Processing stream... (Press 'q' to stop early).")
    while cap.isOpened() and frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % config.FRAME_SKIP != 0:
            frame_count += 1
            continue

        if width > config.RESIZE_WIDTH:
            scale_factor = config.RESIZE_WIDTH / width
            new_width = config.RESIZE_WIDTH
            new_height = int(height * scale_factor)
            frame = cv2.resize(frame, (new_width, new_height))

        yolo_results = model(
            frame,
            task='detect',
            conf=config.CONFIDENCE_THRESHOLD,
            iou=config.IOU_THRESHOLD,
            imgsz=640,
            device=config.YOLO_DEVICE if not openvinoGPU else None, # AutoBackend patch handles device
            half=not openvinoGPU and config.YOLO_DEVICE.startswith('cuda'),
            verbose=False
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

        _, accident_flags = advanced_tracker.update_tracks(detections, frame)
        vis_frame = create_advanced_visualization(frame, detections, accident_flags)
        out.write(vis_frame)

        # Real-time visualization
        if show_window:
            cv2.imshow("Accident Detector - OpenVINO GPU", vis_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        results['frames_processed'] += 1
        results['vehicles_detected'] += len(detections)

        if accident_flags:
            results['accident_alerts'].append({'frame': frame_count, 'vehicle_count': len(detections), 'flags': accident_flags})
            # Add to buffer for median snapshot (copy to avoid mutation)
            accident_buffer.append(vis_frame.copy())
        frame_count += 1
        if frame_count % 30 == 0:
            elapsed = time.time() - start_time
            current_fps = results['frames_processed'] / elapsed
            print(f" > Frame {frame_count} | Speed: {current_fps:.1f} FPS | Detected: {len(detections)} vehicles | Alerts: {len(accident_flags)}")
    cap.release()
    out.release()
    if show_window:
        cv2.destroyAllWindows()

    total_time = time.time() - start_time
    final_fps = results['frames_processed'] / total_time

    print("\n" + "="*40)
    print(f" [DONE] Processed {results['frames_processed']} valid frames at {final_fps:.1f} FPS")
    print(f"        Output saved to: {output_path}")
    print(f"        Total Accident Alerts triggered: {len(results['accident_alerts'])}")
    
    # Save median frame snapshot
    if accident_buffer:
        median_idx = len(accident_buffer) // 2
        snapshot_path = "accident_snapshot.jpg"
        cv2.imwrite(snapshot_path, accident_buffer[median_idx])
        print(f" [HUD] Median accident frame saved to: {snapshot_path} (Index {median_idx} of {len(accident_buffer)})")
        
    print("="*40 + "\n")
    return results

if __name__ == "__main__":
    # Test path fallback for both root and /backend folder execution
    video_to_process = r"backend\test_vid\test3.mp4"
    if not os.path.exists(video_to_process):
        video_to_process = r"test_vid\test3.mp4"
    
    output_video_path = "processed_accident_video.mp4"
    process_accident_video(video_to_process, output_video_path)
