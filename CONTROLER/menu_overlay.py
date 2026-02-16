import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QPainter

class CommandOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.popup_data = {}
        self.output_log = []
        
    def initUI(self):
        # Window Setup
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Full Screen
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())
        
        # Layout
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignCenter)
        self.setLayout(self.layout)
        
    def show_confirmation(self, cmd, secret):
        self.popup_data = {"cmd": cmd, "secret": secret}
        self.output_log = []
        self.update_display()
        self.show()
        
    def hide_confirmation(self):
        self.popup_data = {}
        self.hide()
        
    def add_output(self, text):
        self.output_log.append(text)
        self.update_display()
        
    def update_display(self):
        # Clear
        for i in reversed(range(self.layout.count())): 
            widget = self.layout.itemAt(i).widget()
            if widget: widget.setParent(None)
            
        # Draw Background
        # We can't draw in paintEvent easily if we want widgets on top, 
        # but let's just use stylesheets for widgets or a container.
        # Actually paintEvent is better for full screen dimming.
        
        # Title
        title = QLabel(f"COMMAND CONFIRMATION")
        title.setFont(QFont("Arial", 40, QFont.Bold))
        title.setStyleSheet("color: #FF0000; background-color: black; padding: 20px; border: 4px solid white;")
        title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title)
        
        # Command
        cmd_lbl = QLabel(f"Executing:\n{self.popup_data.get('cmd', '???')}")
        cmd_lbl.setFont(QFont("Arial", 30))
        cmd_lbl.setStyleSheet("color: white; background-color: rgba(50,50,50,0.8); padding: 15px;")
        cmd_lbl.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(cmd_lbl)
        
        # Instructions
        secret = self.popup_data.get('secret', '???')
        instr = QLabel(f"Say '{secret}' or Press SELECT to Confirm.\nSay 'CANCEL' or Press BACK to Cancel.")
        instr.setFont(QFont("Arial", 28))
        instr.setStyleSheet("color: yellow; background-color: black; padding: 15px;")
        instr.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(instr)
        
        # Output Area
        if self.output_log:
            out_text = "\n".join(self.output_log[-8:]) # Show last 8 lines (larger font takes space)
            out_lbl = QLabel(out_text)
            out_lbl.setFont(QFont("Courier", 20))
            out_lbl.setStyleSheet("color: #00FF00; background-color: black; padding: 10px; border: 2px solid gray;")
            out_lbl.setAlignment(Qt.AlignLeft)
            self.layout.addWidget(out_lbl)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 200)) # Darker background for command

class AppLauncherOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        
        # Row 0: Window Controls
        self.row_controls = [
            {"name": "Close Active", "type": "action", "cmd": "close_active", "icon": "X"},
            {"name": "Close All", "type": "action", "cmd": "close_all", "icon": "XX"}
        ]
        
        # Row 1: Apps
        self.row_apps = [
            {"name": "SensorFusion", "type": "app", "cmd": "SensorFusion", "icon": "S"},
            {"name": "AI Assistant", "type": "app", "cmd": "AI_Assistant", "icon": "A"},
            {"name": "Vesktop", "type": "app", "cmd": "vesktop", "icon": "V"},
            {"name": "Firefox", "type": "app", "cmd": "firefox", "icon": "F"},
            {"name": "Kitty", "type": "app", "cmd": "kitty", "icon": "K"}
        ]
        
        # Row 2: Desktops
        self.row_desktops = [
            {"name": "Desktop 1", "type": "desktop", "val": 1, "icon": "1"},
            {"name": "Desktop 2", "type": "desktop", "val": 2, "icon": "2"},
            {"name": "Desktop 3", "type": "desktop", "val": 3, "icon": "3"},
            {"name": "Desktop 4", "type": "desktop", "val": 4, "icon": "4"}
        ]
        
        self.rows = [self.row_controls, self.row_apps, self.row_desktops]
        self.row_labels = ["WINDOW CONTROL", "APPS", "WORKSPACES"]
        
        self.current_row = 1 # Start on Apps
        self.current_col = 0
        
    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())
        
        # Main Layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignCenter)
        self.setLayout(self.main_layout)
        
    def update_display(self):
        # Clear main layout
        for i in reversed(range(self.main_layout.count())): 
            item = self.main_layout.itemAt(i)
            if item.widget(): item.widget().setParent(None)
            
        # Title
        title = QLabel("LAUNCHER & CONTROL")
        title.setFont(QFont("Arial", 40, QFont.Bold))
        title.setStyleSheet("color: #00FFFF; background-color: transparent; margin-bottom: 30px;")
        title.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title)
        
        # Render Rows
        for r_idx, row_items in enumerate(self.rows):
            # Row Label
            lbl = QLabel(self.row_labels[r_idx])
            lbl.setFont(QFont("Arial", 16, QFont.Bold))
            lbl.setStyleSheet("color: #AAAAAA; margin-top: 10px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.main_layout.addWidget(lbl)
            
            # Row Container
            container = QWidget()
            hbox = QHBoxLayout()
            hbox.setSpacing(20)
            hbox.setAlignment(Qt.AlignCenter)
            container.setLayout(hbox)
            
            for c_idx, item in enumerate(row_items):
                # Widget
                w = QLabel()
                w.setFixedSize(180, 180)
                w.setAlignment(Qt.AlignCenter)
                w.setText(f"{item['icon']}\n{item['name']}")
                
                # Check Selection
                is_selected = (r_idx == self.current_row and c_idx == self.current_col)
                
                if is_selected:
                    w.setStyleSheet("background-color: #00FF00; color: black; border: 5px solid white; border-radius: 20px;")
                    w.setFont(QFont("Arial", 22, QFont.Bold))
                elif r_idx == self.current_row:
                    # Item in active row but not selected
                     w.setStyleSheet("background-color: rgba(60,60,60,0.9); color: white; border: 2px solid #555; border-radius: 20px;")
                     w.setFont(QFont("Arial", 18))
                else:
                    # Item in inactive row
                    w.setStyleSheet("background-color: rgba(30,30,30,0.6); color: #888; border: 1px solid #333; border-radius: 20px;")
                    w.setFont(QFont("Arial", 16))
                    
                hbox.addWidget(w)
                
            self.main_layout.addWidget(container)

    def navigate(self, direction):
        if not self.isVisible(): return
        
        if direction == "up":
            self.current_row = max(0, self.current_row - 1)
            # Clamp Col
            self.current_col = min(self.current_col, len(self.rows[self.current_row]) - 1)
            
        elif direction == "down":
            self.current_row = min(len(self.rows) - 1, self.current_row + 1)
            # Clamp Col
            self.current_col = min(self.current_col, len(self.rows[self.current_row]) - 1)
            
        elif direction == "left":
            self.current_col = (self.current_col - 1) % len(self.rows[self.current_row])
            
        elif direction == "right":
            self.current_col = (self.current_col + 1) % len(self.rows[self.current_row])
        
        self.update_display()

    def select(self):
        if not self.isVisible(): return None
        return self.rows[self.current_row][self.current_col]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 230))



