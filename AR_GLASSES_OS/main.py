import sys
import os
import signal

# Ensure path includes current dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
from core.input_manager import InputManager
from core.hardware import HardwareManager
from apps.sensor_fusion import SensorFusionModule
from ui.overlay import MenuOverlay, AppLauncherOverlay
from ui.hud import SensorFusionHUD
import config

class AROS(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        
        # Core Systems
        print("[AROS] Starting Core Systems...")
        self.hw = HardwareManager() # FT232H Access
        self.input = InputManager()
        
        # Apps
        # Note: UI components initialized in initUI

        self.sensor_fusion = SensorFusionModule()

        self.sensor_fusion.orientation_changed.connect(self.on_orientation)
        self.sensor_fusion.orientation_changed.connect(self.hud.update_data)
        self.sensor_fusion.start()
        
        # Connect Input
        # Connect Input
        self.input.MENU.connect(self.toggle_menu)
        self.input.LAUNCHER.connect(self.toggle_launcher)
        # self.input.BACK.connect(self.handle_back) # C0 is now LAUNCHER
        
        self.input.SELECT.connect(lambda: self.route_input("select"))
        self.input.UP.connect(lambda: self.route_input("up"))
        self.input.DOWN.connect(lambda: self.route_input("down"))
        self.input.LEFT.connect(lambda: self.route_input("left"))
        self.input.RIGHT.connect(lambda: self.route_input("right"))
        
        print("[AROS] Ready")

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def toggle_menu(self):
        curr = self.stack.currentIndex()
        if curr == 2: # Already Menu -> Close it
            self.stack.setCurrentIndex(self.last_app_index)
            print("[UI] Menu Hidden")
        else:
            # If coming from Launcher(3) or HUD(1) or Status(0)
            if curr in [0, 1]: self.last_app_index = curr # Save if valid return target
            self.stack.setCurrentIndex(2) # Show Menu
            print("[UI] Menu Shown")

    def toggle_launcher(self):
        curr = self.stack.currentIndex()
        if curr == 3: # Already Launcher -> Close it
            self.stack.setCurrentIndex(self.last_app_index)
            print("[UI] Launcher Hidden")
        else:
            if curr in [0, 1]: self.last_app_index = curr
            self.stack.setCurrentIndex(3) # Show Launcher
            print("[UI] Launcher Shown")

    def route_input(self, action):
        curr = self.stack.currentIndex()
        if curr == 2: # Menu
            if action == "select": 
                item = self.menu.select()
                self.handle_menu_action(item)
            else: self.menu.navigate(action)
        elif curr == 3: # Launcher
            if action == "select": self.launcher.select()
            else: self.launcher.navigate(action)
        # else:
        #     print(f"[Input] Ignored {action} (No overlay active)")

    def play_sound(self, sound_file):
        """Play a sound file using aplay (non-blocking)"""
        try:
            import subprocess
            subprocess.Popen(["aplay", sound_file], stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[Sound] Error playing {sound_file}: {e}")

    def on_button_press(self, btn):
        print(f"[Input] Button {btn} Pressed")
        
        # Global Overrides (C2=Menu, C0=Launcher) - unless in HUD Mode?
        # User might want to switch HUD modes.
        # But C2 is Menu. Menu is higher priority?
        # If HUD is active, we might want to capture D4/C3/C4/C6 (Arrows).
        # C2/C0 should still work.
        
        # Special Handling for HUD Input
        try:
            current_idx = self.stack.currentIndex()
            print(f"[Input] Stack Index: {current_idx}, Button: {btn}") # DEBUG
            
            if current_idx == 1: # HUD Active
                # If valid HUD key, pass it
                if btn in [config.PIN_D4, config.PIN_C3, config.PIN_C4, config.PIN_C6]:
                    print(f"[Input] Routing HUD Key {btn} to HUD Module")
                    if hasattr(self.hud, 'handle_input'):
                        self.hud.handle_input(btn)
                    return 
        except Exception as e:
            print(f"[Input] Error checking stack index: {e}")
            import traceback
            traceback.print_exc() 

        if btn == config.FT_MENU: # C2
            self.toggle_menu()
        elif btn == config.FT_LAUNCHER: # C0
            self.toggle_launcher() # Switch directly
        elif btn == config.FT_SELECT: # C1
            curr_widget = self.stack.currentWidget()
            if curr_widget == self.menu_overlay:
                action = self.menu_overlay.select()
                if action:
                    self.handle_menu_action(action)
            elif curr_widget == self.launcher_overlay:
                self.launcher_overlay.select()
            else: self.menu.navigate("select") # Fallback?

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Recalculate Status Font based on new height
        h = self.height()
        import config
        # Force Large Size for Status Text (Reduced from 0.05 to 0.04)
        font_size = int(h * 0.04) 
        font_size = max(30, font_size)
        self.label.setStyleSheet(f"color: #00FF00; font-size: {font_size}px; font-weight: bold;")
        print(f"[UI] Resized to {self.width()}x{self.height()}. Font updated to {font_size}px.")

    def handle_menu_action(self, item):
        if not item: return
        if item['key'] == 'app_launcher':
            self.toggle_launcher() # Switch directly

    def on_setting_change(self, key, value):
        print(f"[Settings] {key} -> {value}")
        # Dynamic Config Update
        if key == "face_tracking":
            config.FACE_TRACKING = value
        elif key == "text_size":
             # Handle zoom if needed, or just let HUD read config
             pass

    def on_app_launch(self, cmd):
        print(f"[Launcher] Launching {cmd}")
        
        if cmd == "SensorFusion":
            self.stack.setCurrentIndex(1) # Show HUD
            self.last_app_index = 1
            print("[AROS] SensorFusion HUD Started")
        else:
             print(f"[AROS] Unknown App: {cmd}")


    def on_orientation(self, r, p, y, gyro, active_targets=0, face_img=None, face_lum=0):
        if not hasattr(self, "_u_count"): self._u_count = 0
        self._u_count += 1
        if self._u_count % 100 == 0:
            print(f"[SensorFusion] R: {r:.1f} P: {p:.1f} Y: {y:.1f} Td: {active_targets}")
            
        # Update HUD
        if hasattr(self, 'hud'):
            self.hud.update_data(r, p, y, gyro, active_targets, face_img, face_lum)

    def initUI(self):
        self.setWindowTitle("AR Glasses OS")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: black;")
        
        # --- STACKED LAYOUT ---
        from PyQt6.QtWidgets import QStackedLayout
        self.stack = QStackedLayout()
        self.setLayout(self.stack)
        
        # Page 0: Status / Waiting
        self.status_page = QWidget()
        l = QVBoxLayout(self.status_page)
        l.setContentsMargins(0, 0, 0, 0)
        l.addStretch() # Center Vertical
        
        screen_geo = QApplication.primaryScreen().geometry()
        print(f"[UI] Primary Screen Geometry: {screen_geo.width()}x{screen_geo.height()}")
        
        # Calculate dynamic font size based on primary initially (resizes later)
        # FORCE HUGE for Status
        font_size = int(screen_geo.height() * 0.08) # 8% of height
        font_size = max(40, font_size)
        
        self.label = QLabel("Waiting for Input...")
        self.label.setStyleSheet(f"color: #00FF00; font-size: {font_size}px; font-weight: bold;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(self.label)
        l.addStretch() # Center Vertical
        self.stack.addWidget(self.status_page) # Index 0
        
        # Page 1: HUD
        self.hud = SensorFusionHUD()
        self.stack.addWidget(self.hud) # Index 1
        
        # Page 2: Menu
        self.menu = MenuOverlay() 
        self.menu.value_changed.connect(self.on_setting_change)
        self.stack.addWidget(self.menu) # Index 2
        
        # Page 3: Launcher
        self.launcher = AppLauncherOverlay()
        self.launcher.app_launched.connect(self.on_app_launch)
        self.stack.addWidget(self.launcher) # Index 3
        
        # State Tracking
        self.last_app_index = 0 # 0=Status, 1=HUD

        # Fullscreen Geometry Logic
        if config.FULLSCREEN:
             target_screen = None
             screens = QApplication.screens()
             for screen in screens:
                 print(f"[UI] Screen Found: {screen.name()} {screen.geometry()}")
                 if config.TARGET_DISPLAY in screen.name():
                     target_screen = screen
                     print(f"[UI] Target Selected: {screen.name()}")
                     break
             if target_screen is None and len(screens) > 1:
                 target_screen = screens[-1]
                 print(f"[UI] Defaulting to secondary display: {target_screen.name()}")
             
             if target_screen:
                 self.setGeometry(target_screen.geometry())
                 self.showFullScreen()
                 self.windowHandle().setScreen(target_screen)
                 print(f"[UI] Window Geometry Set to: {self.geometry()}")
             else:
                self.showFullScreen()
        else:
            self.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Recalculate Status Font based on new height
        h = self.height()
        import config
        # Force Large Size for Status Text
        font_size = int(h * 0.08) # 8% Height
        font_size = max(40, font_size)
        self.label.setStyleSheet(f"color: #00FF00; font-size: {font_size}px; font-weight: bold;")
        print(f"[UI] Resized to {self.width()}x{self.height()}. Font updated to {font_size}px.")
        # else block moved or removed as it was part of previous logic
        # content was: else: self.show()
        # But wait, the original logic was:
        # if config.FULLSCREEN: ... else: self.showFullScreen()
        # AND THEN `else: self.show()` for the if NO FULLSCREEN case?
        # Let's check context.
        pass

        # State Tracking
        # self.last_app_index = 0 # REMOVED: Resets state on resize, breaking HUD input routing

    def log(self, msg):
        print(f"[AROS Input] {msg}")
        self.label.setText(f"ACTION: {msg}")

def main():
    app = QApplication(sys.argv)
    os_window = AROS()
    
    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
