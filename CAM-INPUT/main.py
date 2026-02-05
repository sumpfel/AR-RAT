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
#import google.generativeai as genai
from PIL import Image
import os
import json

from virtual_keyboard import VirtualKeyboard

# --- TRANSLATION GLOBAL STATE ---
# Shared between main thread and translation thread
translation_active = False
latest_translation_boxes = [] # List of (x, y, w, h, text)
is_translating = False
api_key_loaded = False

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

    #     # Prepare Image
    #     pil_image = Image.fromarray(frame_copy)

    #     # Call Gemini
    #     model = genai.GenerativeModel('gemini-1.5-flash')

    #     prompt = (
    #         "Detect all visible text in this image. "
    #         "Translate each detected text block into German. "
    #         "Return a JSON list of objects. Each object must have: "
    #         "'text' (original text), 'translation' (German translation), "
    #         "and 'box_2d' (bounding box [ymin, xmin, ymax, xmax] normalized 0-1000). "
    #         "If no text, return empty list. Output ONLY JSON."
    #     )

    #     response = model.generate_content([prompt, pil_image])

    #     try:
    #         # Clean response
    #         text = response.text.replace("```json", "").replace("```", "").strip()
    #         data = json.loads(text)

    #         new_boxes = []
    #         h_img, w_img, _ = frame_copy.shape

    #         for item in data:
    #             if "translation" in item and "box_2d" in item:
    #                 ymin, xmin, ymax, xmax = item["box_2d"]
    #                 # Convert 0-1000 to pixels
    #                 x = int((xmin / 1000) * w_img)
    #                 y = int((ymin / 1000) * h_img)
    #                 w = int((xmax - xmin) / 1000 * w_img)
    #                 h = int((ymax - ymin) / 1000 * h_img)

    #                 translated_text = item["translation"]
    #                 new_boxes.append((x, y, w, h, translated_text))

    #         latest_translation_boxes = new_boxes
    #         print(f"Gemini Translation: Found {len(new_boxes)} blocks.")

    #     except Exception as e:
    #         print(f"Gemini Parse Error: {e} | Raw: {response.text[:100]}...")

    # except Exception as e:
    #     print(f"Gemini API Error: {e}")
    # finally:
    #     is_translating = False

