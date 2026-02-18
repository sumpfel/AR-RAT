import time
import math
import json
import os
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread
from adafruit_lsm6ds import LSM6DSOX
from adafruit_lis3mdl import LIS3MDL
from core.hardware import HardwareManager

class SensorFusionModule(QObject):
    # Signal: roll, pitch, yaw, (gx, gy, gz), active_targets, face_img, face_lum
    # Note: pyqtSignal arguments must be types. 
    # face_img is numpy array (object), face_lum is int.
    orientation_changed = pyqtSignal(float, float, float, tuple, int, object, int)
    
    def __init__(self):
        super().__init__()
        self.hw = HardwareManager()
        self.running = False
        
        # Sensor Objects
        self.lsm = None
        self.lis = None
        self.lsm_addr = None
        self.lis_addr = None
        
        # Fusion Parameters
        self.dt = 0.01
        self.alpha_yaw = 0.98
        self.use_gyro = True
        self.use_magnetometer = True
        
        # State
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.yaw_offset = 0.0
        self.first_run = True
        self.last_ts = time.time()
        
        # Calibration
        self.gyro_offset = [0, 0, 0]
        self.mag_off = [0, 0, 0]
        self.mag_scale = [1, 1, 1]
        self.mag_min = [1000, 1000, 1000]
        self.mag_max = [-1000, -1000, -1000]
        self.mag_cal_samples = 0
        
        # Axis Config
        self.forward_axis = 'x'
        self.up_axis = 'y'

    def start(self):
        print("[SensorFusion] Starting...")
        if not self.init_sensors():
            print("[SensorFusion] Failed to init sensors.")

        self.load_calibration()
        
        # Init Camera Logic
        try:
            from apps.camera_logic import CameraLogic
            self.cam = CameraLogic()
            print("[SensorFusion] CameraLogic Initialized.")
        except Exception as e:
            print(f"[SensorFusion] Camera Init Failed: {e}")
            self.cam = None

        self.running = True
        
        # Start Update Loop (Timer for simplicity, 100Hz)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(10) # 10ms = 100Hz
        
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
            
        # Init LIS3MDL
        for addr in [0x1C, 0x1E]:
            try:
                self.lis = LIS3MDL(i2c, address=addr)
                self.lis_addr = addr
                print(f"[SensorFusion] LIS3MDL found at 0x{addr:x}")
                break
            except Exception: pass
            
        if self.lsm and self.lis:
            return True
        return False

    def load_calibration(self):
        # Load Mag
        try:
            with open(f"mag_config_0x{self.lis_addr:x}.json", "r") as f:
                data = json.load(f)
                self.mag_off = [data["offset_x"], data["offset_y"], data["offset_z"]]
                self.mag_scale = [data["scale_x"], data["scale_y"], data["scale_z"]]
        except:
             print("[SensorFusion] No Mag Config found, using defaults.")

        # Load Gyro
        try:
            with open("gyro_config.json", "r") as f:
                data = json.load(f)
                self.gyro_offset = [data["x"], data["y"], data["z"]]
        except:
             print("[SensorFusion] No Gyro Config found.")

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
        
        try:
            # Read Sensors
            if self.lsm:
                gx, gy, gz = self.lsm.gyro
                ax, ay, az = self.lsm.acceleration
            else:
                gx, gy, gz = 0, 0, 0
                ax, ay, az = 0, 0, 0
                
            if self.lis:
                mx, my, mz = self.lis.magnetic
            else:
                mx, my, mz = 0, 0, 0
            
            # Continuous Mag Cal
            changed = False
            raw_mag = [mx, my, mz]
            for i in range(3):
                if raw_mag[i] < self.mag_min[i]:
                    self.mag_min[i] = raw_mag[i]; changed = True
                if raw_mag[i] > self.mag_max[i]:
                    self.mag_max[i] = raw_mag[i]; changed = True
            
            if changed:
                 self.mag_cal_samples += 1
                 # Simple Hard Iron Re-calc
                 for i in range(3):
                     self.mag_off[i] = (self.mag_min[i] + self.mag_max[i]) / 2.0
            
            # Apply Offsets
            scale = math.pi / 180.0
            gx = (gx - self.gyro_offset[0]) * scale
            gy = (gy - self.gyro_offset[1]) * scale
            gz = (gz - self.gyro_offset[2]) * scale
            
            mx = (mx - self.mag_off[0]) * self.mag_scale[0]
            my = (my - self.mag_off[1]) * self.mag_scale[1]
            mz = (mz - self.mag_off[2]) * self.mag_scale[2]
            
            # Fusion
            fwd = self.get_axis_vector(self.forward_axis)
            up = self.get_axis_vector(self.up_axis)
            right = np.cross(fwd, up)
            
            acc = np.array([ax, ay, az])
            # Pitch/Roll
            a_fwd = np.dot(acc, fwd)
            a_right = np.dot(acc, right)
            a_up = np.dot(acc, up)
            
            self.pitch = math.atan2(a_fwd, math.sqrt(a_right**2 + a_up**2))
            self.roll = math.atan2(a_right, a_up)
            
            # Heading - Simplified for checking only
            mag = np.array([mx, my, mz])
            m_x = np.dot(mag, fwd)
            m_y = np.dot(mag, right)
            
            self.yaw = math.atan2(-m_y, m_x) # Basic
            
            # Camera Update
            active_targets = 0
            face_img = None
            face_lum = 0
            
            # Get tracking state from config via helper or passed in?
            # Importing config here to check dynamic flag
            import config
            tracking_enabled = getattr(config, 'FACE_TRACKING', True)
            
            if self.cam and tracking_enabled:
                 active_targets, face_img, face_lum = self.cam.update()

            # Emit
            self.orientation_changed.emit(
                math.degrees(self.roll),
                math.degrees(self.pitch),
                math.degrees(self.yaw),
                (gx, gy, gz),
                active_targets,
                face_img,
                face_lum
            )
            
        except Exception as e:
            print(f"[SensorFusion] Update Error: {e}")
