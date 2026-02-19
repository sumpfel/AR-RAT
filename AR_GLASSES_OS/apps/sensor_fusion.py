import time
import math
import json
import os
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from adafruit_lsm6ds import LSM6DSOX
from adafruit_lis3mdl import LIS3MDL
from core.hardware import HardwareManager

class SensorFusionModule(QObject):
    # Signal: roll, pitch, yaw, (gx, gy, gz), active_targets, face_img, face_lum
    orientation_changed = pyqtSignal(float, float, float, tuple, int, object, int)
    
    def __init__(self):
        super().__init__()
        self.hw = HardwareManager()
        self.running = False
        
        # V2 Configuration (Defaults)
        self.use_gyro = True
        self.use_magnetometer = False # Default OFF as requested
        self.relative_yaw = False
        self.forward_axis = 'x' # Default for V2 (Was -x)
        self.up_axis = 'y'
        
        # Sensors
        self.lsm = None
        self.lis = None
        self.lsm_addr = None
        self.lis_addr = None
        
        # State
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.yaw_offset = 0.0
        self.first_run = True
        self.last_ts = time.time()
        
        # Filter Params
        self.dt = 0.01
        self.alpha_yaw = 0.98
        
        # Calibration
        self.gyro_offset = [0, 0, 0]
        self.mag_off = [0, 0, 0]
        self.mag_scale = [1, 1, 1]
        self.mag_min = [1000, 1000, 1000]
        self.mag_max = [-1000, -1000, -1000]
        self.mag_cal_samples = 0

    def start(self):
        print("[SensorFusion] Starting V2 Logic (Gyro Only)...")
        if not self.init_sensors():
            print("[SensorFusion] Failed to init sensors.")
        
        # Orientation Detection (V2 Logic)
        self.detect_orientation()
        
        self.load_calibration()
        
        # Init Camera
        try:
            from apps.camera_logic import CameraLogic
            self.cam = CameraLogic()
            print("[SensorFusion] CameraLogic Initialized.")
        except Exception as e:
            print(f"[SensorFusion] Camera Init Failed: {e}")
            self.cam = None

        self.running = True
        self.last_ts = time.time()
        
        # Timer 100Hz
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(10)

    def stop(self):
        self.running = False
        if hasattr(self, 'timer'):
            self.timer.stop()

    def init_sensors(self):
        i2c = self.hw.get_i2c()
        if i2c is None: return False
        
        # Init LSM6DSOX
        for addr in [0x6A, 0x6B]:
            try:
                self.lsm = LSM6DSOX(i2c, address=addr)
                self.lsm_addr = addr
                print(f"[SensorFusion] LSM6DSOX found at 0x{addr:x}")
                break
            except Exception: pass
            
        # Init LIS3MDL (Only if mag enabled, or always init but don't use?)
        # V2 inits both.
        for addr in [0x1C, 0x1E]:
            try:
                self.lis = LIS3MDL(i2c, address=addr)
                self.lis_addr = addr
                print(f"[SensorFusion] LIS3MDL found at 0x{addr:x}")
                break
            except Exception: pass
            
        return bool(self.lsm)

    def detect_orientation(self):
        print("[SensorFusion] Detecting Sensor Orientation... Keep device level!")
        ax_sum, ay_sum, az_sum = 0, 0, 0
        samples = 100
        
        # We need to wait for sensors to be ready, loop
        for _ in range(samples):
            if self.lsm:
                ax, ay, az = self.lsm.acceleration
            else:
                ax, ay, az = 0, 0, 0
            ax_sum += ax; ay_sum += ay; az_sum += az
            time.sleep(0.01) # 10ms * 100 = 1s delay
        
        avg_ax = ax_sum / samples
        avg_ay = ay_sum / samples
        avg_az = az_sum / samples
        
        avgs = {'x': avg_ax, 'y': avg_ay, 'z': avg_az}
        print(f"[SensorFusion] Gravity Vector: ({avg_ax:.2f}, {avg_ay:.2f}, {avg_az:.2f})")
        
        # Find axis with max gravity
        max_axis = max(avgs, key=lambda k: abs(avgs[k]))
        max_val = avgs[max_axis]
        
        # Determine sign
        sign = '+' if max_val > 0 else '-'
        
        self.up_axis = f"{sign if sign == '-' else ''}{max_axis}"
        print(f"[SensorFusion] Detected Up Axis: {self.up_axis} (Gravity)")
        
        # Alignment Logic (from V2)
        base_up = self.up_axis.strip('-')
        base_fwd = self.forward_axis.strip('-')
        
        if base_up == base_fwd:
            if base_up == 'x': self.forward_axis = 'y'
            elif base_up == 'y': self.forward_axis = 'z'
            else: self.forward_axis = 'x'
            print(f"[SensorFusion] Adjusted Forward Axis to: {self.forward_axis}")

    def load_calibration(self):
        # Load Gyro
        try:
            with open("gyro_config.json", "r") as f:
                data = json.load(f)
                self.gyro_offset = [data["x"], data["y"], data["z"]]
                print(f"[SensorFusion] Loaded Gyro Offsets: {self.gyro_offset}")
        except:
             print("[SensorFusion] No Gyro Config found (using 0,0,0).")

        # Load Mag (if needed)
        if self.use_magnetometer and self.lis_addr:
            try:
                with open(f"mag_config_0x{self.lis_addr:x}.json", "r") as f:
                    data = json.load(f)
                    self.mag_off = [data["offset_x"], data["offset_y"], data["offset_z"]]
                    self.mag_scale = [data["scale_x"], data["scale_y"], data["scale_z"]]
                    print(f"[SensorFusion] Loaded Mag Config.")
            except:
                 print("[SensorFusion] No Mag Config found.")

    def get_axis_vector(self, axis_name):
        axis_name = axis_name.lower().strip()
        sign = -1 if axis_name.startswith('-') else 1
        axis = axis_name.strip('-')
        if axis == 'x': return np.array([sign, 0, 0])
        if axis == 'y': return np.array([0, sign, 0])
        if axis == 'z': return np.array([0, 0, sign])
        return np.array([1, 0, 0])

    def update(self):
        if not self.running: return
        
        now = time.time()
        dt = now - self.last_ts
        self.last_ts = now
        # Cap dt to avoid jumps if thread hangs
        if dt > 0.1: dt = 0.01 
        
        try:
            # 1. Read Raw
            if self.lsm:
                gx, gy, gz = self.lsm.gyro
                ax, ay, az = self.lsm.acceleration
            else:
                gx, gy, gz = 0,0,0; ax, ay, az = 0,0,0
                
            mx, my, mz = 0,0,0
            if self.lis and self.use_magnetometer:
                mx, my, mz = self.lis.magnetic
                # (Mag Cal update logic omitted for brevity as Mag is OFF)

            # 2. Apply Offsets
            scale = math.pi / 180.0
            
            if self.use_gyro:
                gx = (gx - self.gyro_offset[0]) * scale
                gy = (gy - self.gyro_offset[1]) * scale
                gz = (gz - self.gyro_offset[2]) * scale
            else:
                gx, gy, gz = 0,0,0

            if self.use_magnetometer:
                mx = (mx - self.mag_off[0]) * self.mag_scale[0]
                my = (my - self.mag_off[1]) * self.mag_scale[1]
                mz = (mz - self.mag_off[2]) * self.mag_scale[2]

            # 3. Calculate Pitch/Roll (Accelerometer)
            fwd = self.get_axis_vector(self.forward_axis)
            up = self.get_axis_vector(self.up_axis)
            right = np.cross(fwd, up)
            
            acc = np.array([ax, ay, az])
            
            a_fwd = np.dot(acc, fwd)
            a_right = np.dot(acc, right)
            a_up = np.dot(acc, up)
            
            self.pitch = math.atan2(a_fwd, math.sqrt(a_right**2 + a_up**2))
            self.roll = math.atan2(a_right, a_up)
            
            # 4. Calculate Yaw (Gyro Integration - V2 Logic)
            gyro_vec = np.array([gx, gy, gz])
            
            # Transform Gyro to Body Frame
            b_x = np.dot(gyro_vec, fwd)
            b_y = np.dot(gyro_vec, right)
            b_z = np.dot(gyro_vec, up)
            
            # Euler Rates
            phi = self.roll
            theta = self.pitch
            
            c_phi = math.cos(phi); s_phi = math.sin(phi)
            c_theta = math.cos(theta)
            if abs(c_theta) < 0.001: c_theta = 0.001
            
            # Yaw Rate = (q sin(phi) + r cos(phi)) / cos(theta)
            # Assuming Up=Z (Yaw axis is Z)
            # b_y is q (pitch rate roughly), b_z is r (yaw rate roughly) in body
            # Wait, standard aerospace: p=x, q=y, r=z.
            # Here b_x, b_y, b_z depend on axis mapping.
            # If Fwd=X, Right=Y, Up=Z:
            #   Gyro X -> Roll rate
            #   Gyro Y -> Pitch rate
            #   Gyro Z -> Yaw rate
            # Formula checks out.
            
            yaw_rate = (b_y * s_phi + b_z * c_phi) / c_theta
            
            # Integrate
            # Note: "Invert Yaw Rate (Feedback: 'Flipped')" from V2
            self.yaw -= yaw_rate * dt
            
            # Magnetometer Correction (Optional / Off)
            if self.use_magnetometer:
                # ... (Logic omitted as requested OFF)
                pass
                
            # Normalize
            if self.yaw > math.pi: self.yaw -= 2*math.pi
            if self.yaw < -math.pi: self.yaw += 2*math.pi
            
            # Camera
            active_targets = 0; face_img = None; face_lum = 0
            if self.cam:
                import config
                if getattr(config, 'FACE_TRACKING', True):
                     active_targets, face_img, face_lum = self.cam.update()
            
            # Emit (Swapped Roll/Yaw as requested by user)
            # "switch roll and yaw"
            self.orientation_changed.emit(
                math.degrees(self.yaw),   # Send YAW as Roll
                -math.degrees(self.pitch), # Invert Pitch
                math.degrees(self.roll),  # Send ROLL as Yaw
                (gx, gy, gz),
                active_targets,
                face_img,
                face_lum
            )
            
        except Exception as e:
            print(f"[SensorFusion] Update Error: {e}")
