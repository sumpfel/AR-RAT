import cv2
import mediapipe as mp
import numpy as np
import math
import os

class CameraLogic:
    def __init__(self, target_priority='center'):
        self.target_priority = target_priority
        self.cap = None
        self.detector = None
        
        # Initialize MediaPipe
        self.BaseOptions = mp.tasks.BaseOptions
        self.FaceDetector = mp.tasks.vision.FaceDetector
        self.FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
        self.VisionRunningMode = mp.tasks.vision.RunningMode
        
        self.init_camera()
        self.init_detector()

    def init_camera(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def init_detector(self):
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blaze_face_short_range.tflite')
        options = self.FaceDetectorOptions(
            base_options=self.BaseOptions(model_asset_path=model_path),
            running_mode=self.VisionRunningMode.IMAGE)
        self.detector = self.FaceDetector.create_from_options(options)

    def update(self):
        ret, frame = self.cap.read()
        if not ret: return 0, None, 0
        
        face_img = None
        face_lum = 0
        active_targets = 0
        
        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        
        # Detect
        detection_result = self.detector.detect(mp_image)
        
        if detection_result.detections:
            active_targets = len(detection_result.detections)
            h, w, _ = frame.shape
            cx, cy = w/2, h/2
            
            min_val = float('inf') 
            best_detection = None
            
            for detection in detection_result.detections:
                bbox = detection.bounding_box
                x = int(bbox.origin_x)
                y = int(bbox.origin_y)
                bw = int(bbox.width)
                bh = int(bbox.height)
                
                x = max(0, x); y = max(0, y)
                bw = min(w-x, bw); bh = min(h-y, bh)
                
                if bw > 10 and bh > 10:
                    metric = float('inf')
                    
                    if self.target_priority == 'dark':
                         # Prioritize Lowest Luminance
                         temp_crop = frame[y:y+bh, x:x+bw]
                         temp_gray = cv2.cvtColor(temp_crop, cv2.COLOR_BGR2GRAY)
                         lum = np.mean(temp_gray)
                         metric = lum
                    else:
                         # Default: Prioritize Center
                         fcx, fcy = x + bw/2, y + bh/2
                         dist = math.hypot(fcx-cx, fcy-cy)
                         metric = dist
                    
                    if metric < min_val:
                        min_val = metric
                        best_detection = (x, y, bw, bh)
            
            if best_detection:
                x, y, bw, bh = best_detection
                x = max(0, x); y = max(0, y)
                bw = min(w-x, bw); bh = min(h-y, bh)
                
                if bw > 10 and bh > 10:
                    crop = frame[y:y+bh, x:x+bw]
                    # Black and White Film Effect
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    
                    # Calculate Luminance
                    face_lum = int(np.mean(gray))
                    
                    # Film Noir Effect
                    face_contrasted = cv2.convertScaleAbs(gray, alpha=1.1, beta=-10)
                    
                    # Add Noise
                    noise = np.zeros(face_contrasted.shape, dtype=np.uint8)
                    cv2.randn(noise, 0, 20)
                    face_img = cv2.add(face_contrasted, noise)
        else:
            # Old TV Static
            noise_h, noise_w = 200, 200
            face_img = np.zeros((noise_h, noise_w), dtype=np.uint8)
            cv2.randu(face_img, 0, 255)
            
        return active_targets, face_img, face_lum

    def close(self):
        if self.cap:
            self.cap.release()
