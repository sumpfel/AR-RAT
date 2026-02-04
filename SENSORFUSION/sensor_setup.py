import os

# Set environment variable to tell Blinka to use FT232H
# This acts as a signal to adafruit_blinka to look for the FT232 device
os.environ["BLINKA_FT232H"] = "1"

import board
import busio
import time
from adafruit_lsm6ds import LSM6DSOX
from adafruit_lis3mdl import LIS3MDL

def init_sensors():
    """
    Initialize the I2C bus via FT232 and the LSM6DSOX and LIS3MDL sensors.
    Returns a tuple (lsm, lis)
    """
    try:
        # Initialize I2C bus
        # board.SCL and board.SDA use the FT232H's default I2C pins
        i2c = board.I2C()

        # Initialize LSM6DSOX (Accelerometer + Gyroscope)
        # Try address 0x6A first, then 0x6B
        lsm = None
        for addr in [0x6A, 0x6B]:
            try:
                lsm = LSM6DSOX(i2c, address=addr)
                lsm_addr = addr
                print(f"Found LSM6DSOX at 0x{addr:x}")
                break
            except (ValueError, RuntimeError):
                continue
        
        if lsm is None:
            raise RuntimeError("Could not find LSM6DSOX at address 0x6A or 0x6B")

        # Initialize LIS3MDL (Magnetometer)
        # Try address 0x1C first, then 0x1E
        lis = None
        for addr in [0x1C, 0x1E]:
            try:
                lis = LIS3MDL(i2c, address=addr)
                lis_addr = addr
                print(f"Found LIS3MDL at 0x{addr:x}")
                break
            except (ValueError, RuntimeError):
                continue
                
        if lis is None:
            raise RuntimeError("Could not find LIS3MDL at address 0x1C or 0x1E")
        
        return lsm, lsm_addr, lis, lis_addr

    except RuntimeError as e:
        print(f"Error initializing sensors: {e}")
        print("Check your FT232 connections (SDA, SCK, GND, VCC).")
        print("Ensure 'BLINKA_FT232H' is set and the device is plugged in.")
        raise
    except ValueError as e:
        print(f"Value Error: {e}")
        print("Maybe the I2C address is incorrect or device not found?")
        raise
