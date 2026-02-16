import sys
print(f"Python: {sys.executable}")
import evdev
from evdev import UInput, AbsInfo, ecodes

try:
    # Define capabilities for an Absolute Mouse / Graphics Tablet
    cap = {
        evdev.ecodes.EV_KEY: [evdev.ecodes.BTN_LEFT, evdev.ecodes.BTN_RIGHT],
        evdev.ecodes.EV_ABS: [
            (evdev.ecodes.ABS_X, AbsInfo(value=0, min=0, max=1920, fuzz=0, flat=0, resolution=0)),
            (evdev.ecodes.ABS_Y, AbsInfo(value=0, min=0, max=1080, fuzz=0, flat=0, resolution=0))
        ]
    }
    
    ui = UInput(cap, name='AR-RAT-Virtual-Mouse', version=0x1)
    print("Success: Created UInput Device")
    ui.close()
    sys.exit(0)
except PermissionError:
    print("PermissionError: Cannot access /dev/uinput")
    sys.exit(2)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(3)
