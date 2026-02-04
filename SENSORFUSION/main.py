import time
import json
import os
import sys
import math
import argparse
import numpy as np
from ahrs.filters import Madgwick

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import sensor_setup
import calibration

CONFIG_FILE = "mag_config.json"

def load_config(lis_addr, lis=None):
    config_file = f"mag_config_0x{lis_addr:x}.json"
    if not os.path.exists(config_file):
        print(f"Calibration data for 0x{lis_addr:x} not found. Launching calibration...")
        calibration.calibrate(lis=lis, lis_addr=lis_addr)
    
    if not os.path.exists(config_file):
        print("Calibration failed or was cancelled. Using default values.")
        return {"offset_x": 0, "offset_y": 0, "offset_z": 0, "scale_x": 1, "scale_y": 1, "scale_z": 1}

    with open(config_file, "r") as f:
        return json.load(f)

def calibrate_gyro(lsm, samples=200):
    print("Calibrating Gyroscope... KEEP SENSOR STILL!")
    offset_x, offset_y, offset_z = 0.0, 0.0, 0.0
    for _ in range(samples):
        gx, gy, gz = lsm.gyro
        offset_x += gx
        offset_y += gy
        offset_z += gz
        time.sleep(0.01)
    
    offset_x /= samples
    offset_y /= samples
    offset_z /= samples
    
    print(f"Gyro Calibration Complete. Offsets: X={offset_x:.4f}, Y={offset_y:.4f}, Z={offset_z:.4f}")
    return offset_x, offset_y, offset_z

