import cv2

class CameraHandler:
    def __init__(self, cam_index=0):
        self.cam_index = cam_index
        self.cap = None

    def start(self):
        self.cap = cv2.VideoCapture(self.cam_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise Exception(f"Could not open camera with index {self.cam_index}")
        
        # Optimize buffer size for low latency
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # 🔑 FORCE FAST CAMERA MODE (must be first)
        self.cap.set(cv2.CAP_PROP_FOURCC,
                     cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        # Common resolutions to test, from highest to lowest
        resolutions = [
            (1920, 1080),
            (1280, 720),
            (640, 480)
        ]

        best_res = None
        best_fps = 0

        for w, h in resolutions:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            
            # Read back actual resolution and FPS
            actual_w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

            print(f"Testing {w}x{h}: Got {actual_w}x{actual_h} @ {actual_fps} FPS")

            if actual_fps >= 25:
                best_res = (actual_w, actual_h)
                best_fps = actual_fps
                break # Found the highest res with good FPS
            
            if best_res is None or actual_fps > best_fps:
                best_res = (actual_w, actual_h)
                best_fps = actual_fps

        # Set final best resolution
        if best_res:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, best_res[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, best_res[1])
            self.target_fps = best_fps
        else:
            self.target_fps = 30 # Fallback

        # Read a frame to confirm
        ret, frame = self.cap.read()
        if ret:
            h, w = frame.shape[:2]
            print(f"Camera started. Final Resolution: {w}x{h} @ {self.target_fps} FPS")
        else:
            print("Warning: Camera opened but failed to read initial frame.")

    def get_target_fps(self):
        return self.target_fps

    def get_frame(self):
        """Reads a frame from the camera."""
        if self.cap:
            return self.cap.read()
        return False, None

    def release(self):
        if self.cap:
            self.cap.release()
