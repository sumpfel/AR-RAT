import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import cv2
import numpy as np

class HandDetector:
    def __init__(self, model_path="hand_landmarker.task", max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.5):
        # Create an HandLandmarker object.
        base_options = python.BaseOptions(model_asset_path=model_path)
        # Verify if video mode is best, or image mode. For simple loop, IMAGE mode is easier to sync unless we use async callbacks.
        # Let's use VIDEO mode but feed it with timestamps, or just IMAGE mode for simplicity frame-by-frame.
        # However, VIDEO mode has tracking which is faster/better.
        # But for VIDEO mode, we need valid timestamps. 
        # LIVE_STREAM mode is best for camera but requires async callback.
        # To keep the main loop simple (synchronous), let's use VIDEO mode and managing timestamps manually 
        # OR just use IMAGE mode (simpler, slightly slower but consistent).
        # Given the error previous, let's stick to IMAGE mode for reliability unless perf is bad.
        
        # Actually, let's try VIDEO mode.
        self.running_mode = vision.RunningMode.VIDEO
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=max_num_hands, 
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_tracking_confidence,
            running_mode=self.running_mode)
        
        try:
            self.landmarker = vision.HandLandmarker.create_from_options(options)
        except Exception as e:
            print(f"Failed to load model {model_path}: {e}")
            raise

        self.timestamp_ms = 0

    def process_frame(self, frame):
        """Processes a BGR frame and returns results."""
        # Convert BGR to RGB
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
        
        # Calculate timestamp
        self.timestamp_ms += 33 # Approx 30 FPS
        
        # Detect
        detection_result = self.landmarker.detect_for_video(mp_image, self.timestamp_ms)
        return detection_result

    def get_landmarks_as_list(self, detection_result):
        """Extracts landmarks into a simplified list structure for all detection hands."""
        if not detection_result or not detection_result.hand_landmarks:
            return []
        
        hands_list = []
        
        # Zip landmarks with handedness (if available)
        # MediaPipe Tasks API: detection_result.handedness is a list of categories
        handedness_list = detection_result.handedness
        
        for i, hand_landmarks in enumerate(detection_result.hand_landmarks):
            # Extract basic landmarks
            lm_list = [{'x': lm.x, 'y': lm.y, 'z': lm.z} for lm in hand_landmarks]
            
            # Determine handedness label
            hand_label = "Unknown"
            if handedness_list and len(handedness_list) > i:
                # Tasks API: handedness[i] is a list of categories, usually just one top one.
                # Contains category_name ('Left'|'Right')
                hand_label = handedness_list[i][0].category_name
            
            hands_list.append({
                "landmarks": lm_list,
                "label": hand_label
            })
            
        return hands_list

    def draw_landmarks(self, frame, detection_result):
        """Draws landmarks on the frame."""
        if not detection_result or not detection_result.hand_landmarks:
            return

        # Simple manual drawing since mp.solutions.drawing_utils might be missing/incompatible
        h, w, _ = frame.shape
        for hand_landmarks in detection_result.hand_landmarks:
            # Draw points
            for lm in hand_landmarks:
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
            
            # Draw connections (using standard MediaPipe connections)
            # HARDCODED connections since solutions.hands might be missing
            connections = [
                (0,1), (1,2), (2,3), (3,4),       # Thumb
                (0,5), (5,6), (6,7), (7,8),       # Index
                (5,9), (9,10), (10,11), (11,12),  # Middle
                (9,13), (13,14), (14,15), (15,16),# Ring
                (13,17), (17,18), (18,19), (19,20),# Pinky
                (0,17) # Wrist to Pinky Base
            ]
            
            # Map landmarks to pixel coords first for easier drawing
            coords = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks]
            
            for start_idx, end_idx in connections:
                cv2.line(frame, coords[start_idx], coords[end_idx], (0, 255, 0), 2)
