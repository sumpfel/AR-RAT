from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QImage
import os
import cv2
import random
import json
import shutil
import numpy as np

class AvatarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Helper to find absolute paths
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.face_cascade_path = os.path.join(base_dir, "assets", "lbpcascade_animeface.xml")
        self.face_cascade = cv2.CascadeClassifier(self.face_cascade_path)
        
        # Assets
        self.waifu_dir = os.path.join(base_dir, "assets", "waifus")
        self.mouth_dir = os.path.join(base_dir, "assets", "mouths")
        self.emotion_dir = os.path.join(base_dir, "assets", "emotions")
        
        self.mouth_images = {}
        self.emotion_images = {}
        self.load_assets()
        
        # State
        self.current_waifu_path = None
        self.current_waifu_pixmap = None
        
        # Video State
        self.is_video = False
        self.video_cap = None
        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self.update_video_frame)

        self.mouth_rect = None # (x, y, w, h) relative to original image
        
        self.state = "idle"
        self.emotion = None # "angry", "sad", "sweat", "blush"
        
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_frame = 0

        self.calibration_mode = False
        
        self.pick_random_waifu()

    def load_assets(self):
        # Load mouth images
        for name in ["closed", "open", "wide"]:
            path = os.path.join(self.mouth_dir, f"{name}.png")
            if os.path.exists(path):
                self.mouth_images[name] = QPixmap(path)
        
        # Load emotion images
        for name in ["angry", "sad", "sweat", "blush"]:
            path = os.path.join(self.emotion_dir, f"{name}.png")
            if os.path.exists(path):
                self.emotion_images[name] = QPixmap(path)
        
    def pick_random_waifu(self):
        # Pick random image or video
        if not os.path.exists(self.waifu_dir):
            return

        files = [f for f in os.listdir(self.waifu_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.mp4', '.webm', '.gif'))]
        if not files:
            return
            
        choice = random.choice(files)
        self.load_waifu(os.path.join(self.waifu_dir, choice))

    def load_waifu(self, path):
        if not os.path.exists(path):
            return

        self.current_waifu_path = path
        
        ext = os.path.splitext(path)[1].lower()
        if ext in ['.mp4', '.webm', '.gif', '.mkv']:
            self.is_video = True
            if self.video_cap:
                self.video_cap.release()
            self.video_cap = cv2.VideoCapture(path)
            self.video_timer.start(33) # ~30 FPS
            # Try to read one frame to set pixmap for sizing
            ret, frame = self.video_cap.read()
            if ret:
                self.set_frame_pixmap(frame)
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # Reset
        else:
            self.is_video = False
            self.video_timer.stop()
            if self.video_cap:
                self.video_cap.release()
                self.video_cap = None
            
            self.current_waifu_pixmap = QPixmap(path)
            self.load_calibration()
        
        self.update()

    def update_video_frame(self):
        if not self.is_video or not self.video_cap:
            return
            
        ret, frame = self.video_cap.read()
        if not ret:
            # Loop
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.video_cap.read()
            if not ret: return

        self.set_frame_pixmap(frame)
        self.update()

    def set_frame_pixmap(self, frame):
        # Handle alpha channel if present (4 channels)
        height, width = frame.shape[:2]
        
        if frame.shape[2] == 4:
            # BGRA to RGBA
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGBA)
            fmt = QImage.Format.Format_RGBA8888
        else:
            # BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            fmt = QImage.Format.Format_RGB888
            
        qimg = QImage(rgb_frame.data, width, height, frame.strides[0], fmt)
        self.current_waifu_pixmap = QPixmap.fromImage(qimg)

    def load_calibration(self):
        json_path = self.current_waifu_path + ".json"
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    self.mouth_rect = tuple(data["mouth_rect"])
            except:
                self.detect_face_and_mouth()
        else:
            self.detect_face_and_mouth()

    def detect_face_and_mouth(self):
        # We need an image to detect on.
        # If video, detection is expensive every frame, so we might skip it or detect on first frame
        if self.is_video:
            # For video, default to no mouth or maybe center?
            # It's better to let user calibrate video mouth manually if they want it
            self.mouth_rect = None 
            return

        if not self.current_waifu_path: return
        img = cv2.imread(self.current_waifu_path)
        if img is None: return
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        
        if len(faces) > 0:
            faces = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
            x, y, w, h = faces[0]
            mx = x + int(w * 0.3)
            my = y + int(h * 0.75)
            mw = int(w * 0.4)
            mh = int(h * 0.2) 
            self.mouth_rect = (mx, my, mw, mh)
        else:
            w, h = img.shape[1], img.shape[0]
            self.mouth_rect = (w//3, int(h*0.6), w//3, h//6)

    def import_waifu(self, source_path):
        if not os.path.exists(self.waifu_dir):
            os.makedirs(self.waifu_dir)
            
        filename = os.path.basename(source_path)
        dest_path = os.path.join(self.waifu_dir, filename)
        
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(filename)
            dest_path = os.path.join(self.waifu_dir, f"{base}_{random.randint(1000,9999)}{ext}")
            
        shutil.copy2(source_path, dest_path)
        self.load_waifu(dest_path)

    def toggle_calibration_mode(self):
        self.calibration_mode = not self.calibration_mode
        if self.calibration_mode and self.is_video and not self.mouth_rect and self.current_waifu_pixmap:
             # If starting calibration on video and no mouth exists, start at center
             w, h = self.current_waifu_pixmap.width(), self.current_waifu_pixmap.height()
             self.mouth_rect = (w//2 - 50, h//2 - 25, 100, 50)
             
        self.update()
        return self.calibration_mode
        
    def mousePressEvent(self, event):
        if self.calibration_mode and self.current_waifu_pixmap and event.button() == Qt.MouseButton.LeftButton:
            widget_size = self.size()
            scaled_pixmap = self.current_waifu_pixmap.scaled(widget_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            x_off = (widget_size.width() - scaled_pixmap.width()) // 2
            y_off = (widget_size.height() - scaled_pixmap.height()) // 2
            
            click_x = event.position().x() - x_off
            click_y = event.position().y() - y_off
            
            orig_w = self.current_waifu_pixmap.width()
            orig_h = self.current_waifu_pixmap.height()
            
            scale_x = orig_w / scaled_pixmap.width()
            scale_y = orig_h / scaled_pixmap.height()
            
            img_x = int(click_x * scale_x)
            img_y = int(click_y * scale_y)
            
            current_w = self.mouth_rect[2] if self.mouth_rect else int(orig_w * 0.1)
            current_h = self.mouth_rect[3] if self.mouth_rect else int(orig_h * 0.05)
            
            new_mx = img_x - current_w // 2
            new_my = img_y - current_h // 2
            
            self.mouth_rect = (new_mx, new_my, current_w, current_h)
            
            # Save calibration for video too
            if self.current_waifu_path:
                json_path = self.current_waifu_path + ".json"
                try:
                    with open(json_path, 'w') as f:
                        json.dump({"mouth_rect": self.mouth_rect}, f)
                except Exception as e:
                    print(f"Failed to save calibration: {e}")
            
            self.update()
        
        super().mousePressEvent(event)

    def set_state(self, state):
        self.state = state
        if state == "talking":
            self.animation_timer.start(100) # 10fps
        else:
            self.animation_timer.stop()
            self.update()

    def set_emotion(self, emotion):
        self.emotion = emotion
        if emotion:
            # Auto-clear emotion after 5 seconds
            QTimer.singleShot(5000, lambda: self.set_emotion(None))
        self.update()

    def update_animation(self):
        self.animation_frame += 1
        self.update() # Trigger repaint

    def paintEvent(self, event):
        if not self.current_waifu_pixmap:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Scaling
        widget_size = self.size()
        scaled_pixmap = self.current_waifu_pixmap.scaled(widget_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        x_off = (widget_size.width() - scaled_pixmap.width()) // 2
        y_off = (widget_size.height() - scaled_pixmap.height()) // 2
        
        painter.drawPixmap(x_off, y_off, scaled_pixmap)
        
        # Draw Mouth
        if self.mouth_rect:
            # Logic similar to before
            orig_w = self.current_waifu_pixmap.width()
            orig_h = self.current_waifu_pixmap.height()
            
            if orig_w == 0 or orig_h == 0: return # avoid div by zero

            scale_x = scaled_pixmap.width() / orig_w
            scale_y = scaled_pixmap.height() / orig_h
            
            mx, my, mw, mh = self.mouth_rect
            
            dest_x = x_off + int(mx * scale_x)
            dest_y = y_off + int(my * scale_y)
            dest_w = int(mw * scale_x)
            dest_h = int(mh * scale_y)
            
            mouth_name = "closed"
            should_draw_mouth = False

            if self.state == "talking":
                cycle = ["closed", "open", "wide", "open"]
                mouth_name = cycle[self.animation_frame % len(cycle)]
                should_draw_mouth = True
            
            if self.calibration_mode:
                pen = QPen(QColor(255, 0, 0), 2)
                painter.setPen(pen)
                painter.drawRect(dest_x, dest_y, dest_w, dest_h)
                mouth_name = "open"
                should_draw_mouth = True

            elif self.state == "idle" and not self.is_video:
                mouth_name = "closed"
                should_draw_mouth = True
            
            if should_draw_mouth and mouth_name in self.mouth_images:
                mouth_pix = self.mouth_images[mouth_name]
                painter.drawPixmap(QRect(dest_x, dest_y, dest_w, dest_h), mouth_pix)

        # Draw Emotion Overlay
        if self.emotion and self.emotion in self.emotion_images:
            emo_pix = self.emotion_images[self.emotion]
            
            # Position logic
            if self.mouth_rect:
                 mx, my, mw, mh = self.mouth_rect
            else:
                 mx, my, mw, mh = (orig_w//2, orig_h//2, 50, 50)

            scale_x = scaled_pixmap.width() / orig_w
            scale_y = scaled_pixmap.height() / orig_h
            
            screen_mx = x_off + int(mx * scale_x)
            screen_my = y_off + int(my * scale_y)
            
            t = self.animation_frame # Time factor
            
            if self.emotion == "angry":
                # Pulse size
                pulse = 1.0 + 0.1 * np.sin(t * 0.5) 
                w = int(100 * pulse)
                h = int(100 * pulse)
                x = screen_mx + int(100 * scale_x) 
                y = screen_my - int(150 * scale_y) 
                painter.drawPixmap(QRect(x, y, w, h), emo_pix)
                
            elif self.emotion == "sweat":
                # Slide down
                slide = (t * 2) % 20
                w = 80
                h = 100
                x = screen_mx + int(120 * scale_x) 
                y = screen_my - int(100 * scale_y) + slide
                painter.drawPixmap(QRect(x, y, w, h), emo_pix)
                
            elif self.emotion == "sad":
                # Tears
                w = 150
                h = 150
                x = screen_mx - int(w/2) 
                y = screen_my - int(100 * scale_y) 
                painter.drawPixmap(QRect(x, y, w, h), emo_pix)
            
            elif self.emotion == "blush":
                # Blush - Should be on cheeks, likely two spots or one central if it's a "strip"
                # The generated asset is two circles. So center it horizontally on mouth, but higher up.
                w = 200 # It's a pair of cheeks usually
                h = 100
                x = screen_mx - int(w/2) + int(mw * scale_x / 2) # Center on mouth's center x
                y = screen_my - int(80 * scale_y) # Above mouth
                
                # Check aspect ratio
                # If image is wide, keep aspect
                e_w, e_h = emo_pix.width(), emo_pix.height()
                aspect = e_w / e_h
                h = int(w / aspect)
                
                painter.setOpacity(0.7) # Slight transparency for blush
                painter.drawPixmap(QRect(x, y+10, w, h), emo_pix)
                painter.setOpacity(1.0)

        if self.calibration_mode:
             painter.setPen(QPen(QColor(0, 255, 0), 2))
             painter.drawText(10, 20, "CALIBRATION MODE: Click mouth center")
