import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# Hardware Configuration
# Options: "AUTO", "FT232H", "RPI", "MOCK"
HARDWARE_MODE = "AUTO" 

# Hardware
FT232H_ENABLED = True # Deprecated, use HARDWARE_MODE logic in hardware.py
I2C_ENABLED = True

# Input
KEYBOARD_ENABLED = True
VOICE_ENABLED = True

# Display
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FULLSCREEN = True
UI_SCALE = 1.0  # Revert to standard
FONT_SCALE_RATIO = 0.05 # Increased for readability (User Feedback)
FACE_TRACKING = True
TARGET_DISPLAY = "HDMI" # Substring to match display name (e.g. "HDMI", "DP")

# --- PIN DEFINITIONS ---

# FT232H Pins
FT_LAUNCHER = "C0" # User requested C0 for App Launcher
FT_BACK = "C0"     # Aliased to C0 for now (Back/Home behavior)
FT_SELECT = "C1"
FT_MENU = "C2"
FT_DOWN = "C3"
FT_UP = "D4"
FT_LEFT = "C4"
FT_RIGHT = "C6"

# Raspberry Pi Pins (BCM Numbering)
# Adjust these to your preferred wiring
RPI_BACK = 17   # GPIO 17
RPI_SELECT = 27 # GPIO 27
RPI_MENU = 22   # GPIO 22
RPI_DOWN = 23   # GPIO 23
RPI_UP = 24     # GPIO 24
RPI_LEFT = 5    # GPIO 5
RPI_RIGHT = 6   # GPIO 6

# Active Configuration (Default to FT232H names, overwritten by HardwareManager if RPi detected)
PIN_C0 = FT_BACK 
PIN_C1 = FT_SELECT 
PIN_C2 = FT_MENU 
PIN_C3 = FT_DOWN 
PIN_D4 = FT_UP 
PIN_C4 = FT_LEFT 
PIN_C6 = FT_RIGHT
