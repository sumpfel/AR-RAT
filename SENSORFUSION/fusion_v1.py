import time
import json
import os
import sys
import math
import numpy as np
from ahrs.filters import Madgwick

# Add current directory to path if needed (might not be if in same dir)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import sensor_setup
import calibration

class SensorFusionV1:
    def __init__(self, use_gyro=True, use_magnetometer=True, relative_yaw=False, forward_axis='x', up_axis='z', target_priority='center'):
        self.use_gyro = use_gyro
        self.use_magnetometer = use_magnetometer
        self.relative_yaw = relative_yaw
        self.target_priority = target_priority
        self.forward_axis = forward_axis
        self.up_axis = up_axis
        
        self.lsm = None
        self.lis = None
        self.madgwick = None
        self.Q = np.array([1.0, 0.0, 0.0, 0.0])
        
        # Smoothing
        self.alpha = 0.2
        self.s_roll, self.s_pitch, self.s_yaw = 0.0, 0.0, 0.0
        self.yaw_offset = None
        self.last_ts = time.time()
        self.init_system()

    def get_axis_vector(self, axis_name):
        axis_name = axis_name.lower().strip()
        sign = -1 if axis_name.startswith('-') else 1
        axis = axis_name.strip('-')
        if axis == 'x': return np.array([sign, 0, 0])
        if axis == 'y': return np.array([0, sign, 0])
        if axis == 'z': return np.array([0, 0, sign])
        raise ValueError(f"Invalid axis: {axis_name}")

    def load_config(self, lis_addr, lis=None):
        config_file = f"mag_config_0x{lis_addr:x}.json"
        if not os.path.exists(config_file):
            print(f"Calibration data for 0x{lis_addr:x} not found. Launching calibration...")
            calibration.calibrate(lis=lis, lis_addr=lis_addr)
        
        if not os.path.exists(config_file):
            print("Calibration failed or was cancelled. Using default values.")
            return {"offset_x": 0, "offset_y": 0, "offset_z": 0, "scale_x": 1, "scale_y": 1, "scale_z": 1}

        with open(config_file, "r") as f:
            return json.load(f)

    def calibrate_gyro(self, samples=200):
        print("Calibrating Gyroscope... KEEP SENSOR STILL!")
        ox, oy, oz = 0.0, 0.0, 0.0
        for _ in range(samples):
            gx, gy, gz = self.lsm.gyro
            ox += gx; oy += gy; oz += gz
            time.sleep(0.01)
        self.gyro_offset = (ox/samples, oy/samples, oz/samples)
        print(f"Gyro Calibration Complete. Offsets: {self.gyro_offset}")

    def init_system(self):
        print("Sensor Fusion V1: LSM6DSOX + LIS3MDL")
        
        try:
            self.fwd_vec = self.get_axis_vector(self.forward_axis)
            self.up_vec = self.get_axis_vector(self.up_axis)
            self.right_vec = np.cross(self.fwd_vec, self.up_vec)
            if np.linalg.norm(self.right_vec) < 0.1:
                raise ValueError("Forward and Up axes cannot be parallel.")
            print(f"Mapping: Forward={self.forward_axis}, Up={self.up_axis}")
        except ValueError as e:
            print(e); sys.exit(1)

        try:
            self.lsm, self.lsm_addr, self.lis, self.lis_addr = sensor_setup.init_sensors()
        except Exception as e:
            print(f"Failed to start: {e}"); sys.exit(1)

        # Mag Calibration
        config = self.load_config(self.lis_addr, lis=self.lis)
        self.mag_off = (config["offset_x"], config["offset_y"], config["offset_z"])
        self.mag_scale = (config["scale_x"], config["scale_y"], config["scale_z"])

        # Gyro Calibration
        self.gyro_offset = (0,0,0)
        if self.use_gyro:
            self.calibrate_gyro()

        self.madgwick = Madgwick(frequency=100.0, beta=0.05)

    def update(self):
        # Update Dt logic
        now = time.time()
        dt = now - self.last_ts
        self.last_ts = now
        if dt > 0:
            self.madgwick.Dt = dt

        # Read Sensors
        gx, gy, gz = self.lsm.gyro
        ax, ay, az = self.lsm.acceleration
        mx, my, mz = self.lis.magnetic

        # Apply Calibrations
        cal_mx = (mx - self.mag_off[0]) * self.mag_scale[0]
        cal_my = (my - self.mag_off[1]) * self.mag_scale[1]
        cal_mz = (mz - self.mag_off[2]) * self.mag_scale[2]

        acc_v = np.array([ax, ay, az])
        mag_v = np.array([cal_mx, cal_my, cal_mz])
        
        # Raw Gyro with offset removed
        gyro_v = np.array([gx - self.gyro_offset[0], gy - self.gyro_offset[1], gz - self.gyro_offset[2]])

        if not self.use_gyro:
            # Tilt-Compensated (Accel Only) or Accel+Mag (No Gyro Fusion)
            acc_fwd = np.dot(acc_v, self.fwd_vec)
            acc_right = np.dot(acc_v, self.right_vec)
            acc_up = np.dot(acc_v, self.up_vec)
            
            pitch = math.atan2(acc_fwd, acc_up)
            roll = math.atan2(acc_right, acc_up)
            
            if self.use_magnetometer:
                # Tilt Compensated Compass
                mx_l = np.dot(mag_v, self.fwd_vec)
                my_l = np.dot(mag_v, self.right_vec)
                mz_l = np.dot(mag_v, self.up_vec)
                
                sin_r, cos_r = math.sin(roll), math.cos(roll)
                sin_p, cos_p = math.sin(pitch), math.cos(pitch)
                
                # De-rotate to horizontal
                # 1. De-roll (around X axis)
                my_flat = my_l * cos_r - mz_l * sin_r
                mz_temp = my_l * sin_r + mz_l * cos_r
                
                # 2. De-pitch (around Y axis)
                mx_flat = mx_l * cos_p + mz_temp * sin_p
                
                yaw = math.atan2(-my_flat, mx_flat)
            else:
                yaw = 0.0
        else:
            # Madgwick
            gyr_mapped = np.array([np.dot(gyro_v, self.fwd_vec), np.dot(gyro_v, self.right_vec), np.dot(gyro_v, self.up_vec)])
            acc_mapped = np.array([np.dot(acc_v, self.fwd_vec), np.dot(acc_v, self.right_vec), np.dot(acc_v, self.up_vec)])
            mag_mapped = np.array([np.dot(mag_v, self.fwd_vec), np.dot(mag_v, self.right_vec), np.dot(mag_v, self.up_vec)])

            if self.use_magnetometer:
                self.Q = self.madgwick.updateMARG(self.Q, gyr=gyr_mapped, acc=acc_mapped, mag=mag_mapped)
            else:
                self.Q = self.madgwick.updateIMU(self.Q, gyr=gyr_mapped, acc=acc_mapped)

            w, x, y, z = self.Q
            sinr_cosp, cosr_cosp = 2 * (w * x + y * z), 1 - 2 * (x * x + y * y)
            roll = math.atan2(sinr_cosp, cosr_cosp)
            sinp = 2 * (w * y - z * x)
            pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)
            siny_cosp, cosy_cosp = 2 * (w * z + x * y), 1 - 2 * (y * y + z * z)
            yaw = math.atan2(siny_cosp, cosy_cosp)

        # Yaw Offset
        if self.relative_yaw:
            if self.yaw_offset is None: self.yaw_offset = yaw
            yaw -= self.yaw_offset
            while yaw > math.pi: yaw -= 2 * math.pi
            while yaw < -math.pi: yaw += 2 * math.pi

        # Degrees
        r_deg = math.degrees(roll)
        p_deg = math.degrees(pitch)
        y_deg = math.degrees(yaw)
        
        # Smooth Mag Vector (Low Pass)
        if not hasattr(self, 's_mag'): self.s_mag = mag_v
        mag_alpha = 0.02 # Strong smoothing (was 0.1)
        self.s_mag = self.s_mag * (1 - mag_alpha) + mag_v * mag_alpha
        
        if not self.use_gyro and self.use_magnetometer:
             # Use SMOOTHED mag for Tilt Compensation to reduce jitter
             mag_v_calc = self.s_mag
             
             mx_l = np.dot(mag_v_calc, self.fwd_vec)
             my_l = np.dot(mag_v_calc, self.right_vec)
             mz_l = np.dot(mag_v_calc, self.up_vec)
             
             sin_r, cos_r = math.sin(roll), math.cos(roll)
             sin_p, cos_p = math.sin(pitch), math.cos(pitch)
             
             # De-rotate
             my_flat = my_l * cos_r - mz_l * sin_r
             mz_temp = my_l * sin_r + mz_l * cos_r
             mx_flat = mx_l * cos_p + mz_temp * sin_p
             
             yaw = math.atan2(-my_flat, mx_flat)
        else:
             pass

        # Smooth Angles (Correct Wrap-Around)
        def smooth_angle(current, new_val, alpha):
            diff = new_val - current
            while diff > 180: diff -= 360
            while diff < -180: diff += 360
            return current + alpha * diff

        self.s_roll = smooth_angle(self.s_roll, r_deg, self.alpha)
        self.s_pitch = smooth_angle(self.s_pitch, p_deg, self.alpha)
        
        yaw_alpha = 0.2 
        self.s_yaw = smooth_angle(self.s_yaw, y_deg, yaw_alpha) 
        
        # Normalize s_yaw to +/- 180
        while self.s_yaw > 180: self.s_yaw -= 360
        while self.s_yaw < -180: self.s_yaw += 360
        
        # Normalize s_roll and s_pitch to prevent drift
        while self.s_roll > 180: self.s_roll -= 360
        while self.s_roll < -180: self.s_roll += 360
        
        while self.s_pitch > 180: self.s_pitch -= 360
        while self.s_pitch < -180: self.s_pitch += 360

        return self.s_roll, self.s_pitch, self.s_yaw, gyro_v
