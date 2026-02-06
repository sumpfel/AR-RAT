import sys
import os
import math
import argparse
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont

# Ensure we can import from the directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import SensorFusionEngine

class HUDOverlay(QWidget):
    def __init__(self, engine, fullscreen=True):
        super().__init__()
        self.engine = engine
        
        # Window Flags for Transparency and Topmost
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool  # Tool window often helps with compositors not managing it
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) # Click through

        if fullscreen:
            self.showFullScreen()
        else:
            self.resize(1024, 768)
            self.move(100, 100)
            self.show()

        # Update Loop
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_logic)
        self.timer.start(16) # ~60 FPS

        # Fonts
        self.font_hud = QFont("Consolas", 14, QFont.Weight.Bold)
        self.font_curr = QFont("Consolas", 12)

        self.roll = 0
        self.pitch = 0
        self.yaw = 0
        self.gyro = (0, 0, 0)

    def update_logic(self):
        # Fetch latest data from engine
        self.roll, self.pitch, self.yaw, self.gyro = self.engine.update()
        self.update() # Trigger repaint call

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        hud_color = QColor(0, 255, 0)
        pen_default = QPen(hud_color, 2)
        painter.setPen(pen_default)

        # Fonts - Even Larger
        f_huge = QFont("Consolas", 26, QFont.Weight.Bold)
        f_large = QFont("Consolas", 20, QFont.Weight.Bold)
        f_med = QFont("Consolas", 16, QFont.Weight.Bold)
        f_small = QFont("Consolas", 12, QFont.Weight.Bold)
        
        painter.setFont(f_med)

        w = self.width()
        h = self.height()
        cx, cy = w // 2, h // 2

        # ---------------------------------------------------------
        # 1. Artificial Horizon & Pitch Ladder
        # ---------------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self.roll) 
        
        px_per_deg = h / 45.0
        pitch_offset = self.pitch * px_per_deg
        
        painter.translate(0, pitch_offset)
        painter.drawLine(-w, 0, w, 0) # Horizon
        
        # Pitch Ladder
        for p in range(-90, 95, 10):
            if p == 0: continue 
            
            y_pos = -p * px_per_deg 
            line_w = 200 if p % 30 == 0 else 100
            gap = 60
            
            painter.drawLine(-line_w, int(y_pos), -gap, int(y_pos))
            painter.drawLine(gap, int(y_pos), line_w, int(y_pos))
            
            if p % 30 == 0:
                painter.drawText(-line_w - 55, int(y_pos) + 10, f"{p}")
                painter.drawText(line_w + 15, int(y_pos) + 10, f"{p}")

        painter.restore()

        # ---------------------------------------------------------
        # 2. Fixed Aircraft Symbol
        # ---------------------------------------------------------
        painter.setPen(QPen(QColor(255, 255, 0), 3)) # Yellow
        size = 50
        space = 25
        
        painter.drawLine(cx - size, cy, cx - space, cy)
        painter.drawLine(cx + space, cy, cx + size, cy)
        painter.drawLine(cx, cy - space, cx, cy - size)
        painter.drawLine(cx - 5, cy, cx + 5, cy)
        painter.drawLine(cx, cy - 5, cx, cy + 5)

        # ---------------------------------------------------------
        # 3. Compass Rose (Bottom Center)
        # ---------------------------------------------------------
        compass_y = h - 120
        compass_r = 70
        
        painter.save()
        painter.translate(cx, compass_y)
        painter.setPen(QPen(hud_color, 2))
        painter.drawEllipse(-compass_r, -compass_r, compass_r*2, compass_r*2)
        
        # Heading Marker (Yellow)
        painter.setPen(QPen(QColor(255, 255, 0), 3))
        painter.drawLine(0, -compass_r - 15, 0, -compass_r + 10)
        
        # Rotate Card
        yaw_deg = math.degrees(self.yaw)
        painter.rotate(-yaw_deg) 
        
        painter.setFont(f_med)
        painter.setPen(QPen(hud_color, 2))
        
        offset = compass_r - 25
        painter.drawText(-12, -offset, "N")
        painter.drawText(offset - 12, 10, "E")
        painter.drawText(-12, offset + 10, "S")
        painter.drawText(-offset, 10, "W")
        
        for angle in range(0, 360, 45):
            painter.save()
            painter.rotate(angle)
            painter.drawLine(0, -compass_r, 0, -compass_r + 10)
            painter.restore()
        painter.restore()

        # ---------------------------------------------------------
        # 4. Heading Tape (Top Center)
        # ---------------------------------------------------------
        # "lines going left and right at the mag output on top of screen"
        painter.setPen(pen_default)
        painter.setFont(f_med)
        
        tape_y = 60
        tape_width = 400
        px_per_deg_h = 4.0 # 4 pixels per degree heading
        
        # Center Triangle Marker
        painter.setPen(QPen(QColor(255, 255, 0), 3))
        painter.drawLine(cx, tape_y + 20, cx - 10, tape_y + 35) # Triangle Left
        painter.drawLine(cx, tape_y + 20, cx + 10, tape_y + 35) # Triangle Right
        painter.drawLine(cx - 10, tape_y + 35, cx + 10, tape_y + 35) # Base
        
        # Current Value Text
        painter.setFont(f_huge)
        hdg_val = int(yaw_deg) % 360
        painter.setPen(QPen(hud_color, 2))
        painter.drawText(cx - 40, tape_y + 80, f"{hdg_val:03d}")
        
        # Tape Tick Marks
        # Iterate visible range: Center +/- 50 degrees
        # We clamp loop to logical integers
        
        center_deg = yaw_deg
        
        painter.setPen(QPen(hud_color, 2))
        painter.setFont(f_small)
        
        # Draw Background Line
        painter.drawLine(cx - tape_width//2, tape_y, cx + tape_width//2, tape_y)
        
        min_deg = int(center_deg) - 60
        max_deg = int(center_deg) + 60
        
        # Clip area for tape (Optional, but Qt draws cleanly anyway)
        
        for d in range(min_deg, max_deg):
            if d % 5 != 0: continue
            
            # X Offset from center
            # if d > center, it is to the RIGHT.
            # pos = cx + (d - center) * scale
            x_pos = cx + (d - center_deg) * px_per_deg_h
            
            if x_pos < cx - tape_width//2 or x_pos > cx + tape_width//2:
                continue
            
            is_major = (d % 10 == 0)
            tick_h = 15 if is_major else 8
            
            painter.drawLine(int(x_pos), tape_y, int(x_pos), tape_y - tick_h)
            
            if is_major:
                # Normalize 0-360 for label
                label_val = d % 360
                label_str = f"{label_val:03d}"
                # N/E/S/W labels?
                if label_val == 0: label_str = "N"
                elif label_val == 90: label_str = "E"
                elif label_val == 180: label_str = "S"
                elif label_val == 270: label_str = "W"
                
                painter.drawText(int(x_pos) - 15, tape_y - 20, label_str)

        # ---------------------------------------------------------
        # 5. Numeric Overlays (Left Side)
        # ---------------------------------------------------------
        painter.setPen(pen_default)
        painter.setFont(f_large)
        
        left_margin = 40
        start_y = h - 300
        lh = 50
        
        painter.drawText(left_margin, start_y,      f"PIT {self.pitch:.1f}")
        painter.drawText(left_margin, start_y + lh, f"ROL {self.roll:.1f}")
        painter.drawText(left_margin, start_y + lh*2, f"YAW {hdg_val:03d}")

        # ---------------------------------------------------------
        # 6. Rates (Bottom Right)
        # ---------------------------------------------------------
        gx, gy, gz = self.gyro
        painter.setFont(f_med)
        painter.setPen(QPen(hud_color, 1))
        
        right_margin = w - 300
        bottom_y = h - 120
        lh_r = 40
        
        painter.drawText(right_margin, bottom_y,        f"Gyr X: {gx:5.1f}")
        painter.drawText(right_margin, bottom_y + lh_r, f"Gyr Y: {gy:5.1f}")
        painter.drawText(right_margin, bottom_y + lh_r*2, f"Gyr Z: {gz:5.1f}")
        
        # Hint
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        painter.setFont(QFont("Arial", 12))
        painter.drawText(right_margin, 40, "HUD | Ctrl+C")

        painter.end()

def main():
    parser = argparse.ArgumentParser(description="Qt Fighter Jet HUD")
    parser.add_argument('--windowed', action='store_true', help='Run in windowed mode')
    parser.add_argument('--use-gyro', action='store_true')
    parser.add_argument('--use-magnetometer', action='store_true')
    args = parser.parse_args()

    # Init Engine
    engine = SensorFusionEngine(
        use_gyro=args.use_gyro,
        use_magnetometer=args.use_magnetometer,
        relative_yaw=False
    )
    
    # Init Qt App
    app = QApplication(sys.argv)
    
    fullscreen = not args.windowed
    hud = HUDOverlay(engine, fullscreen=fullscreen)
    
    # We need to ensure Ctrl+C works in terminal
    # Qt blocks python signals by default. Let's add a timer to process signals or just rely on OS kill.
    # Actually Python handles it if we run the updates.
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
