import sys
import os
import argparse

# Ensure we can import from the directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import SensorFusionEngine
import visualizer

def main():
    parser = argparse.ArgumentParser(description="Standalone Fighter Jet HUD Launcher")
    parser.add_argument('--bg-color', type=str, default='gray', help='Background color: gray, black, green, transparent')
    parser.add_argument('--windowed', action='store_true', help='Run in windowed mode instead of fullscreen')
    parser.add_argument('--use-gyro', action='store_true', help='Enable Gyroscope fusion')
    parser.add_argument('--use-magnetometer', action='store_true', help='Enable Magnetometer')
    args = parser.parse_args()

    # Defaults for "Cool HUD"
    fullscreen = not args.windowed
    
    # Color parsing
    colors = {
        'gray': (0.2, 0.2, 0.2, 1.0),
        'black': (0.0, 0.0, 0.0, 1.0),
        'green': (0.0, 1.0, 0.0, 1.0), # Chromakey
        'transparent': (0.0, 0.0, 0.0, 0.0) # Try generic transparency
    }
    bg = colors.get(args.bg_color, colors['gray'])

    print(f"Launching HUD... Fullscreen={fullscreen}, BG={args.bg_color}")
    print(f"Sensors: Gyro={args.use_gyro}, Mag={args.use_magnetometer} (Default: Accel Only)")
    
    try:
        vis = visualizer.Visualizer(fullscreen=fullscreen, bg_color=bg)
    except Exception as e:
        print(f"Failed to launch visualizer: {e}")
        return

    # User requested: "only using accelerometer" by default
    
    engine = SensorFusionEngine(
        use_gyro=args.use_gyro,           
        use_magnetometer=args.use_magnetometer,   
        relative_yaw=False,
        forward_axis='x',
        up_axis='z'
    )
    
    engine.run(visualizer=vis)

if __name__ == "__main__":
    main()
