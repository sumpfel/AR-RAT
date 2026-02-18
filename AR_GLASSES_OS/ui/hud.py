import math
import numpy as np
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF, QBrush, QImage, QPixmap
from PyQt6.QtCore import QPointF, QRectF

class SensorFusionHUD(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) # Click through
        
        # Data
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.gyro = (0, 0, 0)
        
        # Camera Data
        self.active_targets = 0
        self.face_img = None
        self.face_lum = 0
        
        # Modes: 1=Lines, 2=Compass, 3=Targeting, 4=Debug
        self.mode = 1 
        
        # Style
        self.color_hud = QColor(0, 255, 0, 255) # Bright Green
        self.color_alarm = QColor(255, 0, 0, 255) # Red
        self.font_hud = QFont("Monospace", 20, QFont.Weight.Bold)
        self.font_alarm = QFont("Monospace", 30, QFont.Weight.Bold)
        
        # Cube Data for Debug
        self.cube_vertices = [
            [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
            [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]
        ]
        self.cube_edges = [
            (0,1), (1,2), (2,3), (3,0),
            (4,5), (5,6), (6,7), (7,4),
            (0,4), (1,5), (2,6), (3,7)
        ]

    def handle_input(self, btn):
        import config
        # Map Buttons to Modes
        if btn == config.PIN_D4: # UP
            self.mode = 1
        elif btn == config.PIN_C4: # LEFT
            self.mode = 2
        elif btn == config.PIN_C6: # RIGHT
            self.mode = 3
        elif btn == config.PIN_C3: # DOWN
            self.mode = 4
        self.update()

    def update_data(self, r, p, y, gyro_data, active_targets=0, face_img=None, face_lum=0):
        self.roll = r
        self.pitch = p
        self.yaw = y
        self.gyro = gyro_data
        self.active_targets = active_targets
        self.face_img = face_img
        self.face_lum = face_lum
        self.update() # Trigger repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dynamic Config
        import config
        base_scale = config.UI_SCALE
        scale = base_scale * 2.0 
        
        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2
        
        # Update Fonts
        self.font_hud.setPointSize(int(14 * scale))
        self.font_alarm.setPointSize(int(24 * scale))
        
        # Common Pen
        pen = QPen(self.color_hud)
        pen.setWidth(int(3 * scale))
        painter.setPen(pen)
        painter.setFont(self.font_hud)
        
        # Check Alarm (Overlay regardless of mode? Or only some modes?)
        # Let's show alarm in all modes for safety
        is_inverted = abs(self.pitch) > 70 or abs(self.roll) > 70
        if is_inverted:
            pen_alarm = QPen(self.color_alarm)
            pen_alarm.setWidth(int(5 * scale))
            painter.setPen(pen_alarm)
            painter.drawRect(0, 0, w, h)
            
            painter.setFont(self.font_alarm)
            painter.setPen(self.color_alarm)
            painter.drawText(int(cx - 150*scale), int(cy), "OVERHEAD / INVERTED")
            
            # Reset
            painter.setPen(pen)
            painter.setFont(self.font_hud)

        # Draw based on Mode
        if self.mode == 1: # Horizon + Lines
            self.draw_horizon_ladder(painter, w, h, scale, cx, cy)
        
        elif self.mode == 2: # Compass Only
            self.draw_compass(painter, w, h, scale, cx, cy)
            
        elif self.mode == 3: # Targeting
            self.draw_targeting(painter, w, h, scale, cx, cy)
            
        elif self.mode == 4: # Debug Cube
             self.draw_debug_cube(painter, w, h, scale, cx, cy)
             
        # Always draw Orientation Stats small at bottom? User wanted "modes".
        # Mode 1 has them? Mode 2? 
        # Making them exclusive clean views.
        # Maybe Mode 1 needs Pitch/Roll numbers?
        if self.mode == 1:
             painter.drawText(20, int(h - 40*scale), f"R: {self.roll:.1f}  P: {self.pitch:.1f}")

    def draw_horizon_ladder(self, painter, w, h, scale, cx, cy):
        pixels_per_deg = 15 * scale
        
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self.roll) 
        
        # Horizon
        y_horizon = (self.pitch) * pixels_per_deg
        painter.drawLine(int(-w), int(y_horizon), int(w), int(y_horizon))
        painter.drawText(int(-20*scale), int(y_horizon - 5), "--- 0 ---")
        
        # Pitch Lines
        min_p = int(self.pitch - 40)
        max_p = int(self.pitch + 40)
        min_p = (min_p // 10) * 10
        max_p = (max_p // 10) * 10
        
        for i in range(min_p, max_p + 1, 10):
            if i == 0: continue
            y_pos = (self.pitch - i) * pixels_per_deg
            if -h/2 < y_pos < h/2:
                length = (60 * scale) if i % 20 != 0 else (100 * scale)
                gap = 20 * scale
                painter.drawLine(int(-length - gap), int(y_pos), int(-gap), int(y_pos))
                painter.drawLine(int(gap), int(y_pos), int(length + gap), int(y_pos))
                painter.drawText(int(length + gap + 5), int(y_pos + 10), f"{i}")
        painter.restore()

    def draw_compass(self, painter, w, h, scale, cx, cy):
        tape_y = cy - 20 * scale # Center vertically? Or Top? User said "Compass Only".
        # Let's put it in center for "Compass Mode"
        
        tape_width = w * 0.8
        pixel_per_yaw_deg = 8 * scale
        
        # Pointer
        painter.drawLine(int(cx), int(tape_y - 20), int(cx), int(tape_y + 20))
        # Large Value
        f_large = QFont("Monospace", int(30 * scale), QFont.Weight.Bold)
        painter.setFont(f_large)
        painter.drawText(int(cx - 50*scale), int(tape_y - 40), f"{int(self.yaw)%360:03d}")
        
        painter.setFont(self.font_hud) # Reset
        
        vis_range = int((tape_width / 2) / pixel_per_yaw_deg)
        start_deg = int(self.yaw) - vis_range
        end_deg = int(self.yaw) + vis_range
        
        for d in range(start_deg, end_deg + 1):
            if d % 5 == 0: 
                d_wrap = d % 360
                x_off = (d - self.yaw) * pixel_per_yaw_deg
                x_pos = cx + x_off
                
                height = 20 * scale
                label = ""
                if d_wrap == 0: label = "N"; height=30 * scale
                elif d_wrap == 90: label = "E"; height=30 * scale
                elif d_wrap == 180: label = "S"; height=30 * scale
                elif d_wrap == 270: label = "W"; height=30 * scale
                elif d_wrap % 15 == 0: label = f"{d_wrap}"
                
                painter.drawLine(int(x_pos), int(tape_y), int(x_pos), int(tape_y + height))
                if label:
                     painter.drawText(int(x_pos) - 10, int(tape_y + height + 20), label)

    def draw_targeting(self, painter, w, h, scale, cx, cy):
         # Center Text
         painter.drawText(int(cx - 100*scale), 50, f"TARGETS: {self.active_targets}")
         
         if self.face_img is not None:
             try:
                 h_img, w_img = self.face_img.shape[:2]
                 if len(self.face_img.shape) == 2:
                     qformat = QImage.Format.Format_Grayscale8
                     bytes_per_line = w_img
                 else:
                     qformat = QImage.Format.Format_RGB888
                     bytes_per_line = w_img * 3
                 
                 qimg = QImage(self.face_img.data, w_img, h_img, bytes_per_line, qformat)
                 
                 # Draw Big in Center
                 disp_w = 400 * scale
                 disp_h = disp_w * (h_img / w_img)
                 
                 target_rect = QRectF(cx - disp_w/2, cy - disp_h/2, disp_w, disp_h)
                 painter.drawImage(target_rect, qimg)
                 
                 painter.drawText(int(cx - 50*scale), int(cy + disp_h/2 + 30), f"LUM: {self.face_lum}")
             except: pass
         else:
             painter.drawText(int(cx - 80*scale), int(cy), "NO TARGET")

    def draw_debug_cube(self, painter, w, h, scale, cx, cy):
        # 3D Cube Rotation based on Roll/Pitch/Yaw
        # Simple projection
        
        nodes = np.array(self.cube_vertices)
        
        # Scaling
        size = 100 * scale
        nodes = nodes * size
        
        # Rotation Matrices
        rad_r = self.roll # Roll affects Z rotation in screen space (view roll)
        rad_p = self.pitch * math.pi / 180.0
        rad_y = self.yaw * math.pi / 180.0
        
        # Standard Rotation Matrix (Euler)
        # Iterate nodes
        
        projected = []
        
        # Simplified rotation for visualization
        # We rotate the CUBE by the sensor values
        
        cr, sr = math.cos(rad_r), math.sin(rad_r)
        cp, sp = math.cos(rad_p), math.sin(rad_p)
        cy_a, sy_a = math.cos(rad_y), math.sin(rad_y)
        
        # Just doing Pitch/Roll for now as Yaw spins it wildly
        # Actually Yaw is Heading.
        
        for node in nodes:
            x, y, z = node
            
            # Rotate X (Pitch)
            ry = y * cr - z * sr
            rz = y * sr + z * cr
            y, z = ry, rz
            
            # Rotate Y (Yaw/Heading??) -> Usually Yaw is Rotation around global UP (Y).
            # Here we visualize sensor state.
            
            # Rotate Z (Roll from sensor? No, Sensor Roll is view rotation).
            # Let's clear this up:
            # We want to show a cube that represents the device orientation.
            # If I pitch up, the cube should pitch up.
            
            # Simple approach: Rotate points by R/P/Y
            # Rx
            dx = x
            dy = y * math.cos(rad_p) - z * math.sin(rad_p)
            dz = y * math.sin(rad_p) + z * math.cos(rad_p)
            x, y, z = dx, dy, dz
            
            # Ry (Yaw)
            # dx = x * math.cos(rad_y) + z * math.sin(rad_y)
            # dy = y
            # dz = -x * math.sin(rad_y) + z * math.cos(rad_y)
            # x, y, z = dx, dy, dz
            
            # Rz (Roll)
            dx = x * math.cos(rad_r) - y * math.sin(rad_r)
            dy = x * math.sin(rad_r) + y * math.cos(rad_r)
            dz = z
            x, y, z = dx, dy, dz
            
            projected.append((cx + x, cy + y))
            
        # Draw Edges
        for i, j in self.cube_edges:
            p1 = projected[i]
            p2 = projected[j]
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
            
        painter.drawText(int(cx - 50*scale), int(cy + 150*scale), "DEBUG CUBE")
