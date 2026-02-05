import time
import json
import os
import sys
# Add current directory to path to allow importing sensor_setup
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import sensor_setup

CONFIG_FILE = "mag_config.json"

def calibrate(lis=None, lis_addr=None):
    print("Magnetometer Calibration")
    print("------------------------")
    
    if lis is None or lis_addr is None:
        print("Initializing sensors...")
        try:
            _, _, lis, lis_addr = sensor_setup.init_sensors()
        except Exception as e:
            print(f"Failed to initialize sensors: {e}")
            return

    print("Rotate the sensor in 8-figure motion and all directions.")
    print("Press Ctrl+C to stop calibration and save data.")
    print("Starting in 3 seconds...")
    time.sleep(3)

    min_x = float('inf')
    max_x = float('-inf')
    min_y = float('inf')
    max_y = float('-inf')
    min_z = float('inf')
    max_z = float('-inf')

    try:
        while True:
            mag_x, mag_y, mag_z = lis.magnetic
            
            min_x = min(min_x, mag_x)
            max_x = max(max_x, mag_x)
            min_y = min(min_y, mag_y)
            max_y = max(max_y, mag_y)
            min_z = min(min_z, mag_z)
            max_z = max(max_z, mag_z)

            print(f"X: {mag_x:.2f} [{min_x:.2f}, {max_x:.2f}] | "
                  f"Y: {mag_y:.2f} [{min_y:.2f}, {max_y:.2f}] | "
                  f"Z: {mag_z:.2f} [{min_z:.2f}, {max_z:.2f}]", end="\r")
            
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nCalibration finished.")
        
    # hard iron offsets
    offset_x = (max_x + min_x) / 2
    offset_y = (max_y + min_y) / 2
    offset_z = (max_z + min_z) / 2

    # soft iron scale
    avg_delta_x = (max_x - min_x) / 2
    avg_delta_y = (max_y - min_y) / 2
    avg_delta_z = (max_z - min_z) / 2

    avg_delta = (avg_delta_x + avg_delta_y + avg_delta_z) / 3

    scale_x = avg_delta / avg_delta_x if avg_delta_x != 0 else 1.0
    scale_y = avg_delta / avg_delta_y if avg_delta_y != 0 else 1.0
    scale_z = avg_delta / avg_delta_z if avg_delta_z != 0 else 1.0

    config = {
        "offset_x": offset_x,
        "offset_y": offset_y,
        "offset_z": offset_z,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "scale_z": scale_z
    }

    config_file = f"mag_config_0x{lis_addr:x}.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)
    
    print(f"\nCalibration data saved to {config_file}")
    print(json.dumps(config, indent=4))

if __name__ == "__main__":
    calibrate()