def main():
    parser = argparse.ArgumentParser(description='Sensor Fusion with visualization')
    parser.add_argument('--debug', action='store_true', help='Enable 3D visualization')
    parser.add_argument('--forward-axis', type=str, default='x', help='Axis pointing forward (x, -x, y, -y, z, -z)')
    parser.add_argument('--up-axis', type=str, default='z', help='Axis pointing up (x, -x, y, -y, z, -z)')
    parser.add_argument('--use-gyro', action='store_true', help='Enable Gyroscope fusion (Madgwick)')
    parser.add_argument('--use-magnetometer', action='store_true', help='Enable Magnetometer (Compass/Yaw)')
    parser.add_argument('--relative-yaw', action='store_true', help='Zero out the initial heading on startup')
    args = parser.parse_args()

    vis = None
    if args.debug:
        try:
            import visualizer
            vis = visualizer.Visualizer()
        except ImportError:
            vis = None
            print("Could not import visualizer (pygame/opengl missing?). Running without it.")

    print("Sensor Fusion: LSM6DSOX + LIS3MDL")
    print("---------------------------------")
    
    # Axis vector mapping helper
    def get_axis_vector(axis_name):
        axis_name = axis_name.lower().strip()
        sign = -1 if axis_name.startswith('-') else 1
        axis = axis_name.strip('-')
        if axis == 'x': return np.array([sign, 0, 0])
        if axis == 'y': return np.array([0, sign, 0])
        if axis == 'z': return np.array([0, 0, sign])
        raise ValueError(f"Invalid axis: {axis_name}")

    try:
        fwd_vec = get_axis_vector(args.forward_axis)
        up_vec = get_axis_vector(args.up_axis)
        # Calculate Right vector (Right = Forward x Up)
        right_vec = np.cross(fwd_vec, up_vec)
        
        # Check orthogonality
        if np.linalg.norm(right_vec) < 0.1:
             print("Error: Forward and Up axes cannot be parallel.")
             return

        print(f"Mapping: Forward={args.forward_axis} {fwd_vec}, Up={args.up_axis} {up_vec}, Right={right_vec}")
        
    except ValueError as e:
        print(e)
        return
    
    # Initialize Sensors
    try:
        lsm, lsm_addr, lis, lis_addr = sensor_setup.init_sensors()
    except Exception as e:
        print(f"Failed to start: {e}")
        return

    # Load calibration data
    config = load_config(lis_addr, lis=lis)
    off_x, off_y, off_z = config["offset_x"], config["offset_y"], config["offset_z"]
    sc_x, sc_y, sc_z = config["scale_x"], config["scale_y"], config["scale_z"]

    # Calibrate Gyro only if using it
    gyro_off_x, gyro_off_y, gyro_off_z = 0, 0, 0
    if args.use_gyro:
        gyro_off_x, gyro_off_y, gyro_off_z = calibrate_gyro(lsm)

    # Initialize Madgwick Filter
    # Beta tunable: lower = smoother but slower convergence, higher = responsive but jittery
    madgwick = Madgwick(frequency=100.0, beta=0.05) 
    
    # Initial quaternion
    Q = np.array([1.0, 0.0, 0.0, 0.0])

    # Smoothing variables (Exponential Moving Average)
    alpha = 0.2 # Smoothing factor. 1.0 = no smoothing, 0.1 = heavy smoothing
    s_roll, s_pitch, s_yaw = 0.0, 0.0, 0.0
    
    yaw_offset = None

    print("Starting sensor fusion loop...")
    print("Press Ctrl+C to exit.")

    try:
        while True:
            # Read Sensors
            gyro_x, gyro_y, gyro_z = lsm.gyro
            acc_x, acc_y, acc_z = lsm.acceleration
            mag_x, mag_y, mag_z = lis.magnetic

            # Apply Hard Iron / Soft Iron Calibration to Mag
            cal_mag_x = (mag_x - off_x) * sc_x
            cal_mag_y = (mag_y - off_y) * sc_y
            cal_mag_z = (mag_z - off_z) * sc_z

            # Create vectors (no specific frame yet)
            acc_v = np.array([acc_x, acc_y, acc_z])
            mag_v = np.array([cal_mag_x, cal_mag_y, cal_mag_z])
            gyro_v = np.array([gyro_x - gyro_off_x, gyro_y - gyro_off_y, gyro_z - gyro_off_z])

            if not args.use_gyro:
                # Tilt-Compensated logic (Acc Only or Acc+Mag) using Virtual Frames
                acc_fwd = np.dot(acc_v, fwd_vec)
                acc_right = np.dot(acc_v, right_vec)
                acc_up = np.dot(acc_v, up_vec)
                
                pitch = math.atan2(acc_fwd, acc_up)
                roll = math.atan2(acc_right, acc_up)
                
                if args.use_magnetometer:
                    sin_r, cos_r = math.sin(roll), math.cos(roll)
                    sin_p, cos_p = math.sin(pitch), math.cos(pitch)
                    Xh = cal_mag_x * cos_p + cal_mag_z * sin_p
                    Yh = cal_mag_x * sin_r * sin_p + cal_mag_y * cos_r - cal_mag_z * sin_r * cos_p
                    yaw = math.atan2(Yh, Xh)
                else:
                    yaw = 0.0
            else:
                # Madgwick Sensor Fusion Logic (Using Mapped Inputs)
                gyr_mapped = np.array([np.dot(gyro_v, fwd_vec), np.dot(gyro_v, right_vec), np.dot(gyro_v, up_vec)])
                acc_mapped = np.array([np.dot(acc_v, fwd_vec), np.dot(acc_v, right_vec), np.dot(acc_v, up_vec)])
                mag_mapped = np.array([np.dot(mag_v, fwd_vec), np.dot(mag_v, right_vec), np.dot(mag_v, up_vec)])

                if args.use_magnetometer:
                    Q = madgwick.updateMARG(Q, gyr=gyr_mapped, acc=acc_mapped, mag=mag_mapped)
                else:
                    Q = madgwick.updateIMU(Q, gyr=gyr_mapped, acc=acc_mapped)

                w, x, y, z = Q
                sinr_cosp, cosr_cosp = 2 * (w * x + y * z), 1 - 2 * (x * x + y * y)
                roll = math.atan2(sinr_cosp, cosr_cosp)
                sinp = 2 * (w * y - z * x)
                pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)
                siny_cosp, cosy_cosp = 2 * (w * z + x * y), 1 - 2 * (y * y + z * z)
                yaw = math.atan2(siny_cosp, cosy_cosp)

            # Apply Relative Yaw Offset
            if args.relative_yaw:
                if yaw_offset is None:
                    yaw_offset = yaw
                yaw -= yaw_offset
                # Normalize to [-pi, pi]
                while yaw > math.pi: yaw -= 2 * math.pi
                while yaw < -math.pi: yaw += 2 * math.pi

            # Convert to degrees
            roll_deg = math.degrees(roll)
            pitch_deg = math.degrees(pitch)
            yaw_deg = math.degrees(yaw)

            # Apply Smoothing (EMA)
            s_roll = alpha * roll_deg + (1 - alpha) * s_roll
            s_pitch = alpha * pitch_deg + (1 - alpha) * s_pitch
            s_yaw = alpha * yaw_deg + (1 - alpha) * s_yaw

            print(f"Roll: {s_roll:>6.1f} | Pitch: {s_pitch:>6.1f} | Yaw: {s_yaw:>6.1f}", end="\r")
            
            if vis:
                if not vis.update(s_roll, s_pitch, s_yaw):
                    break
            
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

