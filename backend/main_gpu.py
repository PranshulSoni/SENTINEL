import os
import cv2
import numpy as np
import time
from collections import deque
import openvino as ov
from ultralytics import YOLO

import warnings
import torch

warnings.filterwarnings('ignore')

# =====================================================================
# GPU PATCH: Force Ultralytics OpenVINO Backend to strictly use "GPU"
# =====================================================================
if not torch.cuda.is_available():
    print("\n[INIT] No CUDA GPU found. Applying OpenVINO Hardware Acceleration Patch...")
    original_compile = ov.Core.compile_model

    def patched_compile(self, model, device_name=None, config=None):
        print(">> Intercepted AutoBackend. Forcing compile_model on 'GPU' <<")
        return original_compile(self, model, "GPU", config)

    # Apply runtime patch
    ov.Core.compile_model = patched_compile
else:
    print("\n[INIT] CUDA detected! Skipping OpenVINO patch, will use NVIDIA GPU natively.")
# =====================================================================

class AdvancedAccidentConfig:
    """Advanced configuration for accident detection system."""
    
    if torch.cuda.is_available():
        YOLO_MODEL = 'yolov8m.pt' 
    else:
        YOLO_MODEL = 'yolov8m_openvino_model/' 
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
    
    FRAME_SKIP = 2  
    RESIZE_WIDTH = 640

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
    """Create advanced visualization with accident alerts."""
    display_frame = frame.copy()
    
    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        color = config.COLORS['vehicle']
        
        cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
        label = f"Vehicle: {det['confidence']:.2f}"
        cv2.putText(display_frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    if accident_flags:
        alert_text = f" ACCIDENT DETECTED: {len(accident_flags)} vehicles involved"
        cv2.putText(display_frame, alert_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, config.COLORS['accident'], 3)
        
        for i, (vehicle_id, probability) in enumerate(accident_flags):
            cv2.putText(display_frame, f"Accident Prob: {probability:.2f}", 
                       (10, 70 + i*30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, config.COLORS['accident'], 2)
    
    cv2.putText(display_frame, f"Vehicles: {len(detections)}", 
               (10, display_frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return display_frame


def process_accident_video(video_path, output_path="output_analysis.mp4", max_frames=3000, show_window=True):
    """Advanced video processing pipeline."""
    print(f"\n[INFO] Starting video pipeline: {os.path.basename(video_path)}")
    model = YOLO(config.YOLO_MODEL)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Could not open video: {video_path}")
        return None
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Use avc1 for HTML5 <video> browser compatibility instead of mp4v
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    advanced_tracker = AdvancedVehicleTracker()
    
    results = {'frames_processed': 0, 'vehicles_detected': 0, 'accident_alerts': []}
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
    print("="*40 + "\n")
    return results

if __name__ == "__main__":
    video_to_process = r"C:\MyStuff\VS\merge-conflict\backend\test_vid\test1.mp4"
    output_video_path = "processed_accident_video.mp4"
    process_accident_video(video_to_process, output_video_path)
