import sys
import platform

# Check OS
IS_LINUX = platform.system() == "Linux"

# Try importing evdev
try:
    import evdev
    from evdev import UInput, AbsInfo, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

# Always import pynput as fallback / for Buttons
from pynput.mouse import Button, Controller as PynputController

class HybridMouse:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.uinput = None
        self.pynput = PynputController()
        self.use_evdev = False

        if IS_LINUX and EVDEV_AVAILABLE:
            try:
                # Create UInput Device with Absolute Mouse capabilities + Wheel
                cap = {
                    ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE],
                    ecodes.EV_ABS: [
                        (ecodes.ABS_X, AbsInfo(value=0, min=0, max=width, fuzz=0, flat=0, resolution=0)),
                        (ecodes.ABS_Y, AbsInfo(value=0, min=0, max=height, fuzz=0, flat=0, resolution=0))
                    ],
                    ecodes.EV_REL: [ecodes.REL_WHEEL]
                }
                self.uinput = UInput(cap, name='AR-RAT-Virtual-Mouse', version=0x1)
                self.use_evdev = True
                print("HybridMouse: Using evdev (UInput) for Absolute Positioning.")
            except PermissionError:
                print("HybridMouse Warning: No permissions for /dev/uinput. Falling back to pynput.")
            except Exception as e:
                print(f"HybridMouse Warning: Failed to create UInput device ({e}). Falling back to pynput.")

        if not self.use_evdev:
            print("HybridMouse: Using pynput.")

    def move(self, x, y):
        """
        Move mouse to absolute coordinates (x, y).
        """
        # Clamp coordinates
        x = int(max(0, min(x, self.width - 1)))
        y = int(max(0, min(y, self.height - 1)))

        if self.use_evdev:
            self.uinput.write(ecodes.EV_ABS, ecodes.ABS_X, x)
            self.uinput.write(ecodes.EV_ABS, ecodes.ABS_Y, y)
            self.uinput.syn()
        else:
            # pynput set_position
            self.pynput.position = (x, y)

    def click(self, button, down=True):
        """
        Click a button.
        button: pynput.mouse.Button.left/right (or string 'left'/'right')
        down: True for press, False for release.
        """
        if self.use_evdev:
            key = None
            if button == Button.left: key = ecodes.BTN_LEFT
            elif button == Button.right: key = ecodes.BTN_RIGHT
            elif button == Button.middle: key = ecodes.BTN_MIDDLE
            
            if key:
                self.uinput.write(ecodes.EV_KEY, key, 1 if down else 0)
                self.uinput.syn()
        else:
            if down:
                self.pynput.press(button)
            else:
                self.pynput.release(button)

    def scroll(self, dy):
        """
        Scroll. dy is vertical steps.
        """
        if self.use_evdev:
            # evdev relative wheel
            # REL_WHEEL value is number of detents
            try:
                # REL_WHEEL: Positive is UP, Negative is DOWN
                self.uinput.write(e.EV_REL, e.REL_WHEEL, int(dy))
                self.uinput.syn()
            except Exception as ex: # Changed e to ex
                 print(f"UInput Scroll Error: {ex}")
        else:
            self.pynput.scroll(0, dy)

    def type_key(self, key_name):
        """Simulate key press and release."""
        # Normalize key name
        key_name = key_name.upper()
        
        # Linux (evdev)
        if self.use_evdev: # Use self.use_evdev for consistency
            try:
                # Map common keys
                # evdev.ecodes has specific names like KEY_A, KEY_ENTER
                ukey = None
                if hasattr(e, f"KEY_{key_name}"):
                    ukey = getattr(e, f"KEY_{key_name}")
                elif key_name == "ENTER": ukey = e.KEY_ENTER
                elif key_name == "SPACE": ukey = e.KEY_SPACE
                elif key_name == "BACKSPACE": ukey = e.KEY_BACKSPACE
                elif key_name == "TAB": ukey = e.KEY_TAB
                elif len(key_name) == 1:
                     # Try to find character key
                     if hasattr(e, f"KEY_{key_name}"):
                         ukey = getattr(e, f"KEY_{key_name}")
                
                if ukey:
                    self.uinput.write(e.EV_KEY, ukey, 1) # Press
                    self.uinput.syn()
                    time.sleep(0.01)
                    self.uinput.write(e.EV_KEY, ukey, 0) # Release
                    self.uinput.syn()
                else:
                    print(f"HybridMouse: Unknown key '{key_name}'")
            except Exception as ex:
                print(f"UInput Key Error: {ex}")
                
        # Windows/Fallback (pynput)
        # Note: HybridMouse initializes pynput.mouse.Controller, not Keyboard.
        # We need pynput.keyboard if we want fallback.
        else:
             # Lazy import to avoid dependency if not used
             try:
                 from pynput.keyboard import Controller, Key
                 if not hasattr(self, 'keyboard') or self.keyboard is None: # Check if keyboard is None
                     self.keyboard = Controller()
                 
                 p_key = None
                 if len(key_name) == 1:
                     p_key = key_name.lower()
                 elif key_name == "ENTER": p_key = Key.enter
                 elif key_name == "SPACE": p_key = Key.space
                 elif key_name == "BACKSPACE": p_key = Key.backspace
                 elif key_name == "TAB": p_key = Key.tab
                 
                 if p_key:
                     self.keyboard.press(p_key)
                     self.keyboard.release(p_key)
             except Exception as ex:
                 print(f"Pynput Key Error: {ex}")

    def close(self):
        if self.uinput:
            self.uinput.close()