class MenuOverlay(QWidget):
    value_changed = pyqtSignal(str, object) # key, value

    def __init__(self):
        super().__init__()
        self.initUI()
        
        self.menu_items = [
            {"name": "Camera Input", "key": "cam_input", "type": "toggle", "value": False},
            {"name": "Mouse Control", "key": "mouse_control", "type": "toggle", "value": False},
            {"name": "Keyboard Mode", "key": "keyboard_mode", "type": "toggle", "value": False},
            {"name": "Translation Mode", "key": "translation_mode", "type": "toggle", "value": False},
            {"name": "Sound Volume", "key": "sound", "type": "slider", "value": 50},
            {"name": "Voice Command", "key": "voice_cmd", "type": "toggle", "value": False},
            {"name": "--- ADVANCED ---", "key": "sep", "type": "separator", "value": None},
            {"name": "Handedness", "key": "handedness", "type": "toggle", "value": True}, # True=Right, False=Left
            {"name": "Mic Volume", "key": "mic_volume", "type": "slider", "value": 50},
            {"name": "Trigger Word", "key": "trigger_word", "type": "input", "value": "bash"},
            {"name": "Exit", "key": "exit", "type": "action", "value": None}
        ]
        self.settings_file = "settings.json"
        
        self.load_settings()
        
        self.current_index = 0
        self.is_visible = False
        self.update_display()


    def load_settings(self):
        import json
        import os
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    for item in self.menu_items:
                        if item["key"] in data:
                            item["value"] = data[item["key"]]
                print("Settings loaded.")
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_settings(self):
        import json
        data = {}
        for item in self.menu_items:
            if item["type"] != "separator" and item["type"] != "action":
                data[item["key"]] = item["value"]
        
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=4)
            print("Settings saved.")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150)) # Semi-transparent black

    def initUI(self):
        # Window Setup
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Full Screen Overlay
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())

        # Layout
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignCenter)
        self.setLayout(self.layout)

        # Title
        self.title_label = QLabel("AR CONTROL PANEL")
        self.title_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.title_label.setStyleSheet("color: #00FF00; background-color: transparent; margin-bottom: 20px;")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title_label)

    def update_display(self):
        # Clear existing items
        for i in reversed(range(self.layout.count())): 
            widget = self.layout.itemAt(i).widget()
            if widget and widget != self.title_label:
                widget.setParent(None)
        
        # Check Master Switch (Camera Input)
        cam_input_on = self.menu_items[0]["value"]
        
        # Re-create items
        for i, item in enumerate(self.menu_items):
            label = QLabel()
            font = QFont("Arial", 24) # Increased Font Size
            
            # Determine if enabled
            is_enabled = self.is_item_enabled(i)
            
            # Status Text
            status_text = ""
            if item["type"] == "toggle":
                if item["key"] == "handedness":
                    status_text = "[RIGHT]" if item["value"] else "[LEFT]"
                else:
                    status_text = "[ON]" if item["value"] else "[OFF]"
            elif item["type"] == "slider":
                val = item["value"]
                # Visual Bar: [|||||.....]
                blocks = int(val / 10)
                bar = "|" * blocks + "." * (10 - blocks)
                status_text = f"[{bar}] {val}%"
            elif item["type"] == "input":
                status_text = f"[{item['value']}]"
            elif item["type"] == "separator":
                display_text = f"--- {item['name']} ---"
            
            if item["type"] != "separator":
                display_text = f"{item['name']} {status_text}"
            else:
                 display_text = f"--- {item['name']} ---"
            
            # Style components
            bg_color = "transparent"
            text_color = "#AAAAAA"
            
            if not is_enabled:
                text_color = "#555555"
            elif i == self.current_index:
                text_color = "#FFFFFF"
                bg_color = "rgba(0, 255, 0, 0.3)"
                font.setBold(True)
                display_text = f"> {display_text} <"
            
            label.setStyleSheet(f"color: {text_color}; background-color: {bg_color}; padding: 15px; border-radius: 10px;")
            
            label.setFont(font)
            label.setAlignment(Qt.AlignCenter)
            label.setText(display_text)
            self.layout.addWidget(label)

    def is_item_enabled(self, i):
        cam_input_on = self.menu_items[0]["value"]
        item = self.menu_items[i]
        
        # Always enabled (or at least when visible)
        # Always enabled (or at least when visible)
        if item["key"] in ["cam_input", "sound", "voice_cmd", "exit", "handedness", "mic_volume", "trigger_word"]:
            return True
            
        # Dependent items are disabled if Cam Input is OFF
        if not cam_input_on:
            return False
            
        return True

    def navigate(self, direction):
        if not self.isVisible(): return
        
        start_index = self.current_index
        next_index = start_index
        
        # Try to find next enabled item (max tries = length)
        for i in range(1, len(self.menu_items) + 1):
            if direction == "up":
                check_index = (start_index - i) % len(self.menu_items)
            elif direction == "down":
                check_index = (start_index + i) % len(self.menu_items)
            else:
                break
                
            if self.is_item_enabled(check_index):
                self.current_index = check_index
                break

        if direction == "left":
             self.adjust_slider(-10)
        elif direction == "right":
             self.adjust_slider(10)
             
        self.update_display()
        
    def adjust_slider(self, delta):
        item = self.menu_items[self.current_index]
        if item["type"] == "slider":
            new_val = max(0, min(100, item["value"] + delta))
            item["value"] = new_val
            self.update_display()
            self.value_changed.emit(item["key"], new_val)
            self.save_settings()

    def select(self):
        if not self.isVisible(): return None
        
        item = self.menu_items[self.current_index]
        
        # Consistent check
        if not self.is_item_enabled(self.current_index):
            return None # Disabled
            
        if item["type"] == "toggle":
            item["value"] = not item["value"]
            self.update_display()
            self.save_settings()
            return {"key": item["key"], "value": item["value"]}
        elif item["type"] == "action":
            if item["key"] == "exit":
                self.hide_menu()
            return {"key": item["key"], "value": True}
        elif item["type"] == "input":
            # For now, maybe cycle through presets? Or just let user type via keyboard?
            # Since we have no keyboard input in overlay, we rely on voice or CLI to change it?
            # Or maybe cycle a few options?
            # "bash", "computer", "jarvis"
            # Let's simple toggle presets
            presets = ["bash", "computer", "jarvis", "system"]
            try:
                curr_idx = presets.index(item["value"])
                next_idx = (curr_idx + 1) % len(presets)
                item["value"] = presets[next_idx]
            except:
                item["value"] = presets[0]
            self.update_display()
            self.save_settings()
            return {"key": item["key"], "value": item["value"]}
        elif item["type"] == "slider":
             pass
             
        return None
    
    def get_current_item(self):
        return self.menu_items[self.current_index]

    def toggle_menu(self):
        if self.isVisible():
            self.hide()
            self.is_visible = False
        else:
            self.show()
            self.is_visible = True
            self.activateWindow()
            self.raise_()

    def hide_menu(self):
        self.hide()
        self.is_visible = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = MenuOverlay()
    overlay.show()
    sys.exit(app.exec_())
