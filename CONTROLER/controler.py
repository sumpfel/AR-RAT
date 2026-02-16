import os
import signal
import subprocess
import time
import sys
import threading
import socket
import json
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from menu_overlay import MenuOverlay, CommandOverlay, AppLauncherOverlay
from voice_handler import VoiceHandler

# Ensure Blinka knows we are using FT232H
os.environ["BLINKA_FT232H"] = "1"

import board
import digitalio

# Configuration
CAM_INPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "CAM-INPUT"))
RUN_SCRIPT = os.path.join(CAM_INPUT_DIR, "run.sh")
UDP_IP = "127.0.0.1"
UDP_PORT_CAM = 5006 # New port for Control Commands

# Add CAM-INPUT to path for HybridMouse
if CAM_INPUT_DIR not in sys.path:
    sys.path.append(CAM_INPUT_DIR)

try:
    from hybrid_mouse import HybridMouse
except ImportError:
    print("Warning: Could not import HybridMouse. Keyboard/Mouse simulation disabled.")
    class HybridMouse:
        def click(self): pass
        def move_relative(self, d): pass
        def type_key(self, k): pass

from PyQt5.QtCore import QObject, pyqtSignal

class ControllerSignals(QObject):
    toggle_menu = pyqtSignal()
    navigate = pyqtSignal(str)
    select = pyqtSignal()
    hide_menu = pyqtSignal()
    voice_feedback = pyqtSignal(str)
    back = pyqtSignal()

