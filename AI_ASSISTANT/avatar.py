from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, QPointF, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QImage, QPainterPath, QBrush, QMovie

import os
import cv2
import random
import json
import shutil
import numpy as np
import math
from waifu_manager import WaifuManager

class AvatarWidget(QWidget):
    mouthPositionChanged = pyqtSignal(QPoint)

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
        
        # Manager
        self.waifu_manager = WaifuManager(os.path.join(base_dir, "assets"))

        self.mouth_images = {}
        self.load_assets()
        
        # State
        self.current_waifu_path = None
        self.current_waifu_pixmap = None
        
        # Video/GIF State
        self.is_video = False
        self.video_cap = None
        self.movie = None # QMovie for GIFs
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
        self.mouth_images = {}
        # Expected vowels and shapes
        vowels = ["a", "e", "i", "o", "u", "closed", "open", "wide"]
        for name in vowels:
            path = os.path.join(self.mouth_dir, f"{name}.png")
            if os.path.exists(path):
                self.mouth_images[name] = QPixmap(path)
        
    def pick_random_waifu(self):
        files = self.waifu_manager.get_waifu_files()
        if not files:
            return
            
        choice = random.choice(files)
        self.load_waifu(os.path.join(self.waifu_dir, choice))

    def load_waifu(self, path):
        if not os.path.exists(path):
            return

        self.current_waifu_path = path
        
        # Clean up old
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None
        if self.movie:
            self.movie.stop()
            self.movie = None
        self.video_timer.stop()
        
        ext = os.path.splitext(path)[1].lower()
        
        if ext == '.gif':
            # Use QMovie for GIF (Supports transparency)
            self.is_video = True
            self.movie = QMovie(path)
            self.movie.frameChanged.connect(self.update_movie_frame)
            self.movie.start()
            # Initial frame
            self.movie.jumpToFrame(0)
            self.update_movie_frame()
            
        elif ext in ['.mp4', '.webm', '.mkv']:
            # Use OpenCV for video files
            self.is_video = True
            self.video_cap = cv2.VideoCapture(path)
            self.video_timer.start(33) # ~30 FPS
            ret, frame = self.video_cap.read()
            if ret:
                self.set_frame_pixmap(frame)
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # Reset
        else:
            # Static Image
            self.is_video = False
            self.current_waifu_pixmap = QPixmap(path)
            self.load_calibration()
    
    def update_movie_frame(self):
        if self.movie:
            self.current_waifu_pixmap = self.movie.currentPixmap()
            # If movie just started/changed, we might need to load calibration
            if self.mouth_rect is None:
                 self.load_calibration()
            self.update()

    def update_video_frame(self):
        if not self.is_video or not self.video_cap:
            return
            
        ret, frame = self.video_cap.read()
        if not ret:
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.video_cap.read()
            if not ret: return

        self.set_frame_pixmap(frame)
        self.update()

    def set_frame_pixmap(self, frame):
        height, width = frame.shape[:2]
        if frame.shape[2] == 4:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGBA)
            fmt = QImage.Format.Format_RGBA8888
        else:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            fmt = QImage.Format.Format_RGB888
            
        qimg = QImage(rgb_frame.data, width, height, frame.strides[0], fmt)
        self.current_waifu_pixmap = QPixmap.fromImage(qimg)

    def load_calibration(self):
        filename = os.path.basename(self.current_waifu_path)
        rect = self.waifu_manager.get_mouth_rect(filename)
        
        if rect:
            self.mouth_rect = rect
        else:
            self.detect_face_and_mouth()

    def detect_face_and_mouth(self):
        if self.is_video:
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
        dest_path = self.waifu_manager.import_waifu(source_path)
        self.load_waifu(dest_path)

    def toggle_calibration_mode(self):
        self.calibration_mode = not self.calibration_mode
        if self.calibration_mode and self.is_video and not self.mouth_rect and self.current_waifu_pixmap:
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
            
            if self.current_waifu_path:
                filename = os.path.basename(self.current_waifu_path)
                self.waifu_manager.set_mouth_rect(filename, self.mouth_rect)
            
            self.update()
        
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        if self.calibration_mode and self.mouth_rect:
             delta = event.angleDelta().y()
             scale_factor = 1.1 if delta > 0 else 0.9
             
             mx, my, mw, mh = self.mouth_rect
             
             # Scale around center
             center_x = mx + mw / 2
             center_y = my + mh / 2
             
             new_w = max(10, int(mw * scale_factor))
             new_h = max(5, int(mh * scale_factor))
             
             new_mx = int(center_x - new_w / 2)
             new_my = int(center_y - new_h / 2)
             
             self.mouth_rect = (new_mx, new_my, new_w, new_h)

             if self.current_waifu_path:
                 filename = os.path.basename(self.current_waifu_path)
                 self.waifu_manager.set_mouth_rect(filename, self.mouth_rect)
             
             self.update()


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
            QTimer.singleShot(5000, lambda: self.set_emotion(None))
        self.update()

    def update_animation(self):
        self.animation_frame += 1
        self.update() 

    def paintEvent(self, event):
        if not self.current_waifu_pixmap:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        widget_size = self.size()
        scaled_pixmap = self.current_waifu_pixmap.scaled(widget_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        x_off = (widget_size.width() - scaled_pixmap.width()) // 2
        y_off = (widget_size.height() - scaled_pixmap.height()) // 2
        
        painter.drawPixmap(x_off, y_off, scaled_pixmap)
        
        mouth_center_for_signal = None

        # Define dimensions early
        orig_w = self.current_waifu_pixmap.width()
        orig_h = self.current_waifu_pixmap.height()
        if orig_w == 0 or orig_h == 0: return

        scale_x = scaled_pixmap.width() / orig_w
        scale_y = scaled_pixmap.height() / orig_h

        # Draw Mouth
        if self.mouth_rect:
            mx, my, mw, mh = self.mouth_rect
            
            dest_x = x_off + int(mx * scale_x)
            dest_y = y_off + int(my * scale_y)
            dest_w = int(mw * scale_x)
            dest_h = int(mh * scale_y)
            
            mouth_center_for_signal = QPoint(dest_x + dest_w//2, dest_y)

            mouth_name = "closed"
            should_draw_mouth = False

            if self.state == "talking":
                # Simulated Lip Sync: Random vowels
                # We use animation_frame to control speed, but we want randomness.
                # Every few frames change the vowel
                if self.animation_frame % 2 == 0:
                    vowels = ["a", "e", "i", "o", "u"]
                    # Filter available ones
                    available = [v for v in vowels if v in self.mouth_images]
                    if not available: available = ["open", "wide"] # Fallback
                    
                    # Choose pseudo-randomly based on frame to be deterministic per frame but chaotic
                    idx = (self.animation_frame * 7) % len(available)
                    self.current_mouth_name = available[idx] 
                
                mouth_name = getattr(self, "current_mouth_name", "a")
                should_draw_mouth = True
            
            if self.calibration_mode:
                pen = QPen(QColor(255, 0, 0), 2)
                painter.setPen(pen)
                painter.drawRect(dest_x, dest_y, dest_w, dest_h)
                mouth_name = "a" # Use 'a' for calibration (open mouth)
                should_draw_mouth = True

            elif self.state == "idle" and not self.is_video:
                mouth_name = "closed"
                should_draw_mouth = True
            
            if should_draw_mouth:
                # Fallback if specific vowel missing
                if mouth_name not in self.mouth_images:
                     if "open" in self.mouth_images and mouth_name != "closed": mouth_name = "open"
                     elif "closed" in self.mouth_images: mouth_name = "closed"
                
                if mouth_name in self.mouth_images:
                    mouth_pix = self.mouth_images[mouth_name]
                    painter.drawPixmap(QRect(dest_x, dest_y, dest_w, dest_h), mouth_pix)

        # Emit mouth center for bubble tail
        if mouth_center_for_signal:
            self.mouthPositionChanged.emit(mouth_center_for_signal)
        else:
             # Default to center of image if no mouth
             self.mouthPositionChanged.emit(QPoint(x_off + scaled_pixmap.width()//2, y_off + scaled_pixmap.height()//2))

        # Programmatic Expressions (Fixes background issue)
        if self.emotion:
            # Re-read face positions
            mx, my, mw, mh = self.mouth_rect if self.mouth_rect else (orig_w//2, orig_h//2, 50, 50)
            
            screen_mx = x_off + int(mx * scale_x)
            screen_my = y_off + int(my * scale_y)
            screen_mw = int(mw * scale_x)
            
            t = self.animation_frame

            if self.emotion == "angry":
                # Draw Red Anger Mark (Veins)
                # Usually top right
                cx = screen_mx + int(screen_mw * 2.5)
                cy = screen_my - int(screen_mw * 1.5)
                size = 40 + 5 * math.sin(t * 0.5)
                
                painter.setPen(QPen(QColor(220, 0, 0), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                
                # Draw # shape with curves
                #      /   \
                #     /     \
                #    /       \
                #   /   \ /   \
                #       X
                #   \  / \  /
                
                # Simplified "Vein" mark: 4 curves radiating from center
                for angle in [45, 135, 225, 315]:
                    rad = math.radians(angle)
                    p1 = QPointF(cx + math.cos(rad)*10, cy + math.sin(rad)*10)
                    p2 = QPointF(cx + math.cos(rad)*size, cy + math.sin(rad)*size)
                    
                    path = QPainterPath()
                    path.moveTo(p1)
                    # Add a curve to make it look organic
                    ctrl = QPointF(cx + math.cos(rad+0.2)*size*0.5, cy + math.sin(rad+0.2)*size*0.5)
                    path.quadTo(ctrl, p2)
                    painter.drawPath(path)

            elif self.emotion == "sweat":
                 # Draw Blue Sweat Drop
                 # Side of head
                 sx = screen_mx + int(screen_mw * 2.0)
                 sy = screen_my - int(screen_mw * 1.0)
                 slide = (t * 2) % 20
                 sy += int(slide)
                 
                 w = 30
                 h = 50
                 
                 path = QPainterPath()
                 path.moveTo(sx, sy) # Top tip
                 path.cubicTo(sx + w, sy + h, sx - w, sy + h, sx, sy) # Bottom bulb
                 
                 painter.setBrush(QBrush(QColor(100, 200, 255)))
                 painter.setPen(QPen(QColor(50, 100, 200), 2))
                 painter.drawPath(path)
                 
                 # Shine
                 painter.setBrush(QBrush(QColor(255, 255, 255)))
                 painter.setPen(Qt.PenStyle.NoPen)
                 painter.drawEllipse(sx - 5, sy + 30, 6, 10)

            elif self.emotion == "sad":
                # Tears Streaming down from "eyes" (approx above mouth)
                # Two streams
                eye_y = screen_my - int(screen_mw * 1.2)
                eye_x_left = screen_mx - int(screen_mw * 0.8)
                eye_x_right = screen_mx + int(screen_mw * 1.8) # Mouth is usually strictly center? assume mouth x is left corner? 
                # Actually mouth_rect x is left corner. so center is x + w/2
                center_x = screen_mx + screen_mw // 2
                eye_dist = int(screen_mw * 1.5)
                eye_x_left = center_x - eye_dist
                eye_x_right = center_x + eye_dist
                
                painter.setBrush(QBrush(QColor(150, 220, 255, 200)))
                painter.setPen(Qt.PenStyle.NoPen)
                
                slide = (t * 5) % 30
                
                for ex in [eye_x_left, eye_x_right]:
                     # Draw stream
                     path = QPainterPath()
                     path.moveTo(ex, eye_y)
                     path.quadTo(ex - 5, eye_y + 50 + slide, ex, eye_y + 100 + slide)
                     path.quadTo(ex + 5, eye_y + 50 + slide, ex, eye_y)
                     painter.drawPath(path)

            elif self.emotion == "blush":
                # Pink ellipses on cheeks
                center_x = screen_mx + screen_mw // 2
                cheek_y = screen_my - int(screen_mw * 0.5)
                dist = int(screen_mw * 1.5)
                
                painter.setBrush(QBrush(QColor(255, 100, 100, 100))) # Transparent pink
                painter.setPen(Qt.PenStyle.NoPen)
                
                # Left cheek
                painter.drawEllipse(QPointF(center_x - dist, cheek_y), 20, 15)
                # Right cheek
                painter.drawEllipse(QPointF(center_x + dist, cheek_y), 20, 15)
                
                # Lines
                painter.setPen(QPen(QColor(255, 50, 50, 150), 2))
                for i in range(3):
                    # diagonal lines
                    x = center_x - dist - 15 + i*10
                    y = cheek_y - 10
                    painter.drawLine(x, y, x-5, y+20)
                    
                    x = center_x + dist - 15 + i*10
                    painter.drawLine(x, y, x-5, y+20)

        if self.calibration_mode:
             painter.setPen(QPen(QColor(0, 255, 0), 2))
             painter.drawText(10, 20, "CALIBRATION MODE: Click mouth center")
