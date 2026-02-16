import os

# Ensure Blinka knows we are using FT232H
os.environ["BLINKA_FT232H"] = "1"

import time
import board
import digitalio

print("Starting Button Test...")
print("Valid Pins: C0-C6, D4-D7 (C7-C9 are unavailable/unreliable)")
print("Press Ctrl+C to stop.")

# Define the pins we want to test
# Testing ALL valid pins so you can choose which ones to wire up.
pin_names = ["C0", "C1", "C2", "C3", "C4", "C5", "C6", "D4", "D5", "D6", "D7"]
buttons = []

# Initialize pins
for name in pin_names:
    try:
        # Get the pin object from board module dynamically
        pin_obj = getattr(board, name)
        
        # Create DigitalInOut object
        dio = digitalio.DigitalInOut(pin_obj)
        dio.direction = digitalio.Direction.INPUT
        
        # Store tuple of (name, digitalio_object)
        buttons.append((name, dio))
        print(f"Initialized {name}")
    except AttributeError:
        print(f"Warning: Pin {name} not found in board module.")
    except Exception as e:
        print(f"Error initializing {name}: {e}")

print("\nWaiting for input...")
print("Buttons soldered with pull-downs: EXPECT 0 (LOW) when IDLE, 1 (HIGH) when PRESSED.\n")

try:
    while True:
        # Build a status string
        status_parts = []
        for name, btn in buttons:
            val = btn.value
            # If pull-down: 0 is idle, 1 is pressed.
            state = "PRESSED" if val else "_"
            status_parts.append(f"{name}:{int(val)}")
        
        # Print all states on one line with carriage return to overwrite
        print(" | ".join(status_parts), end="\r")
        
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nTest stopped.")
