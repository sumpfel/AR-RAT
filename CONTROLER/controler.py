import os
import signal
import subprocess
import time
import board
import digitalio

# Ensure Blinka knows we are using FT232H
os.environ["BLINKA_FT232H"] = "1"

# Configuration
BUTTON_PIN = board.D4
CAM_INPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "CAM-INPUT"))
RUN_SCRIPT = os.path.join(CAM_INPUT_DIR, "run.sh")

class CamController:
    def __init__(self):
        # Setup button
        # On FT232H, we use internal pull-up. Button should connect pin to GND.
        self.button = digitalio.DigitalInOut(BUTTON_PIN)
        self.button.direction = digitalio.Direction.INPUT
        # self.button.pull = digitalio.Pull.UP # NOT SUPPORTED on FT232H via Blinka
        
        self.process = None
        self.last_button_state = True # HIGH (unpressed) due to pull-up
        
    def start_cam_input(self):
        if self.process is None or self.process.poll() is not None:
            print(f"Starting CAM-INPUT in {CAM_INPUT_DIR}...")
            # We use preexec_fn=os.setsid to create a process group so we can kill children too
            self.process = subprocess.Popen(
                [RUN_SCRIPT],
                cwd=CAM_INPUT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                preexec_fn=os.setsid
            )
            print(f"Process started with PID: {self.process.pid}")
        else:
            print("CAM-INPUT is already running.")

    def stop_cam_input(self):
        if self.process and self.process.poll() is None:
            print("Stopping CAM-INPUT...")
            # Send TERM to the whole process group
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Force killing CAM-INPUT...")
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            self.process = None
            print("CAM-INPUT stopped.")
        else:
            print("CAM-INPUT is not running.")

    def toggle(self):
        if self.process and self.process.poll() is None:
            self.stop_cam_input()
        else:
            self.start_cam_input()

    def run(self):
        print("Controler active. Listening for button presses on D4...")
        print("Ensure the FT232H is connected and BLINKA_FT232H=1 is set if needed.")
        
        try:
            while True:
                current_state = self.button.value
                
                # Detect falling edge (High to Low -> Pressed)
                if not current_state and self.last_button_state:
                    print("Button Pressed!")
                    self.toggle()
                    # Simple debounce
                    time.sleep(0.3)
                
                self.last_button_state = current_state
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("\nShutting down controller...")
            self.stop_cam_input()

if __name__ == "__main__":
    controller = CamController()
    controller.run()
