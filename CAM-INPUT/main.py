import math
import cv2
import argparse
import socket
import json
import time
import subprocess
import re
import os
import shutil
import numpy as np
from datetime import datetime
from camera_handler import CameraHandler
from hand_detector import HandDetector
from gesture_classifier import GestureClassifier
import threading
import queue
import copy
#import google.generativeai as genai
from PIL import Image
from pynput.mouse import Button # Keep Button for enum
# from pynput.mouse import Controller # Removed, replaced by HybridMouse
from hybrid_mouse import HybridMouse
from virtual_keyboard import VirtualKeyboard

# --- GLOBAL STATE ---
mouse = None # Initialized in main() to allow passing screen res
mouse_control_active = False # Toggled via IPC or Menu
left_click_held = False
right_click_held = False
click_cooldown = 0.5
last_click_time = 0

# --- TRANSLATION GLOBAL STATE ---
# Shared between main thread and translation thread
translation_active = False
latest_translation_boxes = [] # List of (x, y, w, h, text)
is_translating = False
api_key_loaded = False
sound_enabled = True

# IPC Control (Initialized in main)
control_socket = None
handedness = "Right" # Default Right-Handed (Mouse=Right, KeyboardToggle=Left)

def check_control_commands():
    global mouse_control_active, translation_active, sound_enabled, keyboard_view_active, handedness
    try:
        data, addr = control_socket.recvfrom(1024)
        cmd = json.loads(data.decode('utf-8'))
        print(f"Received Command: {cmd}")
        
        command = cmd["command"]
        value = cmd["value"]

        if command == "TOGGLE_MOUSE":
            mouse_control_active = value
            print(f"Mouse Control: {mouse_control_active}")
        elif command == "TOGGLE_KEYBOARD":
            keyboard_view_active = value
            print(f"Keyboard Mode: {keyboard_view_active}")
        elif command == "TOGGLE_TRANSLATION":
            translation_active = value
            print(f"Translation Mode: {translation_active}")
        elif command == "TOGGLE_SOUND":
            sound_enabled = value
            print(f"Sound: {sound_enabled}")
        elif command == "SET_VOLUME":
            # Volume is handled by system, but we can log it or use it for internal sound level if needed
            print(f"Volume Set: {value}")
        elif command == "SET_HANDEDNESS":
            handedness = value
            print(f"Handedness Set: {handedness}")
            
    except BlockingIOError:
        pass
    except Exception as e:
        print(f"Control Socket Error: {e}")

def load_api_key():
    global api_key_loaded
    if api_key_loaded: return True

    key = None
    # 1. Check local key.txt
    if os.path.exists("key.txt"):
        try:
            with open("key.txt", "r") as f:
                key = f.read().strip()
        except: pass

    # 2. Check AI Assistant settings
    if not key:
        try:
            settings_path = "../AI_ASSISTANT/settings.json"
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    data = json.load(f)
                    key = data.get("gemini_key", "")
        except: pass

    if key:
        genai.configure(api_key=key)
        api_key_loaded = True
        print("Gemini API Key loaded successfully.")
        return True
    else:
        print("ERROR: No Gemini API Key found. Create 'key.txt' or configure AI Assistant.")
        return False

def run_translation_task(frame_copy):
    """Refined translation task running in background using Google Gemini API."""
    global latest_translation_boxes, is_translating

    # DISABLED BY USER REQUEST
    is_translating = False
    return

    # try:
    #     if not load_api_key():
    #          is_translating = False
    #          return
    # 
    #     # Prepare Image
    #     pil_image = Image.fromarray(frame_copy)
    # 
    #     # Call Gemini
    #     model = genai.GenerativeModel('gemini-1.5-flash')
    # 
    #     prompt = (
    #         "Detect all visible text in this image. "
    #         "Translate each detected text block into German. "
    #         "Return a JSON list of objects. Each object must have: "
    #         "'text' (original text), 'translation' (German translation), "
    #         "and 'box_2d' (bounding box [ymin, xmin, ymax, xmax] normalized 0-1000). "
    #         "If no text, return empty list. Output ONLY JSON."
    #     )
    # 
    #     response = model.generate_content([prompt, pil_image])
    # 
    #     try:
    #         # Clean response
    #         text = response.text.replace("```json", "").replace("```", "").strip()
    #         data = json.loads(text)
    # 
    #         new_boxes = []
    #         h_img, w_img, _ = frame_copy.shape
    # 
    #         for item in data:
    #             if "translation" in item and "box_2d" in item:
    #                 ymin, xmin, ymax, xmax = item["box_2d"]
    #                 # Convert 0-1000 to pixels
    #                 x = int((xmin / 1000) * w_img)
    #                 y = int((ymin / 1000) * h_img)
    #                 w = int((xmax - xmin) / 1000 * w_img)
    #                 h = int((ymax - ymin) / 1000 * h_img)
    # 
    #                 translated_text = item["translation"]
    #                 new_boxes.append((x, y, w, h, translated_text))
    # 
    #         latest_translation_boxes = new_boxes
    #         print(f"Gemini Translation: Found {len(new_boxes)} blocks.")
    # 
    #     except Exception as e:
    #         print(f"Gemini Parse Error: {e} | Raw: {response.text[:100]}...")
    # 
    # except Exception as e:
    #     print(f"Gemini API Error: {e}")
    # finally:
    #     is_translating = False
    # 

