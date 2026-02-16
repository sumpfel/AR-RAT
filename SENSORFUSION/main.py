import argparse
import time
import sys
import os

# Argument Parsing
def parse_args():
    parser = argparse.ArgumentParser(description="AR RAT Sensor Fusion HUD")
    
    # Mode Selection
    parser.add_argument('--mode', choices=['normal', 'no-hud', 'debug'], default='normal',
                        help="Operation mode: 'normal' (HUD), 'no-hud' (Console only), 'debug' (3D Cube)")
    
    # Logic Version
    parser.add_argument('--version', choices=['1', '2'], default='2',
                        help="Sensor Fusion Logic Version: '1' (Original), '2' (Improved Yaw)")
    
    # Original Arguments (preserved for compatibility)
    parser.add_argument('--forward-axis', default='-x')
    parser.add_argument('--up-axis', default='y')
    
    # Sensor Flags (Standardized)
    # Use --gyro / --no-gyro
    parser.add_argument('--gyro', action=argparse.BooleanOptionalAction, default=True, help="Enable/Disable Gyroscope (Default: On)")
    
    # Use --magnetometer / --no-magnetometer
    parser.add_argument('--magnetometer', action=argparse.BooleanOptionalAction, default=False, help="Enable/Disable Magnetometer (Default: Off)")
    
    parser.add_argument('--relative-yaw', action='store_true')
    parser.add_argument('--target-priority', choices=['center', 'dark'], default='center')
    parser.add_argument('--sound-mode', choices=['none', 'alarm', 'all'], default='none')
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    print(f"Starting Sensor Fusion AR RAT")
    print(f"Mode: {args.mode} | Version: {args.version}")
    
    use_gyro = args.gyro
    use_magnetometer = args.magnetometer
    
    # 1. Initialize Sensor Fusion Engine
    if args.version == '1':
        from fusion_v1 import SensorFusionV1 as FusionEngine
    else:
        from fusion_v2 import SensorFusionV2 as FusionEngine
        
    try:
        engine = FusionEngine(
            use_gyro=use_gyro,
            use_magnetometer=use_magnetometer,
            relative_yaw=args.relative_yaw,
            forward_axis=args.forward_axis,
            up_axis=args.up_axis,
            target_priority=args.target_priority
        )
    except Exception as e:
        print(f"Failed to initialize Sensor Engine: {e}")
        return

    # 2. Initialize Camera Logic (Only if needed for HUD or Data)
    # We might want camera data even in 'no-hud' if we are logging?
    # But definitely needed for 'normal'.
    # For 'debug', maybe not? User said: "debug (only a cube and a ground or something to orient it to)"
    # So we can skip camera in debug mode to save resources / focus on sensors.
    
    camera_logic = None
    if args.mode == 'normal':
         try:
             import camera_logic
             cam = camera_logic.CameraLogic(target_priority=args.target_priority)
         except Exception as e:
             print(f"Camera Init Failed: {e}")
             cam = None
    else:
         cam = None

    # 3. Initialize Visualizer
    vis = None
    if args.mode == 'normal':
        try:
            import vis_hud
            vis = vis_hud.Visualizer()
        except Exception as e:
             print(f"HUD Visualizer Init Failed: {e}")
    elif args.mode == 'debug':
        try:
            import vis_debug
            vis = vis_debug.DebugVisualizer()
        except Exception as e:
             print(f"Debug Visualizer Init Failed: {e}")

    # 4. Initialize Sound (Optional)
    snd = None
    if args.sound_mode != 'none' and args.mode == 'normal':
        try:
            import sound_manager
            snd = sound_manager.SoundManager(mode=args.sound_mode)
        except Exception as e:
            print(f"Sound Manager Init Failed: {e}")

    # 5. Main Loop
    print("System active. Press Ctrl+C to exit.")
    try:
        while True:
            # A. Update Sensors
            roll, pitch, yaw, gyro_v = engine.update()
            
            # B. Update Camera (if active)
            active_targets = 0
            face_img = None
            face_lum = 0
            
            if cam:
                # Assuming cam.update() logic matches implicit understanding or need check
                # Note: I wrote CameraLogic.update() to return (targets, img, lum)
                # But wait, did I instantiate it? Yes `cam`
                # But the import was inside the block. 
                # `cam` is the instance.
                try:
                    active_targets, face_img, face_lum = cam.update()
                except Exception as e:
                    print(f"Camera Update Error: {e}", end='\r')
            
            # C. Update Sound
            if snd:
                 is_inverted = (abs(roll) > 120 or abs(pitch) > 85)
                 snd.update(is_inverted, active_targets)
            
            # D. Update Visualizer / Output
            if vis:
                # Both visualizers should have an update method with compatible signature OR we adapt
                # HUD: update(r, p, y, gyro_v, active_targets, face_img, face_lum)
                # Debug: update(r, p, y, gyro_v, active_targets, face_img, face_lum) - I should ensure this signature matches
                if not vis.update(roll, pitch, yaw, gyro_v=gyro_v, active_targets=active_targets, face_img=face_img, face_lum=face_lum):
                    break
            else:
                # Console Output for No-HUD
                print(f"R: {roll:>6.1f} | P: {pitch:>6.1f} | Y: {yaw:>6.1f}", end='\r')
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"\nCritical Error: {e}")
    finally:
        if cam: cam.close()
        # pygame quit handled in vis update usually, but can force quit here if needed
        import pygame
        pygame.quit()

if __name__ == "__main__":
    main()
