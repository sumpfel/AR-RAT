from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QPixmap, QPainter
import os
import cv2
import random

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
        self.mouth_images = {}
        self.load_assets()
        
        # State
        self.current_waifu_path = None
        self.current_waifu_pixmap = None
        self.mouth_rect = None # (x, y, w, h) relative to original image
        
        self.state = "idle"
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_frame = 0
        
        self.pick_random_waifu()

    def load_assets(self):
        # Load mouth images
        for name in ["closed", "open", "wide"]:
            path = os.path.join(self.mouth_dir, f"{name}.png")
            if os.path.exists(path):
                self.mouth_images[name] = QPixmap(path)
        
    def pick_random_waifu(self):
        # Pick random image
        if not os.path.exists(self.waifu_dir):
            return

        files = [f for f in os.listdir(self.waifu_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
        if not files:
            return
            
        choice = random.choice(files)
        self.current_waifu_path = os.path.join(self.waifu_dir, choice)
        self.current_waifu_pixmap = QPixmap(self.current_waifu_path)
        
        # Detect face
        img = cv2.imread(self.current_waifu_path)
        if img is None:
            return
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        
        if len(faces) > 0:
            # Pick largest face
            faces = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
            x, y, w, h = faces[0]
            # Estimate mouth position (bottom 1/4 of face usually)
            # Center of width, 80% down height?
            # Anime mouths are usually small and lower.
            mx = x + int(w * 0.3)
            my = y + int(h * 0.75)
            mw = int(w * 0.4)
            mh = int(h * 0.2) 
            self.mouth_rect = (mx, my, mw, mh)
        else:
            # Fallback
            w, h = img.shape[1], img.shape[0]
            self.mouth_rect = (w//3, int(h*0.6), w//3, h//6)

    def set_state(self, state):
        self.state = state
        if state == "talking":
            self.animation_timer.start(100) # 10fps
        else:
            self.animation_timer.stop()
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
        # We want to fit within the widget size but keep aspect ratio
        widget_size = self.size()
        scaled_pixmap = self.current_waifu_pixmap.scaled(widget_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        # Calculate centering
        x_off = (widget_size.width() - scaled_pixmap.width()) // 2
        y_off = (widget_size.height() - scaled_pixmap.height()) // 2
        
        painter.drawPixmap(x_off, y_off, scaled_pixmap)
        
        # Draw Mouth
        if self.mouth_rect:
            # Map mouth rect to scaled image
            orig_w = self.current_waifu_pixmap.width()
            orig_h = self.current_waifu_pixmap.height()
            
            if orig_w == 0 or orig_h == 0: return

            scale_x = scaled_pixmap.width() / orig_w
            scale_y = scaled_pixmap.height() / orig_h
            
            mx, my, mw, mh = self.mouth_rect
            
            dest_x = x_off + int(mx * scale_x)
            dest_y = y_off + int(my * scale_y)
            dest_w = int(mw * scale_x)
            dest_h = int(mh * scale_y)
            
            mouth_name = "closed"
            if self.state == "talking":
                # Cycle mouths: close -> open -> wide -> open
                cycle = ["closed", "open", "wide", "open"]
                mouth_name = cycle[self.animation_frame % len(cycle)]
            elif self.state == "idle":
                mouth_name = "closed"
            
            if mouth_name in self.mouth_images:
                mouth_pix = self.mouth_images[mouth_name]
                painter.drawPixmap(QRect(dest_x, dest_y, dest_w, dest_h), mouth_pix)
