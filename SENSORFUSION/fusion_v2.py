import time
import json
import os
import sys
import math
import numpy as np

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import sensor_setup
import calibration

class SensorFusionV2:
    def __init__(self, use_gyro=True, use_magnetometer=True, relative_yaw=False, forward_axis='x', up_axis='z', target_priority='center'):
        self.use_gyro = use_gyro
        self.use_magnetometer = use_magnetometer
        self.relative_yaw = relative_yaw
        self.forward_axis = forward_axis
        self.up_axis = up_axis
        
        self.lsm = None
        self.lis = None
        
        # State Variables
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        
        self.yaw_offset = 0.0
        self.first_run = True
        self.last_ts = time.time()
        
        # Filter Parameters
        self.dt = 0.01
        self.alpha_yaw = 0.98 
        
        # Calibration Data
        self.mag_off = [0,0,0]
        self.mag_scale = [1,1,1]
        self.gyro_offset = [0,0,0]
        
        # Continuous Mag Calibration State
        self.mag_min = [1000, 1000, 1000]
        self.mag_max = [-1000, -1000, -1000]
        self.mag_cal_samples = 0
        
        self.init_system()

    def get_axis_vector(self, axis_name):
        axis_name = axis_name.lower().strip()
        sign = -1 if axis_name.startswith('-') else 1
        axis = axis_name.strip('-')
        if axis == 'x': return np.array([sign, 0, 0])
        if axis == 'y': return np.array([0, sign, 0])
        if axis == 'z': return np.array([0, 0, sign])
        raise ValueError(f"Invalid axis: {axis_name}")

    def load_mag_config(self, lis_addr, lis=None):
        config_file = f"mag_config_0x{lis_addr:x}.json"
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                return json.load(f)
        return {"offset_x": 0, "offset_y": 0, "offset_z": 0, "scale_x": 1, "scale_y": 1, "scale_z": 1}
        
    def load_gyro_config(self):
        config_file = "gyro_config.json"
        if os.path.exists(config_file):
            print("Loading Gyro Calibration...")
            with open(config_file, "r") as f:
                 data = json.load(f)
                 return (data["x"], data["y"], data["z"])
        return None

    def calibrate_gyro(self, samples=500):
        # Check if saved config exists
        saved = self.load_gyro_config()
        if saved:
            self.gyro_offset = saved
            print(f"Loaded Gyro Offsets: {self.gyro_offset}")
            return

        print("Calibrating Gyroscope (LONG)... KEEP SENSOR STILL!")
        ox, oy, oz = 0.0, 0.0, 0.0
        for i in range(samples):
            gx, gy, gz = self.lsm.gyro
            ox += gx; oy += gy; oz += gz
            time.sleep(0.005)
            if i % 50 == 0: print(f"Calibrating Gyro: {int(i/samples*100)}%", end='\r')
            
        self.gyro_offset = (ox/samples, oy/samples, oz/samples)
        print(f"\nGyro Calibration Complete. Offsets: {self.gyro_offset}")
        
        # Save config
        with open("gyro_config.json", "w") as f:
            json.dump({"x": self.gyro_offset[0], "y": self.gyro_offset[1], "z": self.gyro_offset[2]}, f)
        print("Gyro Calibration Saved.")

    def detect_orientation(self):
        print("Detecting Sensor Orientation... Keep device level!")
        ax_sum, ay_sum, az_sum = 0, 0, 0
        samples = 100
        for _ in range(samples):
            ax, ay, az = self.lsm.acceleration
            ax_sum += ax; ay_sum += ay; az_sum += az
            time.sleep(0.01)
        
        avg_ax = ax_sum / samples
        avg_ay = ay_sum / samples
        avg_az = az_sum / samples
        
        avgs = {'x': avg_ax, 'y': avg_ay, 'z': avg_az}
        print(f"Gravity Vector: ({avg_ax:.2f}, {avg_ay:.2f}, {avg_az:.2f})", flush=True)
        
        # Find axis with max gravity
        max_axis = max(avgs, key=lambda k: abs(avgs[k]))
        max_val = avgs[max_axis]
        
        # Determine sign
        sign = '+' if max_val > 0 else '-'
        
        self.up_axis = f"{sign if sign == '-' else ''}{max_axis}"
        print(f"Detected Up Axis: {self.up_axis} (Gravity)", flush=True)
        
        # Heuristic for Forward axis
        # If Up is Z, Forward is usually Y or X.
        # We can't know Forward without user input or movement.
        # But we can adhere to the user's wish "Blue to me, Green down, Red right".
        # If Green is Down, Y is Down. Then Up is -Y.
        # We'll just verify UP for now to stop the "wobble".
        
        # Ensure Forward is orthogonal
        base_up = self.up_axis.strip('-')
        base_fwd = self.forward_axis.strip('-')
        
        if base_up == base_fwd:
            # Conflict. Pick a new forward.
            if base_up == 'x': self.forward_axis = 'y'
            elif base_up == 'y': self.forward_axis = 'z'
            else: self.forward_axis = 'x'
            print(f"Adjusted Forward Axis to: {self.forward_axis}", flush=True)

    def init_system(self):
        print("Sensor Fusion V2: Improved Yaw Logic", flush=True)
        
        try:
            self.lsm, self.lsm_addr, self.lis, self.lis_addr = sensor_setup.init_sensors()
        except Exception as e:
            print(f"Failed to start: {e}"); sys.exit(1)
            
        # Orientation Detection
        self.detect_orientation()

        # Mag Calibration
        config = self.load_mag_config(self.lis_addr, lis=self.lis)
        self.mag_off = [config["offset_x"], config["offset_y"], config["offset_z"]]
        self.mag_scale = [config["scale_x"], config["scale_y"], config["scale_z"]]
        
        # Gyro Calibration
        if self.use_gyro:
            self.calibrate_gyro()
            
        self.last_ts = time.time()

    def update_continuous_mag_cal(self, raw_mag):
        # Update Min/Max
        changed = False
        for i in range(3):
            if raw_mag[i] < self.mag_min[i]:
                self.mag_min[i] = raw_mag[i]
                changed = True
            if raw_mag[i] > self.mag_max[i]:
                self.mag_max[i] = raw_mag[i]
                changed = True
        
        if changed:
            self.mag_cal_samples += 1
            # Recalculate Offsets (Hard Iron)
            # Scale (Soft Iron) is harder to do blindly, stick to 1.0 or user default
            # Offset = (Min + Max) / 2
            for i in range(3):
                self.mag_off[i] = (self.mag_min[i] + self.mag_max[i]) / 2.0
            
            # Use average scale?
            avg_delta = (self.mag_max[0]-self.mag_min[0] + self.mag_max[1]-self.mag_min[1] + self.mag_max[2]-self.mag_min[2]) / 3.0
            if avg_delta > 0:
                 for i in range(3):
                     delta = self.mag_max[i] - self.mag_min[i]
                     if delta > 0:
                         self.mag_scale[i] = avg_delta / delta
                     else:
                         self.mag_scale[i] = 1.0

    def update(self):
        now = time.time()
        dt = now - self.last_ts
        self.last_ts = now
        
        # 1. Read Raw Data
        raw_gyro = self.lsm.gyro # rad/s
        raw_acc = self.lsm.acceleration # m/s^2
        raw_mag = self.lis.magnetic # uT
        
        # Dynamic Mag Calibration
        self.update_continuous_mag_cal(raw_mag)
        
        # 2. Apply Offsets
        if self.use_gyro:
            # Convert calculated offsets to radians if they were in degrees?
            # Wait, calibration handles raw units.
            # Convert RAW data to radians (assuming Scale Sensitivity error)
            scale = math.pi / 180.0
            
            gx = (raw_gyro[0] - self.gyro_offset[0]) * scale
            gy = (raw_gyro[1] - self.gyro_offset[1]) * scale
            gz = (raw_gyro[2] - self.gyro_offset[2]) * scale
        else:
            gx, gy, gz = 0.0, 0.0, 0.0
        
        ax, ay, az = raw_acc
        
        mx = (raw_mag[0] - self.mag_off[0]) * self.mag_scale[0]
        my = (raw_mag[1] - self.mag_off[1]) * self.mag_scale[1]
        mz = (raw_mag[2] - self.mag_off[2]) * self.mag_scale[2]
        
        # 3. Calculate Pitch and Roll
        fwd = self.get_axis_vector(self.forward_axis)
        up = self.get_axis_vector(self.up_axis)
        right = np.cross(fwd, up) 
        
        acc_vec = np.array([ax, ay, az])
        mag_vec = np.array([mx, my, mz])
        gyro_vec = np.array([gx, gy, gz])
        
        # Map to components
        a_fwd = np.dot(acc_vec, fwd)
        a_right = np.dot(acc_vec, right)
        a_up = np.dot(acc_vec, up)
        
        # Pitch/Roll from gravity
        # Pitch: angle of nose up/down
        pitch_acc = math.atan2(a_fwd, math.sqrt(a_right**2 + a_up**2))
        roll_acc = math.atan2(a_right, a_up) 
        
        self.pitch = pitch_acc
        self.roll = roll_acc
        
        # 4. YAW Calculation
        
        if self.use_gyro:
            # Transform Gyro to Body Frame corresponding to Euler Angles
            b_x = np.dot(gyro_vec, fwd)
            b_y = np.dot(gyro_vec, right)
            b_z = np.dot(gyro_vec, up)
            
            # Euler Rates
            phi = self.roll
            theta = self.pitch
            
            cos_phi = math.cos(phi)
            sin_phi = math.sin(phi)
            cos_theta = math.cos(theta)
            if abs(cos_theta) < 0.001: cos_theta = 0.001 
            
            # yaw_rate = (q sin(phi) + r cos(phi)) / cos(theta)
            # If Up is Z (Yaw axis):
            yaw_rate = (b_y * sin_phi + b_z * cos_phi) / cos_theta
            
            # Invert Yaw Rate (Feedback: "Flipped")
            self.yaw -= yaw_rate * dt
        
        # Magnetometer
        if self.use_magnetometer:
            # Map mag
            m_x = np.dot(mag_vec, fwd)
            m_y = np.dot(mag_vec, right)
            m_z = np.dot(mag_vec, up)
            
            # De-rotate
            m_y_new = m_y * cos_phi - m_z * sin_phi
            m_z_new = m_y * sin_phi + m_z * cos_phi
            m_x_new = m_x * cos_theta + m_z_new * math.sin(theta)
            
            # Calculate Heading
            mag_yaw = math.atan2(-m_y_new, m_x_new)
            
            # Fix Wrap for Filter
            diff = mag_yaw - self.yaw
            while diff > math.pi: diff -= 2*math.pi
            while diff < -math.pi: diff += 2*math.pi
            
            # Filter
            self.yaw += (1.0 - self.alpha_yaw) * diff
            
        # Normalize
        if self.yaw > math.pi: self.yaw -= 2*math.pi
        if self.yaw < -math.pi: self.yaw += 2*math.pi
        
        y_final = self.yaw
        if self.relative_yaw:
            if self.first_run:
                self.yaw_offset = self.yaw
                self.first_run = False
            
            y_final = self.yaw - self.yaw_offset
            if y_final > math.pi: y_final -= 2*math.pi
            if y_final < -math.pi: y_final += 2*math.pi

        return math.degrees(self.roll), math.degrees(self.pitch), math.degrees(y_final), (gx, gy, gz)
