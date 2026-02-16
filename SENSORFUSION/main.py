import time
import json
import os
import sys
import math
import argparse
import numpy as np
from ahrs.filters import Madgwick
import cv2
import mediapipe as mp

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import sensor_setup
import calibration

class SensorFusionEngine:
    def __init__(self, use_gyro=True, use_magnetometer=True, relative_yaw=False, forward_axis='x', up_axis='z', target_priority='center'):
        self.use_gyro = use_gyro
        self.use_magnetometer = use_magnetometer
        self.relative_yaw = relative_yaw
        self.target_priority = target_priority
        self.forward_axis = forward_axis
        self.up_axis = up_axis
        
        self.vis = None
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
        print("Sensor Fusion: LSM6DSOX + LIS3MDL")
        
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
                # We need mag vector in Body Frame corresponding to Fwd/Right/Up map?
                # Actually, standard formula assumes X=Forward, Y=Right, Z=Down usually?
                # Let's verify standard aviation frame: X=Nose, Y=Right, Z=Down.
                # Pitch is rotation around Y. Roll around X.
                # Here we have mapped acc_fwd ...
                
                # Simplified: Rotate Mag vector by -Roll then -Pitch to bring it to horizontal plane
                # Map mag to logical axes first
                mx_l = np.dot(mag_v, self.fwd_vec)
                my_l = np.dot(mag_v, self.right_vec)
                mz_l = np.dot(mag_v, self.up_vec)
                
                sin_r, cos_r = math.sin(roll), math.cos(roll)
                sin_p, cos_p = math.sin(pitch), math.cos(pitch)
                
                # De-rotate to horizontal
                # 1. De-roll (around X axis)
                # my' = my*cos(r) - mz*sin(r)
                # mz' = my*sin(r) + mz*cos(r)
                my_flat = my_l * cos_r - mz_l * sin_r
                mz_temp = my_l * sin_r + mz_l * cos_r
                
                # 2. De-pitch (around Y axis)
                # mx' = mx*cos(p) + mz'*sin(p)
                mx_flat = mx_l * cos_p + mz_temp * sin_p
                
                yaw = math.atan2(-my_flat, mx_flat)
                # DEBUG: Print mag values occasionally
                # norm = np.linalg.norm(mag_v)
                # print(f"DEBUG: Mag={mag_v} Yaw_Rad={yaw:.2f} Yaw_Deg={math.degrees(yaw):.1f}")
            else:
                yaw = 0.0
                # print("DEBUG: Mag Disabled logic hit", end='\r')
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
        
        # Ensure Yaw is positive 0-360 for display sometimes, but here we keep +/- 180
        # If user wants compass 0..360, we handle in visualizer.

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
             # If using Gyro (Madgwick), it handles smoothing internally via beta gain
             pass

        # Smooth Angles (Correct Wrap-Around)
        def smooth_angle(current, new_val, alpha):
            diff = new_val - current
            while diff > 180: diff -= 360
            while diff < -180: diff += 360
            return current + alpha * diff

        self.s_roll = smooth_angle(self.s_roll, r_deg, self.alpha)
        self.s_pitch = smooth_angle(self.s_pitch, p_deg, self.alpha)
        
        # Yaw can be very jittery, so we apply stronger smoothing
        # User reported "doesn't move much", so reducing smoothing (increasing alpha)
        # Previous: 0.05. New: 0.2 (Faster response)
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

    def run(self, visualizer=None, sound_manager=None):
        print("Starting loop. Press Ctrl+C to exit.")
        cap = cv2.VideoCapture(0)
        
        # Optimize Camera
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # Initialize MediaPipe Tasks Face Detector
        BaseOptions = mp.tasks.BaseOptions
        FaceDetector = mp.tasks.vision.FaceDetector
        FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blaze_face_short_range.tflite')
        
        options = FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=VisionRunningMode.IMAGE)
        
        with FaceDetector.create_from_options(options) as detector:
            try:
                while True:
                    # 1. Capture Camera
                    ret, frame = cap.read()
                    face_img = None
                    active_targets = 0
                    
                    if ret:
                        # Convert to RGB for MediaPipe
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                        
                        # Detect
                        detection_result = detector.detect(mp_image)
                        
                        if detection_result.detections:
                            active_targets = len(detection_result.detections)
                            h, w, _ = frame.shape
                            cx, cy = w/2, h/2
                            
                            min_val = float('inf') # Can represent Distance or Luminance
                            best_detection = None
                            
                            for detection in detection_result.detections:
                                # Get Bounding Box
                                bbox = detection.bounding_box
                                x = int(bbox.origin_x)
                                y = int(bbox.origin_y)
                                bw = int(bbox.width)
                                bh = int(bbox.height)
                                
                                # Clamp coords to frame
                                x = max(0, x); y = max(0, y)
                                bw = min(w-x, bw); bh = min(h-y, bh)
                                
                                if bw > 10 and bh > 10:
                                    metric = float('inf')
                                    
                                    if self.target_priority == 'dark':
                                         # Prioritize Lowest Luminance
                                         temp_crop = frame[y:y+bh, x:x+bw]
                                         temp_gray = cv2.cvtColor(temp_crop, cv2.COLOR_BGR2GRAY)
                                         lum = np.mean(temp_gray)
                                         metric = lum
                                    else:
                                         # Default: Prioritize Center
                                         fcx, fcy = x + bw/2, y + bh/2
                                         dist = math.hypot(fcx-cx, fcy-cy)
                                         metric = dist
                                    
                                    if metric < min_val:
                                        min_val = metric
                                        best_detection = (x, y, bw, bh)
                            
                            if best_detection:
                                x, y, bw, bh = best_detection
                                # Clamp
                                x = max(0, x); y = max(0, y)
                                bw = min(w-x, bw); bh = min(h-y, bh)
                                
                                if bw > 10 and bh > 10:
                                    crop = frame[y:y+bh, x:x+bw]
                                    # Black and White Film Effect
                                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                                    
                                    # Calculate Luminance (Mean Intensity) BEFORE filter for accuracy of subject
                                    # Scaled 0-255.
                                    face_lum = int(np.mean(gray))
                                    
                                    # Film Noir Effect: Variable Contrast + Grain
                                    # 1. Contrast (User requested "distortion is still way too much")
                                    # Reduced alpha to 1.1 (nearly natural) and beta to -10.
                                    face_contrasted = cv2.convertScaleAbs(gray, alpha=1.1, beta=-10)
                                    
                                    # 2. Add Noise (Film Grain) - User said "noise is good"
                                    # Generate random noise
                                    noise = np.zeros(face_contrasted.shape, dtype=np.uint8)
                                    cv2.randn(noise, 0, 20) # Mean 0, StdDev 20
                                    
                                    # Add noise (clip to protect uint8 wrap)
                                    face_img = cv2.add(face_contrasted, noise)
                        else:
                            # No Target: "Old TV Static" Effect
                            # Generate random noise block
                            noise_h, noise_w = 200, 200 # Fixed size block
                            face_img = np.zeros((noise_h, noise_w), dtype=np.uint8)
                            cv2.randu(face_img, 0, 255) # Uniform random noise 0-255
                    
                    # 2. Update Sensors
                    r, p, y, gyro_v = self.update()
                    
                    # 3. Sound Update
                    if sound_manager:
                        is_inverted = (abs(r) > 120 or abs(p) > 85) # Same logic as visualizer
                        sound_manager.update(is_inverted, active_targets)

                    print(f"R: {r:>6.1f} | P: {p:>6.1f} | Y: {y:>6.1f} | T: {active_targets}", end="\r")
                    
                    # 3. Update Visualizer
                    if visualizer:
                        if not visualizer.update(r, p, y, gyro_v=gyro_v, active_targets=active_targets, face_img=face_img, face_lum=face_lum if 'face_lum' in locals() else 0):
                            break
                    else:
                        time.sleep(0.01)

            except KeyboardInterrupt:
                print("\nExiting...")
            except Exception as e:
                print(f"\nError in loop: {e}")
            finally:
                cap.release()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Enable debug output (only values)')
    parser.add_argument('--hud', action='store_true', help='Enable visualization window')
    parser.add_argument('--forward-axis', default='x')
    parser.add_argument('--up-axis', default='z')
    parser.add_argument('--use-gyro', action='store_true')
    parser.add_argument('--use-magnetometer', action='store_true')
    parser.add_argument('--relative-yaw', action='store_true')
    parser.add_argument('--target-priority', choices=['center', 'dark'], default='center', help='Target selection criteria')
    parser.add_argument('--sound-mode', choices=['none', 'alarm', 'all'], default='none', help='Audio feedback mode')
    args = parser.parse_args()

    vis = None
    if args.hud:
        try:
            import visualizer
            vis = visualizer.Visualizer()
        except ImportError:
            print("Visualizer check failed")

    # Initialize Sound Manager
    import sound_manager
    snd = sound_manager.SoundManager(mode=args.sound_mode)
    
    engine = SensorFusionEngine(
        use_gyro=args.use_gyro,
        use_magnetometer=args.use_magnetometer,
        relative_yaw=args.relative_yaw,
        forward_axis=args.forward_axis,
        up_axis=args.up_axis,
        target_priority=args.target_priority
    )
    
    engine.run(visualizer=vis, sound_manager=snd)

if __name__ == "__main__":
    main()
