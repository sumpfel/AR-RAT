import os
import time
import board
import digitalio

# Ensure Blinka knows we are using FT232H
os.environ["BLINKA_FT232H"] = "1"

print("Starting Button Test...")
print("Pin: D4")

# Setup pin
pin = digitalio.DigitalInOut(board.D4)
pin.direction = digitalio.Direction.INPUT
# Note: Pull.UP is not supported on FT232H, so we expect a physical pull-up!

print("Looping... Press Ctrl+C to stop.")
try:
    while True:
        # Print value: True == HIGH (unpressed), False == LOW (pressed)
        value = pin.value
        status = "PRESSED (LOW)" if not value else "unpressed (HIGH)"
        print(f"Value: {value} -> {status}", end="\r")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nTest stopped.")
