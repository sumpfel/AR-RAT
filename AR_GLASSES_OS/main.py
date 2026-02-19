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

        # Connect Signal ONCE to central handler
        self.sensor_fusion.orientation_changed.connect(self.on_orientation)
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
        
        # HUD Input Routing (High Priority)
        if curr == 1: # HUD Active
             print(f"[Input] HUD Active. Routing action: {action}")
             # Map abstract action to physical pin for HUD compatibility
             import config
             pin = None
             if action == "up": pin = config.PIN_D4
             elif action == "down": pin = config.PIN_C3
             elif action == "left": pin = config.PIN_C4
             elif action == "right": pin = config.PIN_C6
             elif action == "select": pin = config.PIN_C1 # Maybe irrelevant for HUD?

             if pin:
                 if hasattr(self.hud, 'handle_input'):
                     self.hud.handle_input(pin)
                 return

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

    # DEAD CODE REMOVED (on_button_press was not connected)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Recalculate Status Font
        h = self.height()
        # Force Large Size for Status Text (Reduced from 0.05 to 0.04)
        font_size = int(h * 0.04) 
        font_size = max(30, font_size)
        self.label.setStyleSheet(f"color: #00FF00; font-size: {font_size}px; font-weight: bold;")
        
        # State Tracking - REMOVED reset to avoid bug
        # self.last_app_index = 0 

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


    def on_orientation(self, r, p, y, gyro_data, active_targets=0, face_img=None, face_lum=0):
        # Update HUD
        if self.stack.currentIndex() == 1:
            self.hud.update_data(r, p, y, gyro_data, active_targets, face_img, face_lum)
            
        # Update Debug Window (Always, if active)
        if self.debug_window:
            self.debug_window.update_data(r, p, y)

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
             secondary_screen = None
             screens = QApplication.screens()
             for screen in screens:
                 print(f"[UI] Screen Found: {screen.name()} {screen.geometry()}")
                 if config.TARGET_DISPLAY in screen.name():
                     target_screen = screen
                     print(f"[UI] Target Selected: {screen.name()}")
                 else:
                     secondary_screen = screen # Grab any non-target as secondary
             
             if target_screen is None and len(screens) > 1:
                 target_screen = screens[-1]
                 # If we defaulted to last, pick previous as secondary?
                 if len(screens) > 1: secondary_screen = screens[0]

             if target_screen:
                 self.setGeometry(target_screen.geometry())
                 self.showFullScreen()
                 
                 # Explicitly set screen handle
                 if self.windowHandle():
                     self.windowHandle().setScreen(target_screen)
                 
                 # --- Secondary Screen Windows (Laptop) ---
                 if secondary_screen:
                     sec_geo = secondary_screen.geometry()
                     
                     # 1. Debug Window (Cube)
                     from ui.debug_window import DebugWindow
                     self.debug_window = DebugWindow()
                     self.debug_window.setWindowTitle("AROS_Debug")
                     self.debug_window.setObjectName("AROS_Debug")
                     
                     # Move to left half? Hyprland will tile, just show() is often enough.
                     # But setting screen is good.
                     self.debug_window.show() # Normal window for tiling
                     
                     if self.debug_window.windowHandle():
                         self.debug_window.windowHandle().setScreen(secondary_screen)
                         # Optional: Move to ensure it's on that screen
                         self.debug_window.move(sec_geo.x() + 100, sec_geo.y() + 100)

                     # 2. Mirror Window (HUD Copy)
                     # We can reuse SensorFusionHUD class
                     self.mirror_window = SensorFusionHUD()
                     self.mirror_window.setWindowTitle("AROS_Mirror")
                     self.mirror_window.setObjectName("AROS_Mirror")
                     self.mirror_window.resize(600, 800) # Portrait-ish default
                     
                     self.mirror_window.show() # Normal window for tiling
                     
                     if self.mirror_window.windowHandle():
                         self.mirror_window.windowHandle().setScreen(secondary_screen)
                         self.mirror_window.move(sec_geo.x() + 700, sec_geo.y() + 100)
                     
                     print(f"[UI] Launched Debug & Mirror on {secondary_screen.name()}")
                     
                     # Hyprland Force Move (Async)
                     monitor_name = secondary_screen.name()
                     QTimer.singleShot(500, lambda: self.force_hyprland_move("AROS_Debug", monitor_name))
                     QTimer.singleShot(800, lambda: self.force_hyprland_move("AROS_Mirror", monitor_name))

                 else:
                     self.debug_window = None
                     self.mirror_window = None
             else:
                self.showFullScreen()
                self.debug_window = None
                self.mirror_window = None
        else:
            self.show()

    def force_hyprland_move(self, title, monitor):
        """Use hyprctl to force window to correct monitor"""
        try:
            import subprocess
            # 1. Focus Window
            # Use regex to exact match title
            cmd_focus = ["hyprctl", "dispatch", "focuswindow", f"title:^{title}$"]
            subprocess.run(cmd_focus, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 2. Move to Monitor
            cmd_move = ["hyprctl", "dispatch", "movewindow", f"mon:{monitor}"]
            subprocess.run(cmd_move, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[UI] Hyprland: Moved '{title}' to {monitor}")
        except Exception as e:
            print(f"[UI] Hyprland Move Failed: {e}")

    def on_orientation(self, r, p, y, gyro_data, active_targets, face_img, face_lum):
        # Update Main HUD (on Glasses)
        if self.stack.currentIndex() == 1:
            self.hud.update_data(r, p, y, gyro_data, active_targets, face_img, face_lum)
            
        # Update Mirror Window (Always if exists)
        if hasattr(self, 'mirror_window') and self.mirror_window:
            # Sync Mode with Main HUD?
            self.mirror_window.mode = self.hud.mode 
            self.mirror_window.update_data(r, p, y, gyro_data, active_targets, face_img, face_lum)

        # Update Debug Window (Cube)
        if self.debug_window:
            self.debug_window.update_data(r, p, y)

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
