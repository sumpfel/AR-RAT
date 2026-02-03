import cv2
import argparse
import socket
import json
import time
from camera_handler import CameraHandler
from hand_detector import HandDetector
from gesture_classifier import GestureClassifier

from virtual_keyboard import VirtualKeyboard

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

    # Initialize Modules
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

        # Handle Interaction Layer (Keyboard) - BEFORE classifier or parallel
        # We need landmarks for interaction
        
        should_close_keyboard = False

        if hands_list:
            # Predict Gestures
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
                
                # STOP -> Toggle Keyboard OFF
                elif g["gesture"] == "Stop":
                     # Reduce requirement for closing
                     if keyboard_view_active and (curr_time - last_toggle_time > toggle_cooldown):
                         should_close_keyboard = True
            
            # Typing Logic (Only if keyboard active)
            active_key = None
            if keyboard_view_active:
                # Find Index Finger Tip (Landmark 8) of first hand (or search all)
                # Let's support typing with ANY hand
                for hand in hands_list:
                     lms = hand["landmarks"]
                     
                     # Check PINCH (Typing Trigger)
                     if classifier.is_pinching(lms):
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
        
        # Apply Logic Changes (delayed to allow logic above to complete)
        if should_close_keyboard and (time.time() - last_toggle_time > toggle_cooldown):
             keyboard_view_active = False
             last_toggle_time = time.time()
             print("Keyboard View: OFF")

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
            if keyboard_view_active:
                cv2.putText(frame, "KEYBOARD ACTIVE", (10, y_offset + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.putText(frame, "Pinch to Type. Stop to Close.", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            
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