def get_screen_resolution():
    try:
        output = subprocess.check_output("xrandr | grep '*' | head -n1", shell=True).decode()
        match = re.search(r"(\d+)x(\d+)", output)
        if match:
            return int(match.group(1)), int(match.group(2))
    except:
        pass
    return 1920, 1080 # Fallback




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
                # 1. Ensure TILED (Not Floating) 
                # Hyprland may spawn it floating by default. We want it to take up space in the layout (Tiled).
                if is_floating:
                    subprocess.run(["hyprctl", "dispatch", "setfloating", f"address:{target_address}"], stdout=subprocess.DEVNULL) # Toggle off? or Set?
                    # "setfloating" with specific target usually toggles in dispatch context if no arg provided.
                    # We call togglefloating explicitly to change state. 
                    # Actually standard dispatch is `togglefloating`. 
                    # But we want to FORCE Tiled.
                    # We will assume `setfloating` without args toggles. 
                    # If we use `setfloating 0`? No.
                    # We will use `togglefloating` if it IS floating.
                    subprocess.run(["hyprctl", "dispatch", "togglefloating", f"address:{target_address}"], stdout=subprocess.DEVNULL)
                    print(f"Hyprland: Set {name} to TILED")
                    time.sleep(0.1)

                # 2. Attempt to move window DOWN to force bottom split
                # This works in Dwindle (pushes new split down) or Master (swaps?)
                # We try 'movewindow d' multiple times to reach bottom.
                subprocess.run(["hyprctl", "dispatch", "movewindow", "d"], stdout=subprocess.DEVNULL)
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

    # UDP Setup
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Targeting UDP {args.udp_ip}:{args.udp_port}")
    
    SCREEN_WIDTH, SCREEN_HEIGHT = get_screen_resolution()
    print(f"Detected Screen Resolution: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")
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

    # Adaptive detection state
    detection_frame_skip = 1
    frame_counter_adaptive = 0
    last_detection_result = None
    last_hands_list = []

    print(f"Started in {args.mode} mode. Press 'q' to quit.")
    if args.mode == "record":
        print("Press 'r' to record current gesture (Only works if 1 hand detected).")

    # Keyboard View State
    keyboard_view_active = False
    translation_view_active = False # New Translation Mode
    last_toggle_time = 0
    toggle_cooldown = 1.0
    
    # Typing State
    last_key_press_time = 0
    key_press_cooldown = 0.5
    active_key = None

    while True:
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

            # Adjust skip rate based on FPS
            if fps_avg < target_fps * 0.5:
                # If we are below half target FPS, skip frames
                # If target is 30 and we have 15, maybe skip 1 (detect every 2nd)
                # If we have 5, skip more.
                detection_frame_skip = max(1, min(10, int(target_fps / max(1, fps_avg))))
            else:
                detection_frame_skip = 1

        # Detect (Adaptive Skipping)
        frame_counter_adaptive += 1
        if frame_counter_adaptive >= detection_frame_skip or last_detection_result is None:
            detection_result = detector.process_frame(frame)
            hands_list = detector.get_landmarks_as_list(detection_result)

            # Hand Filtering: Only keep hands within distance (size > 0.1)
            # Strategy: Split into LEFT and RIGHT groups.
            # For each group, keep only the LARGEST hand (closest to camera).

            hands_left = []
            hands_right = []

            for hand in hands_list:
                lms = hand["landmarks"]
                # Calculate "size" as distance between wrist (0) and middle base (9)
                # This is a robust proxy for distance from camera
                size = math.hypot(lms[0]['x'] - lms[9]['x'], lms[0]['y'] - lms[9]['y'])
                hand["size"] = size

                # Minimum size threshold (ignores hands too far away)
                if size > 0.1:
                    if hand["label"] == "Left":
                        hands_left.append(hand)
                    else: # Right or Unknown (treat as Right/General)
                        hands_right.append(hand)

            # Select best candidate for each side
            final_hands = []

            if hands_left:
                # Sort descending by size -> largest first
                hands_left.sort(key=lambda x: x["size"], reverse=True)
                final_hands.append(hands_left[0]) # Keep biggest Left

            if hands_right:
                hands_right.sort(key=lambda x: x["size"], reverse=True)
                final_hands.append(hands_right[0]) # Keep biggest Right

            hands_list = final_hands
            last_detection_result = detection_result
            last_hands_list = hands_list
            frame_counter_adaptive = 0
        else:
            detection_result = last_detection_result
            hands_list = last_hands_list
        
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
            
            # Check Actions based on gestures
            for g in udp_data["gestures"]:
                # PEACE -> Toggle Keyboard ON
                if g["gesture"] == "Peace":
                    if not keyboard_view_active and (curr_time - last_toggle_time > toggle_cooldown):
                        keyboard_view_active = True
                        translation_view_active = False # Disable Translation
                        last_toggle_time = curr_time
                        print("Keyboard View: ON")
                        
                        # Move to bottom half
                        target_h = SCREEN_HEIGHT // 2
                        set_window_geometry("Hand Gesture Recognition", 0, target_h, SCREEN_WIDTH, target_h)

                # STOP -> Toggle Keyboard OFF
                elif g["gesture"] == "Middle Finger":
                     # Reduce requirement for closing
                     if keyboard_view_active and (curr_time - last_toggle_time > toggle_cooldown):
                         should_close_keyboard = True
            
            # Typing Logic (Only if keyboard active)
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
                elif udp_data['compound'] == "Translate":
                    filename = datetime.now().strftime("screenshots/frame_%Y%m%d_%H%M%S.jpg")
                    cv2.imwrite(filename, frame)

                # Find Index Finger Tip (Landmark 8) of first hand (or search all)
                # Let's support typing with ANY hand
                for hand in hands_list:

                    lms = hand["landmarks"]

                    size = hand.get("size", 0)
                    cv2.putText(frame, f"Size: {size:.2f}", (10, 540), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

                    # Check PINCH (Typing Trigger)
                    if classifier.is_pinching(lms) and not udp_data['compound'] == "Resize" and not udp_data['compound'] == "Move":
                        # Using 0.15 threshold as before, but now based on size calculated earlier
                        if size > 0.15:
                            # Get Index Tip Coords (normalized)
                            idx_x = int(lms[8]['x'] * w)
                            idx_y = int(lms[8]['y'] * h)
                            # Check Key Hit
                            key_hit = v_keyboard.get_key_at(idx_x, idx_y)
                            if key_hit:
                                active_key = key_hit
                                # Send Key Event (Debounced)
                                if curr_time - last_key_press_time > key_press_cooldown:
                                    # Local Events
                                    if key_hit == "SWITCH_LAYOUT_SYM":
                                        # Now cycles: Default -> Symbols -> Emojis -> Default
                                        v_keyboard.switch_layout()
                                        print(f"Layout Switched. Mode: {v_keyboard.layout_mode}")
                                    else:
                                        # Standard Key
                                        print(f"Typing: {key_hit}")
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
             print("Keyboard View: OFF")
             # Restore? Maybe stick to top right or center
             # For now, let's just make it smaller and center it ? Or just leave it?
             # User asked for split screen behavior. If OFF, maybe full screen or standard size?
             # Let's restore a "normal" size
             # Let's restore a "normal" size
             set_window_geometry("Hand Gesture Recognition", (SCREEN_WIDTH-1280)//2, (SCREEN_HEIGHT-720)//2, 1280, 720)

        # ---------------------------------------------------------
        # TRANSLATION MODE LOGIC (Google Lens Style)
        # ---------------------------------------------------------
        if udp_data['compound'] == "Translate":
             if (curr_time - last_toggle_time > toggle_cooldown):
                 translation_view_active = not translation_view_active
                 last_toggle_time = curr_time
                 print(f"Translation Mode: {'ON' if translation_view_active else 'OFF'}")

                 if translation_view_active:
                     keyboard_view_active = False # Disable Keyboard if Translation opens
                     # Translation Mode -> FULL SCREEN (Lens)
                     set_window_geometry("Hand Gesture Recognition", 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
                 else:
                     # Restore default
                     set_window_geometry("Hand Gesture Recognition", (SCREEN_WIDTH-1280)//2, (SCREEN_HEIGHT-720)//2, 1280, 720)

        if translation_view_active:
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

        # Prepare Gesture UDP Packet
        # Clean data
        for g in udp_data["gestures"]:
            if "wrist" in g: del g["wrist"]

        # Only send Gesture UDP if NOT typing? Or always?
        # Let's always send it, but maybe add keyboard status
        udp_data["keyboard_active"] = keyboard_view_active
        json_data = json.dumps(udp_data).encode('utf-8')
        sock.sendto(json_data, (args.udp_ip, args.udp_port))

        # Visualization
        if args.mode in ["debug", "record"] or keyboard_view_active or translation_view_active:
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
            if translation_view_active:
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
             if not keyboard_view_active and not translation_view_active and args.mode == "normal":
                 try:
                     if cv2.getWindowProperty("Hand Gesture Recognition", 0) >= 0:
                        cv2.destroyWindow("Hand Gesture Recognition")
                 except:
                     pass
                     
            # Small sleep to yield CPU in headless normal mode
             time.sleep(0.01)
        


    cam.release()
    cv2.destroyAllWindows()
    sock.close()

if __name__ == "__main__":
    main()