def get_screen_resolution():
    try:
        output = subprocess.check_output("xrandr | grep '*' | head -n1", shell=True).decode()
        match = re.search(r"(\d+)x(\d+)", output)
        if match:
            return int(match.group(1)), int(match.group(2))
    except:
        pass
    return 1920, 1080 # Fallback

class DetectionThread(threading.Thread):
    def __init__(self, detector):
        super().__init__()
        self.detector = detector
        self.frame_queue = queue.Queue(maxsize=1)
        self.result_queue = queue.Queue(maxsize=1)
        self.running = True
        self.daemon = True

    def run(self):
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Optimize: Resize for faster detection if frame is huge? 
            # MediaPipe typically prefers 640x480 or similar.
            # But we want coordinate consistency. process_frame handles it?
            # HandDetector wraps mediapipe.
            
            try:
                detection_result = self.detector.process_frame(frame)
                hands_list = self.detector.get_landmarks_as_list(detection_result)
                
                # We can do the filtering here too to save main thread time
                self.result_queue.put(hands_list)
            except Exception as e:
                print(f"Detection Thread Error: {e}")

    def update_frame(self, frame):
        if self.frame_queue.full():
            try:
                self.frame_queue.get_nowait() # Drop old frame
            except queue.Empty:
                pass
        self.frame_queue.put(frame)

    def get_result(self):
        if not self.result_queue.empty():
            return self.result_queue.get()
        return None

    def stop(self):
        self.running = False


# ---------------------------------------------------------------------
# WINDOW MANAGEMENT HELPER
# ---------------------------------------------------------------------

def set_window_geometry(name, x, y, w, h):
    """
    Moves and resizes the application window.
    Includes specific logic for Hyprland to force tiling and visibility.
    """
    # Check for Hyprland
    if shutil.which("hyprctl"):
        try:
            # Get Clients to find address and current state
            output = subprocess.check_output(["hyprctl", "-j", "clients"], timeout=1).decode()
            clients = json.loads(output)
            
            target_address = None
            is_floating = False
            
            # Simple title match
            for client in clients:
                if client["title"] == name:
                    target_address = client["address"]
                    is_floating = client["floating"]
                    break
            
            if target_address:
                if is_floating:
                    subprocess.run(["hyprctl", "dispatch", "togglefloating", f"address:{target_address}"], stdout=subprocess.DEVNULL)
                    
                subprocess.run(["hyprctl", "dispatch", "movewindow", "d"], stdout=subprocess.DEVNULL)
                subprocess.run(["hyprctl", "dispatch", "movewindow", "d"], stdout=subprocess.DEVNULL)

            else:
                 # If window not found yet, maybe it's just created.
                 pass
        except Exception as e:
            print(f"Hyprland Error: {e}")
    else:
        pass
        # Standard OpenCV / X11 / Windows
        #cv2.resizeWindow(name, w, h)
        #cv2.moveWindow(name, x, y)

