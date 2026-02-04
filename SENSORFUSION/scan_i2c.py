import os

# Set environment variable to tell Blinka to use FT232H
os.environ["BLINKA_FT232H"] = "1"

import board
import busio
import time

def scan_i2c():
    try:
        # Initialize I2C bus
        i2c = board.I2C()
        
        while not i2c.try_lock():
            pass
        
        try:
            print("Scanning I2C bus...")
            devices = i2c.scan()
            
            if devices:
                print("I2C devices found:", [hex(device_address) for device_address in devices])
            else:
                print("No I2C devices found. Check your wiring (SDA, SCL, GND, VCC).")
                
        finally:
            i2c.unlock()
            
    except Exception as e:
        print(f"Error initializing I2C or scanning: {e}")
        print("Make sure the FT232H is connected.")

if __name__ == "__main__":
    scan_i2c()
