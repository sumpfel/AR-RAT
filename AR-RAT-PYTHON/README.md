# Hand Gesture Recognition

This project detects hand gestures and sends them via UDP.

## Requirements
- Python 3.x
- `opencv-python`
- `mediapipe`

Install:
```bash
pip install opencv-python mediapipe
```

## Usage

### 1. Debug Mode (Live Preview)
Run this to test your camera and see the detection overlay.
```bash
python main.py --mode debug
```

### 2. Record New Gestures
Run in record mode to add custom gestures.
```bash
python main.py --mode record
```
- Show your hand to the camera.
- Press **'r'** on your keyboard.
- Type the name of the gesture in the terminal and press Enter.
- The gesture is saved to `gestures.json`.

### 3. Normal Mode (Headless / Production)
Runs without a window (faster) and sends UDP packets.
```bash
python main.py --mode normal --udp_ip 127.0.0.1 --udp_port 5005
```

## Customization
- **Camera Resolution**: The script automatically tries to set 1920x1080.
- **Gestures**: 
    - Basic counters (1-5, Fist) are built-in.
    - Custom gestures are saved in `gestures.json`.
