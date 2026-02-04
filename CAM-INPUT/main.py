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
from camera_handler import CameraHandler
from hand_detector import HandDetector
from gesture_classifier import GestureClassifier

from virtual_keyboard import VirtualKeyboard

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
        # Standard OpenCV / X11 / Windows
        cv2.resizeWindow(name, w, h)
        cv2.moveWindow(name, x, y)

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

    detector = HandDetector(max_num_hands=2, min_detection_confidence=0.7)
    classifier = GestureClassifier()
    v_keyboard = VirtualKeyboard()

    print(f"Started in {args.mode} mode. Press 'q' to quit.")
    if args.mode == "record":
        print("Press 'r' to record current gesture (Only works if 1 hand detected).")

    # Keyboard View State
    keyboard_view_active = False
    last_toggle_time = 0
    toggle_cooldown = 1.0 # Reduced from 2.0 to 1.0
    
    # Typing State
    last_key_press_time = 0
    key_press_cooldown = 0.5
    active_key = None

    while True:
        ret, frame = cam.get_frame()
        if not ret:
            print("Failed to get frame")
            break

        # Flip for mirror view
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        
        # Detect
        detection_result = detector.process_frame(frame)
        hands_list = detector.get_landmarks_as_list(detection_result)
        
        udp_data = {
            "compound": "None",
            "gestures": [],
            "timestamp": time.time()
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
                    if len(hands_list) == 2:
                        x_coords = []
                        y_coords = []
                        for hand in hands_list:
                            lms = hand["landmarks"]

                            x_coords.append(int(lms[8]['x'] * w))
                            y_coords.append(int(lms[8]['y'] * h))
                        v_keyboard.better_moving(x_coords, y_coords)
                # Find Index Finger Tip (Landmark 8) of first hand (or search all)
                # Let's support typing with ANY hand
                for hand in hands_list:
                     lms = hand["landmarks"]

                    # cursor to finger

                     # Check PINCH (Typing Trigger)
                     if classifier.is_pinching(lms) and not udp_data['compound'] == "Resize" and not udp_data['compound'] == "Move":
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
                                     v_keyboard.switch_layout("symbols")
                                     print(f"Layout Switched: Symbols")
                                 elif key_hit == "SWITCH_LAYOUT_EMO":
                                     v_keyboard.switch_layout("emojis")
                                     print(f"Layout Switched: Emojis")
                                 else:
                                     print(f"Typing: {key_hit}")
                                     key_data = {
                                         "type": "keydown",
                                         "key": key_hit,
                                         "timestamp": curr_time
                                     }
                                     sock.sendto(json.dumps(key_data).encode('utf-8'), (args.udp_ip, args.udp_port))
                                 
                                 last_key_press_time = curr_time
        
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
        if args.mode in ["debug", "record"] or keyboard_view_active:
            # Draw Keyboard
            if keyboard_view_active:
                v_keyboard.draw(frame, active_key)
            
            detector.draw_landmarks(frame, detection_result)

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

            if hands_list:
                i = 0
                for hand in hands_list:
                    lms = hand["landmarks"]

                    idx_x = int(lms[4]['x'] * w)
                    idx_y = int(lms[4]['y'] * h)
                    #cv2.putText(frame, f"Hand Position {idx_x}", (10, y_offset + 50 + (i*40)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    #cv2.putText(frame, f"Hand Position {idx_y}", (10, y_offset + 70 + (i*40)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    i+=1

            # Display Mode & View Status
            cv2.putText(frame, f"Mode: {args.mode}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            if keyboard_view_active:
                cv2.putText(frame, "KEYBOARD ACTIVE", (10, y_offset + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.putText(frame, "Pinch to Type. Middlefinger to Close.", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            
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
             if not keyboard_view_active and args.mode == "normal":
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
