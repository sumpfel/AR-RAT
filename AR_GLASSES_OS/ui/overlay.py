import sys
import os
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, 
                             QGraphicsOpacityEffect, QGridLayout, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QFont, QPixmap, QIcon

# --- UTILS ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

class MenuOverlay(QWidget):
    value_changed = pyqtSignal(str, object) # key, value

    def __init__(self, parent=None):
        super().__init__(parent)
        print(f"[MenuOverlay] Initializing... Parent: {parent}")
        
        # Geometry matches parent
        if parent:
            self.resize(parent.size())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200)) # Semi-transparent background
            
    def resizeEvent(self, event):
        print(f"[MenuOverlay] Resized to: {self.size().width()}x{self.size().height()}")
        super().resizeEvent(event)
        
        # Debounced Update for Font/Layout
        QTimer.singleShot(100, self.update_fonts)
        QTimer.singleShot(150, self.update_display)

        
        # Data
        self.current_index = 0
        self.menu_items = [
            {"name": "CAMERA", "key": "cam_input", "type": "toggle", "value": False},
            {"name": "TARGETS", "key": "face_tracking", "type": "toggle", "value": True, "dependency": "cam_input"},
            {"name": "MOUSE", "key": "mouse_control", "type": "toggle", "value": False, "dependency": "cam_input"},
            {"name": "KEYBOARD", "key": "keyboard_mode", "type": "toggle", "value": False, "dependency": "cam_input"},
            {"name": "TRANSLATE", "key": "translation_mode", "type": "toggle", "value": False, "dependency": "cam_input"},
            {"name": "HAND", "key": "handedness", "type": "toggle", "value": True}, # True=Right
            {"name": "SOUND", "key": "sound", "type": "slider", "value": 50, "min": 0, "max": 100, "step": 10, "muted": False},
            {"name": "MIC", "key": "mic_volume", "type": "slider", "value": 80, "min": 0, "max": 100, "step": 10, "muted": False},
            {"name": "ZOOM", "key": "text_size", "type": "slider", "value": 24, "min": 12, "max": 48, "step": 2},
            {"name": "VOICE", "key": "voice_cmd", "type": "toggle", "value": True},
            {"name": "WORD", "key": "trigger_word", "type": "text", "value": "bash"}
        ]
        
        self.settings_file = os.path.join(BASE_DIR, "settings.json")
        self.load_settings()
        
        self.initUI()
        self.hide() 

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(10, self.update_fonts)
        QTimer.singleShot(20, self.update_display)
        self.activateWindow()

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    for item in self.menu_items:
                        if item['key'] in data:
                            saved_val = data[item['key']]
                            # Handle simple values and slider objects
                            if isinstance(saved_val, dict) and 'val' in saved_val:
                                item['value'] = saved_val['val']
                                if 'muted' in saved_val:
                                    item['muted'] = saved_val['muted']
                            else:
                                item['value'] = saved_val
                print("[UI] Settings Loaded")
            except Exception as e:
                print(f"[UI] Error loading settings: {e}")

    def save_settings(self):
        data = {}
        for item in self.menu_items:
            if item['type'] == 'separator' or item['type'] == 'action':
                continue
            
            if item['type'] == 'slider' and 'muted' in item:
                 data[item['key']] = {"val": item['value'], "muted": item['muted']}
            else:
                 data[item['key']] = item['value']
                 
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[UI] Error saving settings: {e}")

    def initUI(self):
        if self.layout(): return

        # Fullscreen Background
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(0, 0, 0, 0)

        # Scroll Area
        from PyQt6.QtWidgets import QScrollArea
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        
        # Container for Scroll Area
        # Use a centering logic? User wants "overall size" text. 
        # If it's vertical, we just fill width.
        
        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.layout_container = QVBoxLayout(self.container)
        self.layout_container.setContentsMargins(40, 40, 40, 40)
        self.layout_container.setSpacing(15)
        self.layout_container.setAlignment(Qt.AlignmentFlag.AlignTop) # Align top for long lists

        # Title
        # Title
        # self.title_label = QLabel("AR CONTROL PANEL")
        # self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.title_label.setWordWrap(True) # Wrap Title
        # self.title_label.setStyleSheet("color: #00FF00; font-weight: bold; margin-bottom: 20px; border-bottom: 2px solid #00FF00;")
        # self.layout_container.addWidget(self.title_label)
        
        self.item_widgets = []
        for item in self.menu_items:
            lbl = QLabel()
            lbl.setWordWrap(True) # Wrap Item Text
            self.layout_container.addWidget(lbl)
            self.item_widgets.append(lbl)
            
        self.layout_container.addStretch()
        
        self.scroll.setWidget(self.container)
        self.layout_main.addWidget(self.scroll)
        
        # Initial Font Calc
        self.update_fonts()
        self.update_fonts()
        self.update_display()

    def is_item_enabled(self, item):
        if "dependency" in item:
            dep_key = item["dependency"]
            # Find dependency item
            for i in self.menu_items:
                if i["key"] == dep_key:
                    return i["value"] # Enabled if dependency is True
        return True

    def update_fonts(self):
         # Base Font Size from Window Height
         import config
         screen_h = self.height()
         base_size = int(screen_h * config.FONT_SCALE_RATIO * config.UI_SCALE * 2.0) # Double size as base
         self.base_font_size = max(16, base_size) 
         
         # Update Title Font
         # self.title_label.setFont(QFont("Monospace", int(self.base_font_size * 1.5), QFont.Weight.Bold))

    def update_display(self):
        print(f"[MenuOverlay] Updating Display. {len(self.menu_items)} items.")
        # Get Text Size Modifier from settings
        size_mod = 0
        for item in self.menu_items:
            if item['key'] == 'text_size':
                 # User setting acts as offset to base size? 
                 # Or replacement? 
                 # User said "text size should be overall size".
                 # The setting `text_size` is 12-48. That's pixels.
                 # Let's interpret it as relative offset or just use calculated one if user wants dynamic.
                 # But they also said "if text is set to really big".
                 # So let's use the setting as the MAIN driver but scaled by UI_SCALE?
                 # Actually, let's keep the slider but default it to a reasonable value
                 # and let the user override. 
                 # BUT, the base range 12-48 might be too small for 4k screen.
                 # Let's scale the value by UI_SCALE.
                 import config
                 size_mod = item['value'] * config.UI_SCALE
                 break
        
        final_size = int(size_mod) if size_mod > 0 else self.base_font_size
        font = QFont("Monospace", final_size)
        
        for i, item in enumerate(self.menu_items):
            lbl = self.item_widgets[i]
            
            # Dynamic Font Sizing
            if i == self.current_index:
                 # Selected: Larger and Bold
                 lbl.setFont(QFont("Monospace", int(self.base_font_size * 1.5), QFont.Weight.Bold))
                 prefix = "> "
                 color = "#00FF00"
                 bg = "rgba(0, 255, 0, 30)"
            else:
                 # Unselected: Normal size
                 lbl.setFont(QFont("Monospace", self.base_font_size))
                 prefix = "  "
                 color = "#888888"
                 bg = "transparent"

            enabled = self.is_item_enabled(item)
            if not enabled:
                color = "#444444"
                prefix = ""
            
            text = f"{prefix}{item['name']}"
            
            if item['type'] == 'toggle':
                state = "[ON]" if item['value'] else "[OFF]"
                if item['key'] == 'handedness':
                    state = "[RIGHT]" if item['value'] else "[LEFT]"
                text += f" {state}"
            elif item['type'] == 'slider':
                mute_str = "[MUTED]" if item.get('muted', False) else ""
                text += f" < {item['value']} > {mute_str}"
                if item.get('muted', False) and enabled: color = "#FFAA00"
            elif item['type'] == 'text':
                text += f":\n{item['value']}" # Force newline for value
                
            lbl.setText(text)
            lbl.setStyleSheet(f"color: {color}; background-color: {bg}; padding: 10px; border-radius: 10px;")
            
            # Ensure visible if selected
            if i == self.current_index:
                 self.scroll.ensureWidgetVisible(lbl)

    def navigate(self, direction):
        if not self.isVisible(): return
        
        start_index = self.current_index
        
        if direction == "up":
            for _ in range(len(self.menu_items)):
                self.current_index = (self.current_index - 1) % len(self.menu_items)
                if self.is_item_enabled(self.menu_items[self.current_index]):
                    break
        elif direction == "down":
            for _ in range(len(self.menu_items)):
                self.current_index = (self.current_index + 1) % len(self.menu_items)
                if self.is_item_enabled(self.menu_items[self.current_index]):
                    break
        elif direction in ["left", "right"]:
            self.adjust_value(direction)
            
        self.update_display()

    def adjust_value(self, direction):
        item = self.menu_items[self.current_index]
        if not self.is_item_enabled(item): return
        
        if item['type'] == 'slider':
            delta = -item['step'] if direction == "left" else item['step']
            item['value'] = max(item['min'], min(item['max'], item['value'] + delta))
            
            # Emit full state for sliders with mute, else just value
            if 'muted' in item:
                self.value_changed.emit(item['key'], {"val": item['value'], "muted": item['muted']})
            else:
                 self.value_changed.emit(item['key'], item['value'])
                 
        elif item['type'] == 'toggle':
            item['value'] = not item['value']
            self.value_changed.emit(item['key'], item['value'])
            
        self.save_settings()

    def select(self):
        if not self.isVisible(): return
        item = self.menu_items[self.current_index]
        if not self.is_item_enabled(item): return
        
        if item['type'] == 'toggle':
            item['value'] = not item['value']
            self.value_changed.emit(item['key'], item['value'])
            # If this toggled a dependency (cam_input), we might need to refresh UI heavily or move cursor
            if item['key'] == 'cam_input' and not item['value']:
                # Dependency disabled stuff, ensure cursor isn't on disabled item? 
                # Current item is cam_input so it's fine.
                pass
                
        elif item['type'] == 'slider':
            # Toggle Mute
            item['muted'] = not item['muted']
            self.value_changed.emit(item['key'], {"val": item['value'], "muted": item['muted']})
            
        elif item['type'] == 'action':
            if item['key'] == 'exit':
                self.hide()
            return item
            
        self.save_settings()
        self.update_display()
        return item

