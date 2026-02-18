import threading
import time
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from pynput import keyboard
from .hardware import HardwareManager
import config 

class InputManager(QObject):
    # Unified Signals
    UP = pyqtSignal()
    DOWN = pyqtSignal()
    LEFT = pyqtSignal()
    RIGHT = pyqtSignal()
    
    SELECT = pyqtSignal()   # Enter / C1
    BACK = pyqtSignal()     # Esc / C0
    MENU = pyqtSignal()     # Tab / C2
    LAUNCHER = pyqtSignal() # L
    
    def __init__(self):
        super().__init__()
        self.hardware = HardwareManager()
        self.running = False
        
        # --- BUTTONS ---
        self.buttons = {}
        # Map Board Pins to Signals
        # Note: config pins are updated by HardwareManager init
        # Map Board Pins to Signals
        # Note: config pins are updated by HardwareManager init
        self.btn_map = {
            config.PIN_D4: self.UP,
            config.PIN_C3: self.DOWN,
            config.PIN_C4: self.LEFT,
            config.PIN_C6: self.RIGHT,
            config.PIN_C1: self.SELECT,
            config.PIN_C0: self.LAUNCHER, # Swapped BACK to LAUNCHER
            config.PIN_C2: self.MENU
        }
        
        # If BACK and LAUNCHER share C0, this one mapping covers both if we handle logic in Main.
        # But wait, config.PIN_C0 is "C0". FT_BACK is "C0". FT_LAUNCHER is "C0".
        # So emitting self.LAUNCHER is fine. Main will decide behavior.
        # What about self.BACK logic? 
        # If C0 is pressed, it emits LAUNCHER. 
        # If we need BACK behavior, we can bind LAUNCHER signal to handle_back in some contexts.
        # OR we map it to a new shared signal?
        # Let's map it to LAUNCHER signal as requested: "c0 is for opening/closing app launcher".
        # "Back" concept might be "Toggle Launcher" or "Toggle Menu" which acts as back.
        # I will remove self.BACK from the map if it's redundant.
        pass
        
        # Init Pins
        for pin_name, signal in self.btn_map.items():
            if pin_name: # Handle None/Empty
                dio = self.hardware.setup_pin(pin_name)
                if dio:
                    self.buttons[pin_name] = {"obj": dio, "last": False, "signal": signal}
                
        # --- KEYBOARD (EVDEV) ---
        self.keyboard_thread = threading.Thread(target=self.evdev_loop, daemon=True)
        if config.KEYBOARD_ENABLED:
            self.keyboard_thread.start()
            
        # Start Button Polling Loop
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_buttons)
        self.timer.start(50) # 20Hz polling
        
    def poll_buttons(self):
        for name, data in self.buttons.items():
            btn = data["obj"]
            try:
                # MockPins might return different types, ensure bool
                val = bool(btn.value)
                # Active High Check
                is_pressed = val 
                
                # Signal on Rising Edge
                if is_pressed and not data["last"]:
                    print(f"[Input] Button {name} Pressed")
                    data["signal"].emit()
                    
                data["last"] = is_pressed
            except Exception as e:
                print(f"[Input] Error reading {name}: {e}")

    def evdev_loop(self):
        try:
            import evdev
            from evdev import InputDevice, categorize, ecodes
            
            # Find keyboard device
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            keyboard_dev = None
            for dev in devices:
                # Broader check for keyboards
                if "keyboard" in dev.name.lower() or "usb" in dev.name.lower():
                    # Simple heuristic: supports KEY_ENTER?
                    caps = dev.capabilities()
                    if ecodes.EV_KEY in caps:
                        if ecodes.KEY_ENTER in caps[ecodes.EV_KEY] or ecodes.KEY_A in caps[ecodes.EV_KEY]:
                             keyboard_dev = dev
                             break
            
            if not keyboard_dev:
                print("[Input] No evdev keyboard found!")
                return
                
            print(f"[Input] Using Keyboard: {keyboard_dev.name}")
            
            for event in keyboard_dev.read_loop():
                if event.type == ecodes.EV_KEY and event.value == 1: # Key Down
                    # Map Keys
                    if event.code == ecodes.KEY_UP:
                        # print("[Input] Key: UP")
                        self.UP.emit()
                    elif event.code == ecodes.KEY_DOWN:
                        # print("[Input] Key: DOWN")
                        self.DOWN.emit()
                    elif event.code == ecodes.KEY_LEFT:
                        # print("[Input] Key: LEFT")
                        self.LEFT.emit()
                    elif event.code == ecodes.KEY_RIGHT:
                        # print("[Input] Key: RIGHT")
                        self.RIGHT.emit()
                    elif event.code == ecodes.KEY_ENTER:
                        print("[Input] Key: ENTER")
                        self.SELECT.emit()
                    elif event.code == ecodes.KEY_ESC:
                        print("[Input] Key: ESC")
                        self.BACK.emit()
                    elif event.code == ecodes.KEY_TAB or event.code == ecodes.KEY_M:
                        print("[Input] Key: MENU")
                        self.MENU.emit()
                    elif event.code == ecodes.KEY_L:
                        print("[Input] Key: LAUNCHER")
                        self.LAUNCHER.emit()
                        
        except ImportError:
             print("[Input] evdev module not installed. Keyboard input disabled.")
        except Exception as e:
            print(f"[Input] Evdev Error: {e}")
