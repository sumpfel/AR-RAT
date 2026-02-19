import math
import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QPolygonF

class DebugWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AROS Input Debugger")
        self.setObjectName("AROS_DEBUG") # For Hyprland Rules
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint) # Try standard window
        self.resize(800, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False) # Opaque
        
        # Data
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        
        # Style
        self.color_bg = QColor(10, 10, 20)
        self.font_debug = QFont("Monospace", 14)
        
        # Cube Data (From vis_debug.py)
        # 1x1x1 unit cube vertices
        self.vertices = np.array([
            [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, -1],
            [1, -1, 1], [1, 1, 1], [-1, -1, 1], [-1, 1, 1]
        ], dtype=float)
        
        # Faces (indices) and Colors (R,G,B)
        self.faces = [
            ([0,1,2,3], (255,0,0)),   # Red
            ([3,2,7,6], (0,255,0)),   # Green
            ([6,7,5,4], (0,0,255)),   # Blue
            ([4,5,1,0], (255,255,0)), # Yellow
            ([1,5,7,2], (0,255,255)), # Cyan
            ([4,0,3,6], (255,0,255))  # Magenta
        ]

    def update_data(self, r, p, y):
        self.roll = r
        self.pitch = p
        self.yaw = y
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.color_bg)
        
        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2
        scale = 150.0 
        
        # Draw Stats
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(self.font_debug)
        painter.drawText(20, 40, f"Roll:  {self.roll:.1f}")
        painter.drawText(20, 70, f"Pitch: {self.pitch:.1f}")
        painter.drawText(20, 100, f"Yaw:   {self.yaw:.1f}")
        
        # Prepare 3D Points
        projected_points = []
        transformed_points = []
        
        # Rotation Matrices
        # Order from vis_debug.py:
        # 1. World Rotate -90 X (Y->Z, Z->-Y)
        # 2. Rotate Pitch around X
        # 3. Rotate -Yaw around Z
        # 4. Rotate -Roll around Y
        
        rad_p = np.radians(self.pitch)
        rad_y = np.radians(-self.yaw)
        rad_r = np.radians(-self.roll)
        
        # Precompute Matrices
        # Rx(theta)
        def rx(theta):
            c, s = np.cos(theta), np.sin(theta)
            return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
            
        # Ry(theta)
        def ry(theta):
            c, s = np.cos(theta), np.sin(theta)
            return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
            
        # Rz(theta)
        def rz(theta):
            c, s = np.cos(theta), np.sin(theta)
            return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

        # 1. World Rotate: X axis -90 degrees
        mat_world = rx(np.radians(-90))
        
        # 2. Object Rotation Matrices
        mat_p = rx(rad_p)
        mat_y = rz(rad_y)
        mat_r = ry(rad_r)
        
        # Combined Rotation for Object (Cube + Axes)
        mat_object = mat_r @ mat_y @ mat_p
        mat_final = mat_object @ mat_world
        
        # --- Draw Ground Grid (Fixed in World) ---
        # Grid logic from vis_debug.py:
        # Loop -10 to 10. Y is -2 (Height). 
        # But wait, vis_debug applies World Rotate (-90 X) first.
        # So Ground is in X-Z plane after rotation? 
        # vis_debug: draw_ground_grid() draws lines in (x, -2, z).
        # Then rotates -90 X.
        # So (x, -2, z) -> (x, z, 2). 
        # Wait. 
        # v' = Rx(-90) * v.
        # [1 0 0] [x]   [x]
        # [0 0 1] [-2] = [z]
        # [0 -1 0] [z]   [2]
        # So ground is at Z=2 (towards viewer? No Z is depth).
        # OpenGL Look is -Z. Camera is at -5 or -8.
        # So world is pushed back.
        
        # In logic: Draw Grid using ONLY mat_world (fixed).
        grid_lines = []
        for i in range(-10, 11, 2): # Step 2 to save perf
             # Parallel to Z
             p1 = np.array([i, -2, -10])
             p2 = np.array([i, -2, 10])
             # Parallel to X
             p3 = np.array([-10, -2, i])
             p4 = np.array([10, -2, i])
             grid_lines.extend([(p1, p2), (p3, p4)])
             
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        for p1, p2 in grid_lines:
             # Transform by World Only
             v1 = mat_world @ p1
             v2 = mat_world @ p2
             
             # Project
             # Need Z offset to move it in front of camera?
             # vis_debug uses glTranslate(0,0,-8).
             # So we add 8 to Z? Or subtract? 
             # In OpenGL -Z is forward. Positive Z is behind camera.
             # If we project: x / z.
             # Let's approximate perspective: scaling factor / (z + distance).
             # Current code uses Orthographic (just scale * x).
             # For grid to look 3D, we need perspective?
             # Let's stick to Orthographic for consistency if possible, or simple weak perspective.
             # To match "orientation", Orthographic is safer for axes.
             
             pt1 = QPointF(v1[0] * scale + cx, -v1[1] * scale + cy)
             pt2 = QPointF(v2[0] * scale + cx, -v2[1] * scale + cy)
             painter.drawLine(pt1, pt2)

        # --- Draw Axes (Rotated with Object) ---
        # Vertices for Axes
        len_axis = 2.0
        axis_pts = [
            (np.array([0,0,0]), np.array([len_axis,0,0]), QColor(255,0,0), "X"), # X Red
            (np.array([0,0,0]), np.array([0,len_axis,0]), QColor(0,255,0), "Y"), # Y Green
            (np.array([0,0,0]), np.array([0,0,len_axis]), QColor(0,0,255), "Z")  # Z Blue
        ]
        
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        
        for start, end, color, label in axis_pts:
            v_start = mat_final @ start
            v_end = mat_final @ end
            
            p1 = QPointF(v_start[0] * scale + cx, -v_start[1] * scale + cy)
            p2 = QPointF(v_end[0] * scale + cx, -v_end[1] * scale + cy)
            
            painter.setPen(QPen(color, 3))
            painter.drawLine(p1, p2)
            
            # Label
            painter.setPen(color)
            painter.drawText(p2, label)

        # --- Draw Cube (Existing Logic) ---
        for v in self.vertices:
            # Rotate
            rotated = mat_final @ v
            transformed_points.append(rotated)
            
            x = rotated[0] * scale + cx
            y = -rotated[1] * scale + cy 
            
            projected_points.append(QPointF(x, y))
            
        # Sort Faces by Depth (Painter's Algorithm)
        sorted_faces = []
        for face_indices, color_rgb in self.faces:
            z_sum = 0
            poly = QPolygonF()
            for idx in face_indices:
                z_sum += transformed_points[idx][2]
                poly.append(projected_points[idx])
            
            avg_z = z_sum / 4.0
            sorted_faces.append((avg_z, poly, color_rgb))
            
        # Draw furthest first (Smallest Z in this coord system?)
        # With -90X rotation:
        # World Z comes from Y.
        # In Viewer space: +Z is usually towards viewer?
        # Let's keep existing sort order, if it works.
        sorted_faces.sort(key=lambda x: x[0]) 
        
        for z, poly, color in sorted_faces:
             painter.setBrush(QBrush(QColor(*color)))
             painter.setPen(QPen(QColor(0,0,0), 2))
             painter.drawPolygon(poly)