# --- APP LAUNCHER ---
class AppLauncherOverlay(QWidget):
    app_launched = pyqtSignal(str) # cmd

    def __init__(self, parent=None):
        super().__init__(parent)
        # self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        # self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # if parent:
        #    self.resize(parent.size())


        # Row 0: Window Controls
        # Apps List
        self.menu_items = [
            {"name": "SENSOR FUSION", "cmd": "SensorFusion", "type": "app"},
            {"name": "AI ASSISTANT", "cmd": "AI_Assistant", "type": "app"},
            {"name": "DISCORD", "cmd": "vesktop", "type": "app"},
            {"name": "FIREFOX", "cmd": "firefox", "type": "app"},
            {"name": "TERMINAL", "cmd": "kitty", "type": "app"},
            {"name": "CLOSE ALL", "cmd": "close_all", "type": "action"}
        ]
        
        self.current_index = 0
        self.item_widgets = []
        
        self.initUI()
        self.hide()

    def initUI(self):
        if self.layout(): return

        # Fullscreen Background
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(0, 0, 0, 0)
        
        from PyQt6.QtWidgets import QScrollArea
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.layout_container = QVBoxLayout(self.container)
        self.layout_container.setContentsMargins(40, 40, 40, 40)
        self.layout_container.setSpacing(20)
        self.layout_container.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll.setWidget(self.container)
        self.layout_main.addWidget(self.scroll)

    def update_display(self):
        # Clear layout safely
        while self.layout_container.count():
            item = self.layout_container.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        import config
        # Use Window Height
        screen_h = self.height()
        base_font_size = int(screen_h * config.FONT_SCALE_RATIO * config.UI_SCALE * 2.0) # Base size
        
        self.item_widgets = []
        self.scroll.verticalScrollBar().setValue(0) # Reset Scroll
        
        for i, item in enumerate(self.menu_items):
            lbl = QLabel()
            lbl.setWordWrap(True)
            
            # Selection Style
            if i == self.current_index:
                 # Selected: Big and Bold
                 lbl.setFont(QFont("Monospace", int(base_font_size * 1.5), QFont.Weight.Bold))
                 prefix = "> "
                 color = "#00FFFF"
                 bg = "rgba(0, 255, 255, 30)"
            else:
                # Normal
                lbl.setFont(QFont("Monospace", base_font_size))
                prefix = "  "
                color = "#888888"
                bg = "transparent"
            
            lbl.setText(f"{prefix}{item['name']}")
            lbl.setStyleSheet(f"color: {color}; background-color: {bg}; padding: 15px; border-radius: 10px;")
            
            self.layout_container.addWidget(lbl)
            self.item_widgets.append(lbl)
            
            if i == self.current_index:
                self.scroll.ensureWidgetVisible(lbl)

    def navigate(self, direction):
        if not self.isVisible(): return
        
        if direction == "up":
            self.current_index = (self.current_index - 1) % len(self.menu_items)
        elif direction == "down":
            self.current_index = (self.current_index + 1) % len(self.menu_items)
            
        self.update_display()

    def select(self):
        if not self.isVisible(): return
        item = self.menu_items[self.current_index]
        print(f"[Launcher] Selected: {item['name']}")
        if item['type'] == 'app':
            self.app_launched.emit(item['cmd'])
            self.hide()
        elif item['type'] == 'action':
            # Handle actions?
            pass
        return item
    
    def show_launcher(self):
        self.show()
        self.network_update_needed = True 
        # self.update_display() # Handled by showEvent
        self.activateWindow()
        self.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(20, self.update_display)
        self.activateWindow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(150, self.update_display)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 230))

class CommandOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())
        
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(self.layout)
        
        self.popup_data = {}
        self.output_log = []
        self.hide()

    def show_confirmation(self, cmd, secret):
        self.popup_data = {"cmd": cmd, "secret": secret}
        self.output_log = []
        self.update_display()
        self.show()
        self.raise_()
        self.activateWindow()
        
    def hide_confirmation(self):
        self.popup_data = {}
        self.hide()
        
    def add_output(self, text):
        self.output_log.append(text)
        self.update_display()
        
    def update_display(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        title = QLabel(f"COMMAND CONFIRMATION")
        title.setFont(QFont("Arial", 40, QFont.Weight.Bold))
        title.setStyleSheet("color: #FF0000; background-color: black; padding: 20px; border: 4px solid white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(title)
        
        cmd_lbl = QLabel(f"Executing:\n{self.popup_data.get('cmd', '???')}")
        cmd_lbl.setFont(QFont("Arial", 30))
        cmd_lbl.setStyleSheet("color: white; background-color: rgba(50,50,50,0.8); padding: 15px;")
        cmd_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(cmd_lbl)
        
        secret = self.popup_data.get('secret', '???')
        instr = QLabel(f"Say '{secret}' or Press SELECT to Confirm.\nSay 'CANCEL' or Press BACK to Cancel.")
        instr.setFont(QFont("Arial", 28))
        instr.setStyleSheet("color: yellow; background-color: black; padding: 15px;")
        instr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(instr)
        
        if self.output_log:
            out_text = "\n".join(self.output_log[-8:])
            out_lbl = QLabel(out_text)
            out_lbl.setFont(QFont("Courier", 20))
            out_lbl.setStyleSheet("color: #00FF00; background-color: black; padding: 10px; border: 2px solid gray;")
            out_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.layout.addWidget(out_lbl)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200))