def main():
    parser = argparse.ArgumentParser(description="Hand Gesture Recognition UDP Sender")
    parser.add_argument("--mode", type=str, default="normal", choices=["normal", "debug", "record"], help="Operation mode")
    parser.add_argument("--udp_ip", type=str, default="127.0.0.1", help="UDP Target IP")
    parser.add_argument("--udp_port", type=int, default=5005, help="UDP Target Port")
    parser.add_argument("--cam_index", type=int, default=0, help="Camera Index")
    args = parser.parse_args()
    
    # -------------------------------------------------------------
    # FIX: Declare globals that are modified in main loop or gestures
    # -------------------------------------------------------------
    global mouse_control_active, translation_active, keyboard_view_active, sound_enabled, control_socket, mouse, handedness
    
    # Initialize Global State based on Args
    if args.mode in ["debug", "record"]:
        mouse_control_active = True

    # UDP Sender Setup
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Targeting UDP {args.udp_ip}:{args.udp_port}")

    # UDP Receiver (Control) Setup
    control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        control_socket.bind(('127.0.0.1', 5006))
        control_socket.setblocking(False)
        print("Control Socket bound to 127.0.0.1:5006")
    except Exception as e:
        print(f"Failed to bind Control Socket: {e}")
        return
    
    SCREEN_WIDTH, SCREEN_HEIGHT = get_screen_resolution()
    print(f"Detected Screen Resolution: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")
    
    # Initialize Hybrid Mouse
    mouse = HybridMouse(SCREEN_WIDTH, SCREEN_HEIGHT)
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print('Exiting...')
        try:
            cam.release()
            cv2.destroyAllWindows()
            det_thread.stop()
            sock.close()
            control_socket.close()
        except:
            pass
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    cv2.namedWindow("Hand Gesture Recognition", cv2.WINDOW_NORMAL)

    # --- INITIALIZATION ---
    # Camera Setup
    try:
        cam = CameraHandler(args.cam_index)
        cam.start()
    except Exception as e:
        print(f"Camera Error: {e}")
        return

    detector = HandDetector(max_num_hands=4, min_detection_confidence=0.7) # Increased max hands to 4 for filtering
    classifier = GestureClassifier()
    v_keyboard = VirtualKeyboard()

    target_fps = cam.get_target_fps()
    fps_history = []
    fps_avg = target_fps
    last_fps_time = time.time()
    frame_count = 0

    # Init Thread
    det_thread = DetectionThread(detector)
    det_thread.start()
    
    # State for threaded results
    current_hands_list = []
    
    print(f"Started in {args.mode} mode. Press 'q' to quit.")
    if args.mode == "record":
        print("Press 'r' to record current gesture (Only works if 1 hand detected).")

    # Toggle States (Enabled by Menu)
    keyboard_enabled = (args.mode in ["debug", "record"])
    translation_enabled = (args.mode in ["debug", "record"])
    
    # Active View States (Toggled by Gesture)
    keyboard_view_active = False 
    
    # Typing State
    last_key_press_time = 0
    key_press_cooldown = 0.5
    last_toggle_time = 0
    toggle_cooldown = 2.0
    active_key = None

    # MOUSE STATE
    global last_click_time, left_click_held, right_click_held
    # Initialize scroll state
    last_scroll_y = {}

    try:
            while True:
                # Check IPC
                try:
                    data, addr = control_socket.recvfrom(1024)
                    cmd = json.loads(data.decode('utf-8'))
                    print(f"Received Command: {cmd}")
                    
                    command = cmd["command"]
                    value = cmd["value"]
        
                    if command == "TOGGLE_MOUSE":
                        mouse_control_active = value
                        print(f"Mouse Control: {mouse_control_active}")
                    elif command == "TOGGLE_KEYBOARD":
                        keyboard_enabled = value
                        # If disabled, force close
                        if not keyboard_enabled: keyboard_view_active = False
                        print(f"Keyboard Enabled: {keyboard_enabled}")
                    elif command == "TOGGLE_TRANSLATION":
                        translation_enabled = value
                        if not translation_enabled: 
                            translation_active = False
                            set_window_geometry("Hand Gesture Recognition", (SCREEN_WIDTH-1280)//2, (SCREEN_HEIGHT-720)//2, 1280, 720)
                        print(f"Translation Enabled: {translation_enabled}")
                    elif command == "TOGGLE_SOUND":
                        sound_enabled = value
                        print(f"Sound: {sound_enabled}")
                    elif command == "SET_VOLUME":
                        print(f"Volume Set: {value}")
                except BlockingIOError:
                    pass
                except Exception as e:
                    print(f"Control Socket Error: {e}")
            
                ret, frame = cam.get_frame()
                if not ret:
                    print("Failed to get frame")
                    break
        
                # Flip for mirror view -> DISABLED for OCR/World Readability
                # frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape
                
                curr_time = time.time()
                frame_count += 1
        
                # Calculate FPS every 1 second or so
                if curr_time - last_fps_time >= 0.5:
                    fps_avg = frame_count / (curr_time - last_fps_time)
                    fps_history.append(fps_avg)
                    if len(fps_history) > 10: fps_history.pop(0)
                    fps_avg = sum(fps_history) / len(fps_history)
        
                    frame_count = 0
                    last_fps_time = curr_time
        
                # --- DETECT ---
                det_thread.update_frame(frame.copy())
                
                new_results = det_thread.get_result()
                if new_results is not None:
                     hands_list_raw = new_results
                     
                     # Apply Filtering Logic
                     hands_left = []
                     hands_right = []
                     
                     for hand in hands_list_raw:
                        lms = hand["landmarks"]
                        size = math.hypot(lms[0]['x'] - lms[9]['x'], lms[0]['y'] - lms[9]['y'])
                        hand["size"] = size
        
                        if size > 0.1:
                            if hand["label"] == "Left":
                                hands_left.append(hand)
                            else: 
                                hands_right.append(hand)
        
                     final_hands = []
                     if hands_left:
                        hands_left.sort(key=lambda x: x["size"], reverse=True)
                        final_hands.append(hands_left[0])
                     if hands_right:
                        hands_right.sort(key=lambda x: x["size"], reverse=True)
                        final_hands.append(hands_right[0])
                     
                     current_hands_list = final_hands
        
                # Local variable for this frame's logic
                hands_list = current_hands_list
                
                udp_data = {
                    "compound": "None",
                    "gestures": [],
                    "timestamp": curr_time
                }
        
                # ---------------------------------------------------------
                # HAND DETECTED
                # ---------------------------------------------------------
                should_close_keyboard = False
                if hands_list:
                    # Predict Gestures from Landmarks
                    results = classifier.predict(hands_list)
                    udp_data.update(results)
                    
                    curr_time = time.time()
                    
                    # --- MOUSE CONTROL LOGIC ---
                    
                    # Mouse is active IF:
                    # 1. Enabled via Menu/IPC (mouse_control_active)
                    # 2. Keyboard View is NOT active
                    # 3. Translation Mode is NOT active
                    
                    should_move_mouse = mouse_control_active and (not keyboard_view_active) and (not translation_active)

                    if should_move_mouse:
                        # ONLY Control with PRIMARY hand (Right if avail, else Left) to avoid jitter
                        # Or just the first one in the list?
                        # Let's prefer Right Hand for mouse? Or just use the first 'final_hands'
                        
                        control_hand = None
                        # Prefer configured handedness for mouse
                        target_hand_label = handedness 
                        for h_cand in hands_list:
                            if h_cand["label"] == target_hand_label:
                                control_hand = h_cand
                                break
                        if not control_hand and hands_list:
                            control_hand = hands_list[0]
        
                        if control_hand:
                            hand = control_hand # Scope for gestures
                            lms = hand["landmarks"]
                            
                            # Debug Hand Selection
                            # print(f"Controlling Mouse with: {hand['label']}")
                            
                            # 1. Move Cursor (Index Tip)
                            # User Request: "just be aplied the same movement as the finger... use the tip of the finger as coordinate"
                            # FIX 1: The camera is providing a non-mirrored image (for Text Reading).
                            # This means moving hand RIGHT -> Image LEFT -> x approaches 0.
                            # We need to INVERT X for intuitive mouse control.
                            
                            idx_x = lms[8]['x']
                            idx_y = lms[8]['y']
                            
                            # Invert X because camera is not mirrored
                            screen_x = int((1.0 - idx_x) * SCREEN_WIDTH)
                            screen_y = int(idx_y * SCREEN_HEIGHT)
                            
                            # Improve Robustness: Hyprland / Linux might need exception handling
                            # Improve Robustness: Hyprland / Linux might need exception handling
                            try:
                                mouse.move(screen_x, screen_y)
                                # print(f"Move: {screen_x}, {screen_y}") 
                            except Exception as e:
                                print(f"Mouse Move Error: {e}")
                                pass
                            
                            # 2. Clicks (Pinch Logic like Keyboard)
                            is_pinching = classifier.is_pinching(lms)
                            
                            # Left Click (Index Pinch)
                            if is_pinching:
                                if not left_click_held:
                                    mouse.click(Button.left, True)
                                    left_click_held = True
                                    print("Click: Left Down (Pinch)")
                            else:
                                if left_click_held:
                                    mouse.click(Button.left, False)
                                    left_click_held = False
                                    # print("Click: Left Up")
                                    
                            # Right Click (Middle Finger Pinch or Distance)
                            dist_mid_thumb = math.hypot(lms[12]['x'] - lms[4]['x'], lms[12]['y'] - lms[4]['y'])
                            click_thresh = 0.05
                            
                            if dist_mid_thumb < click_thresh:
                                if not right_click_held:
                                     mouse.click(Button.right, True)
                                     right_click_held = True
                                     print("Click: Right Down")
                            else:
                                if right_click_held:
                                    mouse.click(Button.right, False)
                                    right_click_held = False
                                    # print("Click: Right Up")
                            
                            # 3. Scroll
                            # Using global gesture detection results (might include other hand, but safe enough)
                            # We should probably check if THIS hand is doing Open_Palm
                            
                            # Check if THIS hand has 'Open_Palm' gesture in udp_data
                            # We need to match hand label
                            this_hand_gesture = next((g["gesture"] for g in udp_data["gestures"] if g["hand"] == hand["label"]), None)
                            
                            if this_hand_gesture == "Open_Palm":
                                 current_y = lms[0]['y'] # Wrist
                                 hand_label = hand["label"]
                                 
                                 if hand_label in last_scroll_y:
                                     prev_y = last_scroll_y[hand_label]
                                     delta_y = current_y - prev_y
                                     
                                     scroll_threshold = 0.02
                                     scroll_speed = 5
                                     
                                     if abs(delta_y) > scroll_threshold:
                                         steps = int(-delta_y * 100 * scroll_speed)
                                         if steps != 0:
                                             mouse.scroll(steps)
                                             print(f"Scroll: {steps}")
                                             
                                 last_scroll_y[hand_label] = current_y
                            else:
                                if hand["label"] in last_scroll_y:
                                    del last_scroll_y[hand["label"]]
        
                    
                    # Check Actions based on gestures
                    for g in udp_data["gestures"]:
                        # PEACE -> Toggle Keyboard ON (Only if enabled)
                        # Handedness Logic: If Right Handed, Toggle with Left Hand (and vice versa)
                        toggle_hand_label = "Left" if handedness == "Right" else "Right"
                        
                        if g["gesture"] == "Peace" and g["hand"] == toggle_hand_label:
                            # Allow opening keyboard even if mouse is active (it will auto-disable mouse)
                            if keyboard_enabled and not keyboard_view_active and (curr_time - last_toggle_time > toggle_cooldown):
                                keyboard_view_active = True
                                translation_active = False
                                last_toggle_time = curr_time
                                print("Keyboard View: OPENED")
                                
                                target_h = SCREEN_HEIGHT // 2
                                set_window_geometry("Hand Gesture Recognition", 0, target_h, SCREEN_WIDTH, target_h)
        
                        # MIDDLE FINGER -> Toggle Keyboard OFF (Only if active)
                        elif g["gesture"] == "Middle Finger":
                             if keyboard_view_active and (curr_time - last_toggle_time > toggle_cooldown):
                                 should_close_keyboard = True
                    
                    # Typing Logic (Only if keyboard active)
                    active_key = None
                    if keyboard_view_active:
                        if udp_data['compound'] == "Move":
                            x_coords = []
                            y_coords = []
                            for hand in hands_list:
                                lms = hand["landmarks"]
                                x_coords.append(int(lms[8]['x'] * w))
                                y_coords.append(int(lms[8]['y'] * h))
                            v_keyboard.better_moving(x_coords, y_coords)
                        
                        # Typing...
                        for hand in hands_list:
                            lms = hand["landmarks"]
                            size = hand.get("size", 0)
                            cv2.putText(frame, f"Size: {size:.2f}", (10, 540), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
        
                            # Check PINCH
                            if classifier.is_pinching(lms) and not udp_data['compound'] == "Resize" and not udp_data['compound'] == "Move":
                                if size > 0.15:
                                    idx_x = int(lms[8]['x'] * w)
                                    idx_y = int(lms[8]['y'] * h)
                                    key_hit = v_keyboard.get_key_at(idx_x, idx_y)
                                    if key_hit:
                                        active_key = key_hit
                                        if curr_time - last_key_press_time > key_press_cooldown:
                                            if key_hit == "SWITCH_LAYOUT_SYM":
                                                v_keyboard.switch_layout()
                                                print(f"Layout Switched. Mode: {v_keyboard.layout_mode}")
                                            else:
                                                print(f"Typing: {key_hit}")
                                                # Type the key using HybridMouse (uinput/pynput)
                                                mouse.type_key(key_hit)
                                                
                                                key_data = {
                                                    "type": "keydown",
                                                    "key": key_hit,
                                                    "timestamp": curr_time
                                                }
                                                sock.sendto(json.dumps(key_data).encode('utf-8'), (args.udp_ip, args.udp_port))
                                            last_key_press_time = curr_time
                                else:
                                    cv2.putText(frame, f"HAND NOT CLOSE ENOUGH", (10, 500), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 3)
        
                if should_close_keyboard and (time.time() - last_toggle_time > toggle_cooldown):
                     keyboard_view_active = False
                     last_toggle_time = time.time()
                     print("Keyboard View: CLOSED")
                     set_window_geometry("Hand Gesture Recognition", (SCREEN_WIDTH-1280)//2, (SCREEN_HEIGHT-720)//2, 1280, 720)
        
                # ---------------------------------------------------------
                # TRANSLATION MODE LOGIC (Google Lens Style)
                # ---------------------------------------------------------
                if translation_enabled:
                     if udp_data['compound'] == "Translate" and not keyboard_view_active:
                          if (curr_time - last_toggle_time > toggle_cooldown):
                               translation_active = not translation_active
                               last_toggle_time = curr_time
                               print(f"Translation Mode: {'ON' if translation_active else 'OFF'}")
                               
                               if translation_active:
                                   set_window_geometry("Hand Gesture Recognition", 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
                               else:
                                   set_window_geometry("Hand Gesture Recognition", (SCREEN_WIDTH-1280)//2, (SCREEN_HEIGHT-720)//2, 1280, 720)
        
                if translation_active:
                    if not keyboard_view_active: # If translation is active, keyboard should be off
                        # Translation Mode -> FULL SCREEN (Lens)
#                         set_window_geometry("Hand Gesture Recognition", 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
                        pass
                    
                    # Trigger continuous translation if not running
                    global is_translating
                    if not is_translating:
                         is_translating = True
                         # Copy frame for thread
                         frame_for_ocr = frame.copy()
                         frame_for_ocr = cv2.cvtColor(frame_for_ocr, cv2.COLOR_BGR2RGB)
        
                         t = threading.Thread(target=run_translation_task, args=(frame_for_ocr,))
                         t.daemon = True
                         t.start()
                else:
                    # If translation was active and now is not, restore window size
                    # This needs to be careful not to conflict with keyboard_view_active
                    if not keyboard_view_active and not mouse_control_active: # Only restore if no other special mode is active
#                         set_window_geometry("Hand Gesture Recognition", (SCREEN_WIDTH-1280)//2, (SCREEN_HEIGHT-720)//2, 1280, 720)
                        pass
        
        
                # Prepare Gesture UDP Packet
                # Clean data
                for g in udp_data["gestures"]:
                    if "wrist" in g: del g["wrist"]
        
                # Only send Gesture UDP if NOT typing? Or always?
                # Let's always send it, but maybe add keyboard status
                udp_data["keyboard_active"] = keyboard_view_active
                udp_data["mouse_active"] = mouse_control_active
                json_data = json.dumps(udp_data).encode('utf-8')
                sock.sendto(json_data, (args.udp_ip, args.udp_port))
        
                # Visualization
                # User requested: "only keyboard mode or translation mode show cam as a window"
                # So if ONLY mouse is active, do NOT show window.
                if args.mode in ["debug", "record"] or keyboard_view_active or translation_active:
                    # Draw Keyboard
                    if keyboard_view_active:
                        v_keyboard.draw(frame, active_key)
                    
                    detector.draw_landmarks(frame, hands_list)
        
                    # frame is already the final frame
                    
                    y_offset = 70
                    
                    # Show Compound
                    if udp_data["compound"] != "None":
                         cv2.putText(frame, f"COMMAND: {udp_data['compound']}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                         y_offset += 40
                    
                    # Show Individual
                    for g in udp_data["gestures"]:
                         text = f"{g['hand']}: {g['gesture']} ({g['confidence']:.2f})"
                         cv2.putText(frame, text, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                         y_offset += 30
        
                    # Display Mode & View Status
                    cv2.putText(frame, f"Mode: {args.mode}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
                    # FPS Display
                    fps_color = (0, 255, 0) # Green default
                    if fps_avg <= 5:
                        fps_color = (0, 0, 139) # Dark Red
                    elif fps_avg < target_fps:
                        # Interpolate between Red and Green
                        ratio = (fps_avg - 5) / (target_fps - 5) if target_fps > 5 else 1
                        ratio = max(0, min(1, ratio))
                        # HSL or just simple RGB? Let's do simple RGB transition
                        # Low FPS: Red (0,0,255), High FPS: Green (0,255,0)
                        # Note: OpenCV uses BGR
                        r = int(255 * (1 - ratio))
                        g = int(255 * ratio)
                        fps_color = (0, g, r)
        
                    cv2.putText(frame, f"FPS: {fps_avg:.1f} / {target_fps}", (w - 250, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, fps_color, 2)
        
                    if keyboard_view_active:
                        cv2.putText(frame, "KEYBOARD ACTIVE", (10, y_offset + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        cv2.putText(frame, "Pinch to Type. Middlefinger to Close.", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
                    
                    # Draw Translation Overlay
                    if translation_active:
                        # 1. Draw "Scanner" UI
                        # Valid area?
                        cv2.rectangle(frame, (50, 50), (w-50, h-50), (255, 255, 0), 2)
                        cv2.putText(frame, "GOOGLE LENS MODE (TRANSLATING...)", (60, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
                        # 2. Draw Translation Boxes
                        for (tx, ty, tw, th, ttext) in latest_translation_boxes:
                            # Draw stylish background
                            overlay = frame.copy()
                            cv2.rectangle(overlay, (tx, ty), (tx + tw, ty + th), (0, 0, 0), -1)
                            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
                            # Text
                            cv2.putText(frame, ttext, (tx, ty + th - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        
                    # Status Overlays
                    y_off = 30
                    params = [
                        ("Mouse", mouse_control_active, (0, 255, 255)),
                        ("Keyboard", keyboard_view_active, (255, 255, 0)),
                        ("Translation", translation_active, (255, 0, 255)),
                        ("Sound", sound_enabled, (0, 255, 0))
                    ]
                    
                    for name, active, color in params:
                         status = "ON" if active else "OFF"
                         col = color if active else (100, 100, 100)
                         cv2.putText(frame, f"{name}: {status}", (10, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
                         y_off += 30
        
                    if mouse_control_active:
                        cv2.putText(frame, "Pinch Index: Left Click | Middle: Right Click", (10, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        
                    cv2.imshow("Hand Gesture Recognition", frame)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord('r') and args.mode == "record" and len(hands_list) == 1:
                        # Only record if 1 hand
                        print("\nRecording Gesture (Single Hand)...")
                        name = input("Enter gesture name: ")
                        if name:
                            classifier.add_sample(name, hands_list[0]["landmarks"])
                            print(f"Saved gesture '{name}'!")
                else:
                     # If state changed to inactive and we are in normal mode, destroy window
                     # If mouse is active, we KEEP RUNNING but without window.
                     if (not keyboard_view_active and not translation_active) and args.mode == "normal":
                         try:
                             if cv2.getWindowProperty("Hand Gesture Recognition", 0) >= 0:
                                cv2.destroyWindow("Hand Gesture Recognition")
                         except:
                             pass
                             
                    # Small sleep to yield CPU in headless normal mode
                     time.sleep(0.01)
    
    finally:
        print("Cleaning up...")
        try:
            cam.release()
            cv2.destroyAllWindows()
            det_thread.stop()
            sock.close()
            control_socket.close()
        except:
            pass

if __name__ == "__main__":
    main()