class CamController(QObject): # Inherit from QObject for custom slots if needed, or just use signals
    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.overlay = MenuOverlay()
        self.cmd_overlay = CommandOverlay()
        self.launcher_overlay = AppLauncherOverlay() # New Launcher
        self.voice_handler = VoiceHandler(callback=self.voice_callback_thread)
        self.mouse = HybridMouse()
        
        self.state = "NORMAL" # NORMAL, CONFIRMING, RUNNING, FINISHED, LAUNCHER
        self.voice_cmd_data = {}
        self.cmd_process = None
        
        # Connect Signals
        self.signals = ControllerSignals()
        self.signals.toggle_menu.connect(self.toggle_menu_slot)
        self.signals.navigate.connect(self.navigate_slot) # Changed to custom slot for modifiers
        self.signals.select.connect(self.select_slot)
        self.signals.hide_menu.connect(self.overlay.hide_menu)
        self.signals.voice_feedback.connect(self.show_voice_feedback)
        self.signals.back.connect(self.launcher_toggle_slot) # C0 toggles launcher now
        
        # --- BUTTON SETUP ---
        # lowest : c0 (Back/Hide)
        # middle: c1 (Select/Enter)
        # top: c2 (Menu Toggle)
        # 4 arrow buttons: c3(Down), d4(Up), c4(Forward/Left), c6(Backward/Right)
        
        self.pin_map = {
            "c0": board.C0,
            "c1": board.C1,
            "c2": board.C2,
            "c3": board.C3,
            "d4": board.D4,
            "c4": board.C4,
            "c6": board.C6
        }
        
        # Init FT232H
        self.setup_gpio()

        # Connect Overlay Signals
        self.overlay.value_changed.connect(self.handle_setting_change)
        
        self.process = None
        self.running = True
        
        # Voice Handler
        # self.voice_handler = VoiceHandler(callback=self.voice_callback_thread) # Moved up


        # IPC Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Sync Initial State
        self.sync_settings()

    def sync_settings(self):
        # Sync Voice Command State
        for item in self.overlay.menu_items:
            if item["key"] == "voice_cmd" and item["value"]:
                self.voice_handler.start()
            elif item["key"] == "trigger_word":
                self.voice_handler.set_trigger(item["value"])
            elif item["key"] == "sound":
                self.send_command("SET_VOLUME", item["value"])
            elif item["key"] == "mic_volume":
                # Initial mic sync
                pass # Already default or system?
        


        # State Machine
        # NORMAL: Standard Menu/App Control
        # CONFIRMING: Voice Command Confirmation Popup
        # RUNNING: Command Executing (Popup shows output)
        # self.state = "NORMAL" # Moved up
        # self.voice_cmd_data = {} # {cmd, secret} # Moved up
        # self.cmd_process = None # Moved up
        self.secret_words = ["eagle", "ocean", "mountain", "river", "sun", "moon", "star", "forest"]
        import random
        
    def setup_gpio(self):
        # Initialize Buttons
        self.buttons = {}
        for name, pin in self.pin_map.items():
            try:
                # Only init if not already existing (or after release)
                btn = digitalio.DigitalInOut(pin)
                btn.direction = digitalio.Direction.INPUT
                # FT232H: External pull-downs assumed 
                self.buttons[name] = {"obj": btn, "last": False} 
            except Exception as e:
                print(f"Error initializing {name}: {e}")
                
    def release_gpio(self):
        # Release all button resources to free FT232H
        print("Releasing GPIO resources...")
        for name, btn_data in self.buttons.items():
             try:
                 btn_data["obj"].deinit()
             except:
                 pass
        self.buttons = {}
        # Force garbage collection/delay to ensure FTDI release?
        import time
        time.sleep(0.5)

    def is_button_pressed(self, name):
        # Helper to check current state (for modifiers)
        if name in self.buttons:
             return self.buttons[name].get("is_pressed", False)
        return False
        
    # ... (Slots are fine) ...

    def launch_app(self, app):
        cmd_key = app["cmd"]
        name = app["name"]
        print(f"Launching {name} ({cmd_key})...")
        self.launcher_overlay.hide()
        self.state = "NORMAL"
        
        final_cmd = []
        is_exclusive = False # If true, release GPIO
        
        # Determine Command
        if cmd_key == "SensorFusion":
             is_exclusive = True
             # Path: ...
             base_dir = os.path.dirname(CAM_INPUT_DIR)
             script_path = os.path.join(base_dir, "SENSORFUSION", "main.py")
             venv_python = os.path.join(base_dir, "SENSORFUSION", ".venv", "bin", "python")
             if os.path.exists(venv_python):
                 final_cmd = [venv_python, script_path]
             else:
                 final_cmd = [sys.executable, script_path]
                 
        elif cmd_key == "AI_Assistant":
             # User reported it needs separate process but didn't say it uses FT232H
             # But let's keep it standard. 
             # If AI Assistant uses Microphone only, it's fine.
             base_dir = os.path.dirname(CAM_INPUT_DIR)
             script_path = os.path.join(base_dir, "AI_ASSISTANT", "main.py")
             venv_python = os.path.join(base_dir, "AI_ASSISTANT", ".venv", "bin", "python")
             if os.path.exists(venv_python):
                 final_cmd = [venv_python, script_path]
             else:
                 final_cmd = [sys.executable, script_path]

        elif cmd_key == "vesktop":
            final_cmd = ["flatpak", "run", "dev.vencord.Vesktop"]
        elif cmd_key == "firefox":
            final_cmd = ["firefox"]
        elif cmd_key == "kitty":
            final_cmd = ["kitty"]
        else:
            return

        # Launch
        try:
             # Release GPIO if exclusive
             if is_exclusive:
                 self.release_gpio()
                 self.external_process = subprocess.Popen(final_cmd) # Keep handle
             else:
                 subprocess.Popen(final_cmd, start_new_session=True)
                 
        except Exception as e:
             print(f"Launch Error: {e}")
             if is_exclusive: self.setup_gpio() # Re-acquire if failed


    # --- BACKGROUND THREAD LOOP ---
    def check_buttons(self):
        # 1. Check External Process (SensorFusion)
        if hasattr(self, "external_process") and self.external_process:
             ret = self.external_process.poll()
             if ret is None:
                 # It is still running. Buttons are DISABLED.
                 # We could maybe check Keyboard or Voice here if we wanted to Force Kill?
                 return 
             else:
                 # It finished!
                 print(f"App finished with code {ret}. Restoring GPIO...")
                 self.external_process = None
                 self.setup_gpio()
                 return
                 
        # 2. Poll buttons (Normal Operation)
        for name, btn_data in self.buttons.items():
            try:
                btn = btn_data["obj"]
                val = btn.value 
                
                # Logic: Active High
                is_pressed = val 
                
                # Update Current State
                btn_data["is_pressed"] = is_pressed
                
                # Detect Rising Edge
                if is_pressed and not btn_data["last"]:
                    if name == "c2": self.signals.toggle_menu.emit()
                    elif name == "c1": self.signals.select.emit()
                    elif name == "c0": self.signals.back.emit()
                    elif name == "d4": self.signals.navigate.emit("up")
                    elif name == "c3": self.signals.navigate.emit("down")
                    elif name == "c4": self.signals.navigate.emit("left")
                    elif name == "c6": self.signals.navigate.emit("right")
                            
                btn_data["last"] = is_pressed
            except Exception as e:
                print(f"GPIO Error: {e}")
                
    def monitor_process(self):
        # CAM-INPUT monitor
        if self.process:
            ret = self.process.poll()
            if ret is not None:
                try:
                    out, err = self.process.communicate(timeout=0.1)
                except: pass

    # --- SLOTS (Run in Main Thread) ---
    def toggle_menu_slot(self):
        # Button c2: Universal Close / Toggle Menu
        
        # 1. If any overlay is open, close it
        if self.state == "CONFIRMING" or self.state == "FINISHED":
            self.close_popup()
            return
        elif self.state == "LAUNCHER":
            self.launcher_overlay.hide()
            self.state = "NORMAL"
            return
        elif self.overlay.isVisible():
            self.overlay.hide()
            return
            
        # 2. If valid state, Toggle Menu
        if self.state == "NORMAL":
            self.overlay.show()
            self.overlay.activateWindow()
            self.overlay.raise_()
            
    def launcher_toggle_slot(self):
        # Button c0: Toggle App Launcher
        if self.state == "NORMAL":
            self.state = "LAUNCHER"
            self.launcher_overlay.current_index = 0
            self.launcher_overlay.update_display()
            self.launcher_overlay.show()
            self.launcher_overlay.activateWindow()
            self.launcher_overlay.raise_()
        elif self.state == "LAUNCHER":
            self.launcher_overlay.hide()
            self.state = "NORMAL"
            
    def select_slot(self):
        # Button c1
        
        # Modifier Check: UP (d4) + SELECT (c1) -> Close Window (Shortcut)
        if self.is_button_pressed("d4"):
            print("Modifier: UP + SELECT -> Close Window")
            subprocess.run(["hyprctl", "dispatch", "killactive"], stdout=subprocess.DEVNULL)
            return

        if self.state == "CONFIRMING":
            self.execute_voice_command()
            
        elif self.state == "LAUNCHER":
             item = self.launcher_overlay.select()
             if not item: return
             
             itype = item.get("type")
             if itype == "app":
                 self.launch_app(item)
             elif itype == "action":
                 cmd = item.get("cmd")
                 if cmd == "close_active":
                     subprocess.run(["hyprctl", "dispatch", "killactive"], stdout=subprocess.DEVNULL)
                     self.launcher_overlay.hide()
                     self.state = "NORMAL"
                 elif cmd == "close_all":
                     # Not easily done with one dispatch, maybe kill all floating? 
                     # For now just kill active multiple times? or specific logic?
                     # User said "close all windows on top of app launch row".
                     # Assuming "Close Active" is enough for now or just killall?
                     print("Close All not fully implemented, closing active.")
                     subprocess.run(["hyprctl", "dispatch", "killactive"], stdout=subprocess.DEVNULL)
                     
             elif itype == "desktop":
                 val = item.get("val")
                 subprocess.run(["hyprctl", "dispatch", "workspace", str(val)], stdout=subprocess.DEVNULL)
                 self.launcher_overlay.hide()
                 self.state = "NORMAL"
                 
        elif self.state == "NORMAL":
            if self.overlay.isVisible():
                action = self.overlay.select()
                self.handle_menu_action(action)
            else:
                # Normal Select (Left Click)
                self.mouse.click()

    def navigate_slot(self, direction):
        # Modifier Check: DOWN (c3) + LEFT/RIGHT -> Workspace Switch (Shortcut)
        if self.is_button_pressed("c3") and direction in ["left", "right"]:
            print(f"Modifier: DOWN + {direction.upper()} -> Switch Desktop")
            if direction == "left":
                subprocess.run(["hyprctl", "dispatch", "workspace", "m-1"], stdout=subprocess.DEVNULL)
            else:
                subprocess.run(["hyprctl", "dispatch", "workspace", "m+1"], stdout=subprocess.DEVNULL)
            return
            
        if self.state == "LAUNCHER":
            self.launcher_overlay.navigate(direction)
        elif self.overlay.isVisible():
            self.overlay.navigate(direction)
        else:
            self.mouse.move_relative(direction) 




    def send_command(self, command, value=None):
        data = {"command": command, "value": value}
        try:
            self.sock.sendto(json.dumps(data).encode('utf-8'), (UDP_IP, UDP_PORT_CAM))
            print(f"Sent: {data}")
        except Exception as e:
            print(f"UDP Error: {e}")

    def start_cam_input(self):
        if self.process is None or self.process.poll() is not None:
            print(f"Starting CAM-INPUT in {CAM_INPUT_DIR}...")
            self.process = subprocess.Popen(
                [RUN_SCRIPT],
                cwd=CAM_INPUT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                preexec_fn=os.setsid
            )
            print(f"Process started with PID: {self.process.pid}")
        else:
            print("CAM-INPUT is already running.")

    def stop_cam_input(self):
        if self.process:
            print("Stopping CAM-INPUT...")
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    print("Force killing CAM-INPUT...")
                    self.process.kill()
            self.process = None
            print("CAM-INPUT stopped.")

    def handle_setting_change(self, key, value):
        print(f"Setting Change: {key} -> {value}")
        if key == "sound":
            # Send volume command to CAM-INPUT
            self.send_command("SET_VOLUME", value)
            
            # Control System Volume via amixer
            try:
                subprocess.run(["amixer", "sset", "Master", f"{value}%"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Volume Error: {e}")
        elif key == "mic_volume":
            # Control Mic Volume via amixer
            try:
                subprocess.run(["amixer", "sset", "Capture", f"{value}%"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Mic Volume Error: {e}")

    def voice_callback_thread(self, data):
        # Called from Voice Thread -> Emit signal to Main Thread
        # data is now a dict
        self.signals.voice_feedback.emit(json.dumps(data)) # Pass as JSON string to signal

    def show_voice_feedback(self, data_str):
        data = json.loads(data_str)
        dtype = data.get("type")
        
        if dtype == "command_request":
            cmd = data.get("cmd")
            self.initiate_confirmation(cmd)
            
        elif dtype == "text":
            text = data.get("text")
            print(f"Voice Text: {text}")
            
            if self.state == "CONFIRMING":
                secret = self.voice_cmd_data.get("secret", "").lower()
                if secret in text:
                    self.execute_voice_command()
                elif "cancel" in text:
                    self.cancel_voice_command()
                    
            elif self.state == "RUNNING":
                if "stop" in text:
                    self.stop_command_process()
                elif "close" in text:
                    # Only close if finished? User said "close stops and closes it if/not finished??"
                    # User: "if not finished 'close' stops and closes it"
                    self.stop_command_process()
                    self.close_popup() # Just try closing (cleanup will handle process)

            elif self.state == "FINISHED":
                 if "close" in text:
                     self.close_popup()

    def initiate_confirmation(self, cmd):
        if self.state != "NORMAL": return # Busy
        
        import random
        secret = random.choice(self.secret_words)
        self.voice_cmd_data = {"cmd": cmd, "secret": secret}
        self.state = "CONFIRMING"
        
        self.cmd_overlay.show_confirmation(cmd, secret)

    def execute_voice_command(self):
        if self.state != "CONFIRMING": return
        
        cmd = self.voice_cmd_data.get("cmd")
        print(f"Executing Voice Command: {cmd}")
        
        self.state = "RUNNING"
        self.cmd_overlay.add_output(f"STARTED: {cmd}")
        
        # Start Process
        try:
            # Use shell=True for complex commands, but safety risk is accepted by user via confirmation
            self.cmd_process = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                preexec_fn=os.setsid 
            )
            
            # Start a thread to read output
            t = threading.Thread(target=self.read_process_output, args=(self.cmd_process,))
            t.daemon = True
            t.start()
            
        except Exception as e:
            self.cmd_overlay.add_output(f"Failed to start: {e}")
            self.state = "FINISHED"

    def read_process_output(self, process):
        try:
            for line in process.stdout:
                line = line.strip()
                if line:
                    # We need to update UI from Main Thread, but we are in BG thread
                    # Use signal? Or just reuse voice_feedback signal with type="output"?
                    # Let's create a specialized path or just hack it.
                    # QTimer.singleShot(0, lambda: self.overlay.add_output(line)) works if thread safe?
                    # Safer: Emit signal.
                    # Re-use voice_feedback signal: {"type": "output", "text": line}
                    self.signals.voice_feedback.emit(json.dumps({"type": "output", "text": line}))
                    
            process.wait()
            # Finished
            self.signals.voice_feedback.emit(json.dumps({"type": "process_finished", "code": process.returncode}))
            
        except Exception as e:
            print(f"Read Error: {e}")

    # Handle output signal in show_voice_feedback (need to update it)
    # Refactoring show_voice_feedback to handle "output" and "process_finished"
    
    def cancel_voice_command(self):
        self.state = "NORMAL"
        self.cmd_overlay.hide_confirmation()
        self.voice_cmd_data = {}

    def stop_command_process(self):
        if self.cmd_process and self.cmd_process.poll() is None:
            self.cmd_overlay.add_output("Stopping (SIGTERM)...")
            self.cmd_process.terminate()
            # State remains RUNNING until process actually exits and thread emits "process_finished"

    def kill_command_process(self):
        if self.cmd_process and self.cmd_process.poll() is None:
            self.cmd_overlay.add_output("Force Killing (SIGKILL)...")
            self.cmd_process.kill()

    def close_popup(self):
        # Allow closing even if running (user said "stop and close")
        if self.cmd_process and self.cmd_process.poll() is None:
             self.stop_command_process()
             
        self.state = "NORMAL"
        self.cmd_overlay.hide_confirmation()

    def revert_title(self, text):
        self.overlay.title_label.setText(text)
        self.overlay.title_label.setStyleSheet("color: #00FF00; background-color: transparent; margin-bottom: 20px;")

    def handle_menu_action(self, action):
        if not action: return
        
        key = action["key"]
        val = action["value"]
        
        print(f"Menu Action: {key} = {val}")
        
        if key == "cam_input":
            if val: self.start_cam_input()
            else: self.stop_cam_input()
        elif key == "mouse_control":
            self.send_command("TOGGLE_MOUSE", val)
        elif key == "handedness":
            hand_str = "Right" if val else "Left"
            self.send_command("SET_HANDEDNESS", hand_str)
        elif key == "keyboard_mode":
            self.send_command("TOGGLE_KEYBOARD", val)
        elif key == "translation_mode":
            self.send_command("TOGGLE_TRANSLATION", val)
        elif key == "sound":
            self.send_command("TOGGLE_SOUND", val)
        elif key == "voice_cmd":
            if val: self.voice_handler.start()
            else: self.voice_handler.stop()
        elif key == "trigger_word":
             if self.voice_handler:
                 self.voice_handler.set_trigger(val)
        elif key == "exit":
            self.overlay.hide()
            
    def show_voice_feedback(self, data_str):
        data = json.loads(data_str)
        dtype = data.get("type")
        
        if dtype == "command_request":
            cmd = data.get("cmd")
            self.initiate_confirmation(cmd)
            
        elif dtype == "text":
            text = data.get("text")
            print(f"Voice Text: {text}")
            
            if self.state == "CONFIRMING":
                secret = self.voice_cmd_data.get("secret", "").lower()
                if secret in text:
                    self.execute_voice_command()
                elif "cancel" in text:
                    self.cancel_voice_command()
                    
            elif self.state == "RUNNING":
                if "stop" in text:
                    self.stop_command_process()
                elif "close" in text:
                    self.stop_command_process()
                    self.close_popup()

            elif self.state == "FINISHED":
                 if "close" in text:
                     self.close_popup()
                     
        elif dtype == "output":
             text = data.get("text")
             self.cmd_overlay.add_output(text)
             
        elif dtype == "process_finished":
             code = data.get("code")
             self.cmd_overlay.add_output(f"Finished with code: {code}")
             self.state = "FINISHED"

    # --- BACKGROUND THREAD LOOP ---


    def monitor_process(self):
        if self.process:
            ret = self.process.poll()
            if ret is not None:
                print(f"CAM-INPUT process ended with return code {ret}")
                # Read output if any (we piped stdout/stderr)
                try:
                    out, err = self.process.communicate(timeout=0.1)
                    if out: print(f"CAM-INPUT STDOUT:\n{out}")
                    if err: print(f"CAM-INPUT STDERR:\n{err}")
                except:
                    pass
                self.process = None

    def input_loop(self):
        while self.running:
            self.check_buttons()
            self.monitor_process()
            time.sleep(0.05)

    def run(self):
        # Start Input Thread
        t = threading.Thread(target=self.input_loop)
        t.daemon = True
        t.start()
        
        # Start GUI Loop (Main Thread)
        try:
            sys.exit(self.app.exec_())
        except KeyboardInterrupt:
            self.running = False
            self.stop_cam_input()

if __name__ == "__main__":
    controller = CamController()
    controller.run()
