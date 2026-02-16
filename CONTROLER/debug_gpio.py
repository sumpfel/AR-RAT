import os
os.environ["BLINKA_FT232H"] = "1"

import board
from adafruit_blinka.microcontroller.ftdi_mpsse.mpsse.pin import Pin

print("Init Pin class...")
# Force init of mpsse_gpio
try:
    p = Pin(8) # C0
    gpio = Pin.mpsse_gpio
    print(f"GPIO Width: {gpio.width}")
    print(f"GPIO Mask: {bin(gpio.all_pins)} ({gpio.all_pins})")
    
    # Check current direction/value of C7 (Pin 15)
    c7_mask = 1 << 15
    print(f"C7 (bit 15) in mask: {bool(gpio.all_pins & c7_mask)}")
    direction = gpio.direction
    print(f"Current Direction: {bin(direction)}")
    print(f"C7 Direction: {'OUT' if direction & c7_mask else 'IN'}")
    
    # Check C8/C9 availability (bits 16, 17 probably? or 8,9 if width is different?)
    # Mapping: D0-D7 = 0-7. C0-C7 = 8-15.
    c8_mask = 1 << 16
    c9_mask = 1 << 17
    print(f"C8 (bit 16) in mask: {bool(gpio.all_pins & c8_mask)}")
    print(f"C9 (bit 17) in mask: {bool(gpio.all_pins & c9_mask)}")
    
except Exception as e:
    print(f"Error: {e}")
