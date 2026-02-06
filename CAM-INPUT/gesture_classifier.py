import math
import json
import os
import numpy as np

class GestureClassifier:
    def __init__(self, gestures_file="gestures.json"):
        self.gestures_file = gestures_file
        self.custom_gestures = {}
        self.load_gestures()
        
        # Mapping finger ID to landmarks (Tip, PIP)
        # Thumb: 4, Index: 8, Middle: 12, Ring: 16, Pinky: 20
        self.finger_tips = [8, 12, 16, 20]
        self.finger_pips = [6, 10, 14, 18]
        self.thumb_tip = 4
        self.thumb_ip = 3
        self.wrist = 0

    def load_gestures(self):
        if os.path.exists(self.gestures_file):
            try:
                with open(self.gestures_file, 'r') as f:
                    self.custom_gestures = json.load(f)
                print(f"Loaded {len(self.custom_gestures)} custom gestures.")
            except Exception as e:
                print(f"Error loading gestures: {e}")
                self.custom_gestures = {}

    def save_gestures(self):
        try:
            with open(self.gestures_file, 'w') as f:
                json.dump(self.custom_gestures, f, indent=4)
            print("Gestures saved.")
        except Exception as e:
            print(f"Error saving gestures: {e}")

    def add_sample(self, name, landmarks):
        """Records a new gesture sample (normalized)."""
        norm_landmarks = self._normalize_landmarks(landmarks)
        self.custom_gestures[name] = norm_landmarks
        self.save_gestures()

    def _normalize_landmarks(self, landmarks):
        """
        Normalizes landmarks to be scale-invariant and wrist-relative.
        Returns a flat list of coordinates [x1, y1, z1, x2, y2, z2...].
        """
        # Convert dict list to numpy array for easier math
        # landmarks is list of {'x':..., 'y':..., 'z':...}
        coords = []
        for lm in landmarks:
            coords.append([lm['x'], lm['y'], lm['z']])
        coords = np.array(coords)

        # 1. Translate to wrist (index 0)
        base = coords[0]
        coords = coords - base

        # 2. Scale by max distance from wrist (to handle hand moving closer/further)
        max_dist = np.max(np.linalg.norm(coords, axis=1))
        if max_dist > 0:
            coords = coords / max_dist

        return coords.tolist()

    def _calculate_distance(self, landmarks1, landmarks2):
        """Euclidean distance between two normalized landmark sets."""
        a = np.array(landmarks1)
        b = np.array(landmarks2)
        return np.linalg.norm(a - b)

    def _heuristic_gesture(self, landmarks):
        """Basic finger counting logic and AR specific shortcuts."""
        lms = landmarks # list of dicts
        
        fingers_open = []
        
        # Check 4 fingers (Index to Pinky)
        # Finger is open if Tip is above PIP (lower y) - assuming upright hand
        # This simple check fails if hand is inverted, but sufficient for basic usage.
        for tip, pip in zip(self.finger_tips, self.finger_pips):
            if lms[tip]['y'] < lms[pip]['y']: 
                fingers_open.append(1)
            else:
                fingers_open.append(0)
        
        # Count non-thumb fingers being open
        count_non_thumb = sum(fingers_open)
        
        # Check Thumb
        # Thumb is open if Tip is to the side of IP? 
        # Simpler: Distance from Index MCP (5). 
        # But for 'Okay' gesture, we need specific check of Thumb Tip near Index Tip.
        
        thumb_tip = lms[4]
        index_tip = lms[8]
        
        # Distance between thumb tip and index tip
        pinch_dist = math.hypot(thumb_tip['x'] - index_tip['x'], thumb_tip['y'] - index_tip['y'])
        
        # Check for "Okay" / "Enter": Index and Thumb close, other fingers OPEN
        # Pinch distance threshold: 0.05 (normalized roughly 0-1 range usually, but here likely raw coords from simple list are 0-1)
        # Other 3 fingers (Middle, Ring, Pinky) must be open.
        # fingers_open indices: 0=Index, 1=Middle, 2=Ring, 3=Pinky
        
        is_pinching = pinch_dist < 0.05
        middle_open = fingers_open[1]
        ring_open = fingers_open[2]
        pinky_open = fingers_open[3]
        
        if is_pinching and middle_open and ring_open and pinky_open:
            return "Okay", 0.9

        # Check for "Okay" variant where others are closed? (Usually Okay has others open or closed)
        # Let's stick to standard Okay (others open).
        
        # Check for "Stop" / "No": All 5 fingers open.
        # Check thumb open: Tip 'far' from Index MCP (5)
        thumb_index_mcp_dist = math.hypot(thumb_tip['x'] - lms[5]['x'], thumb_tip['y'] - lms[5]['y'])
        is_thumb_open = thumb_index_mcp_dist > 0.07 # Heuristic threshold
        
        if count_non_thumb == 4 and is_thumb_open:
            return "Stop", 0.9

        if fingers_open[0] and is_thumb_open and not middle_open and not ring_open and not pinky_open:
            return "L", 0.8

        # Check for "Point": Index open, others closed
        if fingers_open[0] and not middle_open and not ring_open and not pinky_open:
             return "Point", 0.9

        # Check for "Middle Finger": Middle open, others closed
        if fingers_open[1] and not fingers_open[0] and not fingers_open[2] and not fingers_open[3]:
             return "Middle Finger", 0.9
             
        # Check for "Peace" (Keyboard View Toggle): Index + Middle open, Ring + Pinky closed
        if fingers_open[0] and fingers_open[1] and not fingers_open[2] and not fingers_open[3]:
            return "Peace", 0.9

        # Check for "Fist": All closed
        # Strict "0 fingers open" can be flaky.
        # Robust Fist Check: Tips are close to Wrist/MCPs
        # Let's check average distance of tips to wrist
        tips_indices = [8, 12, 16, 20]
        wrist_idx = 0
        avg_dist_to_wrist = 0
        for ti in tips_indices:
             avg_dist_to_wrist += math.hypot(lms[ti]['x'] - lms[wrist_idx]['x'], lms[ti]['y'] - lms[wrist_idx]['y'])
        avg_dist_to_wrist /= 4
        
        # Threshold: Fist is usually < 0.2 approx (normalized). Spread hand > 0.3-0.4
        # Note: landmark coords here from MediaPipe are normalized [0,1].
        # Let's refine based on experience: ~0.1 to 0.15 is tight fist.
        # Also ensure count_non_thumb is low <= 1 (allow one loose finger)
        
        if count_non_thumb <= 1 and avg_dist_to_wrist < 0.25:
             # Additional check: Thumb shouldn't be fully extended out? 
             # Actually Fist implies thumb over fingers or side.
             return "Fist", 0.8
        
        if count_non_thumb == 0:
            return "Fist", 0.8

        return "Unknown", 0.0

    def is_pinching(self, landmarks):
        """
        Strict check for Thumb-Index pinch (typing action).
        Returns True if pinching, regardless of other fingers.
        """
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        dist = math.hypot(thumb_tip['x'] - index_tip['x'], thumb_tip['y'] - index_tip['y'])
        dist_atleast = math.hypot(landmarks[8]['x']-landmarks[7]['x'], landmarks[8]['y']-landmarks[7]['y'])
        return dist < dist_atleast*1.25

    def predict(self, hands_list):
        """
        Returns a dict with gesture data:
        {
          "gestures": [ {"hand": "Right", "gesture": "Point", "confidence": 0.9}, ... ],
          "compound": "None" | "Resize" | "Move" | "Select",
          "hand_distance": float
        }
        """
        results = {
            "gestures": [],
            "compound": "None",
            "hand_distance": 0.0
        }
        
        if not hands_list:
            return results

        # 1. Individual Gestures
        single_hand_predictions = []
        for hand in hands_list:
            landmarks = hand["landmarks"]
            # Check custom then heuristic
            gesture_name, confidence = self._predict_single_hand_custom(landmarks)
            if gesture_name is None:
                gesture_name, confidence = self._heuristic_gesture(landmarks)
            
            single_hand_predictions.append({
                "hand": hand["label"],
                "gesture": gesture_name,
                "confidence": confidence,
                "wrist": landmarks[0], # Store wrist for distance calc
                "landmarks": landmarks # Store landmarks for complex checks
            })
        
        results["gestures"] = single_hand_predictions

        # 2. Compound Gestures (Two Hands)
        if len(single_hand_predictions) == 2:
            h1 = single_hand_predictions[0]
            h2 = single_hand_predictions[1]
            
            # Calculate wrist distance (normalized space 0-1 approx)
            w1 = h1["wrist"]
            w2 = h2["wrist"]
            dist = math.hypot(w1['x'] - w2['x'], w1['y'] - w2['y'])
            results["hand_distance"] = dist
            
            # Logic
            g1 = h1["gesture"]
            g2 = h2["gesture"]
            
            # "Resize" / "Zoom": Both Pinching (Okay)
            if g1 == "Okay" and g2 == "Okay":
                results["compound"] = "Resize"
            
            # "Move" / "Grab": Both Fist
            elif g1 == "L" and g2 == "L":
                results["compound"] = "Move"

            # "Translate": Diamond / Triangle Shape
            # Left Thumb touches Right Thumb AND Left Index touches Right Index
            l_hand = h1 if h1["hand"] == "Left" else h2
            r_hand = h2 if h2["hand"] == "Right" else h1
            
            if l_hand["hand"] == "Left" and r_hand["hand"] == "Right":
                l_lms = l_hand["landmarks"]
                r_lms = r_hand["landmarks"]
                
                # Thumbs Touching (Landmark 4)
                thumbs_dist = math.hypot(l_lms[4]['x'] - r_lms[4]['x'], l_lms[4]['y'] - r_lms[4]['y'])
                # Indices Touching (Landmark 8)
                indices_dist = math.hypot(l_lms[8]['x'] - r_lms[8]['x'], l_lms[8]['y'] - r_lms[8]['y'])
                
                # Threshold for touching (0.08 is reasonable for normalized coords)
                if thumbs_dist < 0.08 and indices_dist < 0.08:
                    results["compound"] = "Translate"
                    
        return results

    def _predict_single_hand_custom(self, landmarks):
        """Check custom gestures first."""
        norm_current = self._normalize_landmarks(landmarks)
        
        best_match = None
        min_dist = float('inf')
        
        for name, saved_lms in self.custom_gestures.items():
            dist = self._calculate_distance(norm_current, saved_lms)
            if dist < min_dist:
                min_dist = dist
                best_match = name
        
        if best_match and min_dist < 0.4:
            return best_match, max(0, 1.0 - min_dist)
        
        return None, 0.0
