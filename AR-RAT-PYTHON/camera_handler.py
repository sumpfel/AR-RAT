import cv2

class CameraHandler:
    def __init__(self, cam_index=0):
        self.cam_index = cam_index
        self.cap = None

    def start(self):
        """Attempts to open the camera and set the highest possible resolution."""
        self.cap = cv2.VideoCapture(self.cam_index)
        if not self.cap.isOpened():
            raise Exception(f"Could not open camera with index {self.cam_index}")

        # Try to set a high resolution - OpenCV will settle for the highest supported
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        
        # Read a frame to confirm and get actual resolution
        ret, frame = self.cap.read()
        if ret:
            h, w = frame.shape[:2]
            print(f"Camera started. Resolution: {w}x{h}")
        else:
            print("Warning: Camera opened but failed to read initial frame.")

    def get_frame(self):
        """Reads a frame from the camera."""
        if self.cap:
            return self.cap.read()
        return False, None

    def release(self):
        if self.cap:
            self.cap.release()
