import pygame
from pygame.locals import *
import math
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import cv2

class Visualizer:
    def __init__(self, width=1024, height=768, fullscreen=False, bg_color=(0, 0, 0, 0)):
        pygame.init()
        # pygame.font.init() # DISABLED because broken in environment
        
        # Request Alpha Channel for transparency
        pygame.display.gl_set_attribute(pygame.GL_ALPHA_SIZE, 8)
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 16)
        pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)

        flags = DOUBLEBUF | OPENGL | RESIZABLE # Add RESIZABLE
        if fullscreen:
            flags |= FULLSCREEN
            self.display = (0, 0) # Auto monitor res
        else:
            if bg_color[3] == 0: # If transparent requested
                 flags |= NOFRAME # often req for transparency, but conflicts with resize borders?
                 # User wants resizable AND transparent. Typically contradictory in some WMs.
                 # Let's keep NOFRAME if they really want transparency, but RESIZABLE might just allow maximizing?
                 # Actually, user said "change size of window".
                 # If NOFRAME, you can't resize with mouse.
                 # If I remove NOFRAME, transparency might break on some compositors.
                 # I'll enable RESIZABLE. If they conflict, user has to choose.
                 # But standard pygame transparency often requires specific flags.
                 # Let's try adding RESIZABLE and keeping NOFRAME (users can sometimes resize via Alt+RightClick).
                 pass
            self.display = (width, height)
            
        pygame.display.set_caption("Sensor Fusion HUD - Fighter Jet Mode")
        screen = pygame.display.set_mode(self.display, flags)
        
        self.bg_color = bg_color
        
        # Determine FOV
        w, h = screen.get_size()
        self.display = (w, h)
        self.fov = 45
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(self.fov, (w/h), 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        self.face_texture_id = None


    # --- VECTOR FONT IMPLEMENTATION (Complete A-Z, 0-9) ---
    def draw_char(self, char, x, y, scale=1.0):
        """Draws a character using GL_LINES at (x,y) with given scale"""
        glPushMatrix()
        glTranslatef(x, y, 0)
        glScalef(scale, scale, 1)
        
        # Char dims: 10x16 approx.
        glBegin(GL_LINES)
        
        c = char.upper()
        
        # NUMBERS
        if c in '0123456789':
            if c in '02356789': chmod = 1 # Top
            else: chmod=0
            if c in '02356789': glVertex2f(0, 16); glVertex2f(10, 16)
            
            if c in '045689': glVertex2f(0, 8); glVertex2f(0, 16) # Top Left
            if c in '01234789': glVertex2f(10, 8); glVertex2f(10, 16) # Top Right
            if c in '2345689': glVertex2f(0, 8); glVertex2f(10, 8) # Middle
            if c in '0268': glVertex2f(0, 0); glVertex2f(0, 8) # Bottom Left
            if c in '013456789': glVertex2f(10, 0); glVertex2f(10, 8) # Bottom Right
            if c in '0235689': glVertex2f(0, 0); glVertex2f(10, 0) # Bottom
            
        # LETTERS
        elif c == 'A':
            glVertex2f(0,0); glVertex2f(0,12); glVertex2f(0,12); glVertex2f(5,16)
            glVertex2f(5,16); glVertex2f(10,12); glVertex2f(10,12); glVertex2f(10,0)
            glVertex2f(0,8); glVertex2f(10,8)
        elif c == 'B': # P + loop
            glVertex2f(0,0); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(8,16)
            glVertex2f(8,16); glVertex2f(10,12); glVertex2f(10,12); glVertex2f(8,8)
            glVertex2f(8,8); glVertex2f(0,8); glVertex2f(8,8); glVertex2f(10,4)
            glVertex2f(10,4); glVertex2f(8,0); glVertex2f(8,0); glVertex2f(0,0)
        elif c == 'C':
            glVertex2f(10,16); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(0,0)
            glVertex2f(0,0); glVertex2f(10,0)
        elif c == 'D':
            glVertex2f(0,0); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(6,16)
            glVertex2f(6,16); glVertex2f(10,12); glVertex2f(10,12); glVertex2f(10,4)
            glVertex2f(10,4); glVertex2f(6,0); glVertex2f(6,0); glVertex2f(0,0)
        elif c == 'E':
            glVertex2f(10,16); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(0,0)
            glVertex2f(0,0); glVertex2f(10,0); glVertex2f(0,8); glVertex2f(8,8)
        elif c == 'F':
            glVertex2f(10,16); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(0,0)
            glVertex2f(0,8); glVertex2f(8,8)
        elif c == 'G':
            glVertex2f(10,16); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(0,0)
            glVertex2f(0,0); glVertex2f(10,0); glVertex2f(10,0); glVertex2f(10,8)
            glVertex2f(10,8); glVertex2f(5,8)
        elif c == 'H':
            glVertex2f(0,0); glVertex2f(0,16); glVertex2f(10,0); glVertex2f(10,16)
            glVertex2f(0,8); glVertex2f(10,8)
        elif c == 'I':
            glVertex2f(5,0); glVertex2f(5,16); glVertex2f(0,0); glVertex2f(10,0)
            glVertex2f(0,16); glVertex2f(10,16)
        elif c == 'J':
            glVertex2f(10,16); glVertex2f(10,0); glVertex2f(10,0); glVertex2f(0,0)
            glVertex2f(0,0); glVertex2f(0,6)
        elif c == 'K':
            glVertex2f(0,0); glVertex2f(0,16); glVertex2f(10,16); glVertex2f(0,8)
            glVertex2f(0,8); glVertex2f(10,0)
        elif c == 'L':
            glVertex2f(0,16); glVertex2f(0,0); glVertex2f(0,0); glVertex2f(10,0)
        elif c == 'M':
            glVertex2f(0,0); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(5,8)
            glVertex2f(5,8); glVertex2f(10,16); glVertex2f(10,16); glVertex2f(10,0)
        elif c == 'N':
            glVertex2f(0,0); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(10,0)
            glVertex2f(10,0); glVertex2f(10,16)
        elif c == 'O':
            glVertex2f(0,0); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(10,16)
            glVertex2f(10,16); glVertex2f(10,0); glVertex2f(10,0); glVertex2f(0,0)
        elif c == 'P':
            glVertex2f(0,0); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(10,16)
            glVertex2f(10,16); glVertex2f(10,8); glVertex2f(10,8); glVertex2f(0,8)
        elif c == 'Q': # O with tail
            glVertex2f(0,0); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(10,16)
            glVertex2f(10,16); glVertex2f(10,0); glVertex2f(10,0); glVertex2f(0,0)
            glVertex2f(5,5); glVertex2f(10,-3)
        elif c == 'R':
            glVertex2f(0,0); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(10,16)
            glVertex2f(10,16); glVertex2f(10,8); glVertex2f(10,8); glVertex2f(0,8)
            glVertex2f(0,8); glVertex2f(10,0)
        elif c == 'S':
            glVertex2f(10,16); glVertex2f(0,16); glVertex2f(0,16); glVertex2f(0,8)
            glVertex2f(0,8); glVertex2f(10,8); glVertex2f(10,8); glVertex2f(10,0)
            glVertex2f(10,0); glVertex2f(0,0)
        elif c == 'T':
            glVertex2f(5,0); glVertex2f(5,16); glVertex2f(0,16); glVertex2f(10,16)
        elif c == 'U':
            glVertex2f(0,16); glVertex2f(0,0); glVertex2f(0,0); glVertex2f(10,0)
            glVertex2f(10,0); glVertex2f(10,16)
        elif c == 'V':
            glVertex2f(0,16); glVertex2f(5,0); glVertex2f(5,0); glVertex2f(10,16)
        elif c == 'W':
            glVertex2f(0,16); glVertex2f(0,0); glVertex2f(0,0); glVertex2f(5,8)
            glVertex2f(5,8); glVertex2f(10,0); glVertex2f(10,0); glVertex2f(10,16)
        elif c == 'X':
            glVertex2f(0,0); glVertex2f(10,16); glVertex2f(0,16); glVertex2f(10,0)
        elif c == 'Y':
            glVertex2f(0,16); glVertex2f(5,8); glVertex2f(10,16); glVertex2f(5,8)
            glVertex2f(5,8); glVertex2f(5,0)
        elif c == 'Z':
            glVertex2f(0,16); glVertex2f(10,16); glVertex2f(10,16); glVertex2f(0,0)
            glVertex2f(0,0); glVertex2f(10,0)
        elif c == '-':
            glVertex2f(0, 8); glVertex2f(10, 8)
        elif c == ':':
            glVertex2f(5, 10); glVertex2f(5, 12); glVertex2f(5, 4); glVertex2f(5, 6)
        
        glEnd()
        glPopMatrix()
        return 14 # Advance width

    def draw_string(self, text, x, y, scale=1.0, color=(0, 1, 0), center=False):
        """Draws a string using vector font"""
        glColor3fv(color)
        
        if center:
             # Calculate width
             total_width = 0
             for char in text:
                 if char == ' ':
                     total_width += 10 * scale
                 else:
                     total_width += 14 * scale # Assuming 14 is the advance width for chars
             x -= total_width / 2
        
        current_x = x
        for char in text:
            if char == ' ':
                current_x += 10 * scale
            else:
                current_x += self.draw_char(char.upper(), current_x, y, scale) * scale

    def draw_text(self, text, x, y, scale=1.0, color=(1,1,1), center=False):
        # Alias for draw_string
        self.draw_string(text, x, y, scale, color, center)

    def draw_text_3d(self, text, x, y, z, scale=1.0, color=(0.2, 1.0, 0.2)):
         """Draws 3D text in world space using vector font"""
         glPushMatrix()
         glTranslatef(x, y, z)
         glScalef(scale, scale, 1)
         
         glColor3fv(color)
         
         # Calc width for centering
         width = 0
         for char in text:
             if char == ' ':
                 width += 10
             else:
                 width += 14
         
         current_x = -width / 2 # Start drawing from here to center
         
         for char in text:
             if char == ' ':
                 current_x += 10
             else:
                 current_x += self.draw_char(char.upper(), current_x, 0, 1.0) # 1.0 because glScalef already applied
         glPopMatrix()


    def update_face_texture(self, face_img):
        if face_img is None: return

        if self.face_texture_id is None:
            self.face_texture_id = glGenTextures(1)
        
        # Convert BGR/Gray to RGB/RGBA if needed, but we expect Grayscale or processed
        # Assuming face_img is numpy array (H, W) or (H, W, 3)
        
        h, w = face_img.shape[:2]
        if len(face_img.shape) == 2:
            mode = GL_LUMINANCE
        else:
            mode = GL_RGB
            # If BGR from OpenCV, convert to RGB
            face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)

        glBindTexture(GL_TEXTURE_2D, self.face_texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, mode, w, h, 0, mode, GL_UNSIGNED_BYTE, face_img)


    def draw_hud_symbology(self, roll, pitch, yaw):
        """Draws the 3D HUD elements (Horizon, Pitch Ladder)"""
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        # Apply Frame Rotation to simulate FPV
        glRotatef(-roll, 0, 0, 1)
        glRotatef(-pitch, 1, 0, 0)
        
        # --- DRAW HORIZON ---
        glLineWidth(2)
        glBegin(GL_LINES)
        glColor3f(0.2, 1.0, 0.2) # Bright Green
        glVertex3f(-20, 0, -10) 
        glVertex3f(20, 0, -10)
        glEnd()

        # --- DRAW PITCH LADDER ---
        for p in range(-90, 95, 10):
            if p == 0: continue
            
            glPushMatrix()
            glRotatef(p, 1, 0, 0)
            
            w = 2.0 if p % 30 == 0 else 1.0
            gap = 0.5
            
            glColor3f(0.2, 1.0, 0.2)
            
            glBegin(GL_LINES)
            glVertex3f(-w, 0, -10)
            glVertex3f(-gap, 0, -10)
            
            glVertex3f(gap, 0, -10)
            glVertex3f(w, 0, -10)
            
            if p % 30 == 0:
                tick = 0.2
                s = -1 if p > 0 else 1 
                glVertex3f(-w, 0, -10) 
                glVertex3f(-w, s*tick, -10) 
                
                glVertex3f(w, 0, -10)
                glVertex3f(w, s*tick, -10)
            glEnd()
            
            # --- NUMERIC LABELS FOR PITCH ---
            self.draw_text_3d(f"{p}", w + 0.5, 0, -10, scale=0.02, color=(0.2, 1.0, 0.2))
            self.draw_text_3d(f"{p}", -w - 0.5, 0, -10, scale=0.02, color=(0.2, 1.0, 0.2))

            glPopMatrix()



        glPopMatrix()



    def draw_compass_circle(self, cx, cy, radius, yaw):
        glLineWidth(2)
        glColor3f(0.2, 1.0, 0.2)
        
        glPushMatrix()
        glTranslatef(cx, cy, 0)
        
        # Static Ring
        glBegin(GL_LINE_LOOP)
        for i in range(0, 360, 10):
            rad = math.radians(i)
            glVertex2f(math.cos(rad)*radius, math.sin(rad)*radius)
        glEnd()
        
        # N/E/S/W Labels (Rotating)
        # If I face North (Yaw 0), N should be at Top (90 deg vis).
        # Vis Angle = 90 - Yaw + Offset.
        
        for angle, label in [(0, 'N'), (90, 'E'), (180, 'S'), (270, 'W')]:
             vis_angle = math.radians(90 - yaw + angle)
             lx = math.cos(vis_angle) * (radius - 15)
             ly = math.sin(vis_angle) * (radius - 15)
             
             # Center text
             self.draw_string(label, lx, ly, scale=1.0, color=(0.2, 1.0, 0.2), center=True)

        # Fixed Needle at Top (Triangle pointing UP)
        glColor3f(1.0, 0.0, 0.0)
        glBegin(GL_TRIANGLES)
        glVertex2f(0, radius + 10)
        glVertex2f(-5, radius)
        glVertex2f(5, radius)
        glEnd()

        glPopMatrix()

    def draw_target_info(self, active_targets, face_texture_id, face_lum=0):
        w, h = self.display
        panel_x = w - 250
        panel_y = h // 2
        
        # Labels Green
        self.draw_string(f"TARGETS: {active_targets}", panel_x, panel_y + 110, scale=1.0, color=(0.2, 1.0, 0.2))
        
        if face_texture_id:
             self.draw_string("CURRENT TARGET", panel_x, panel_y + 80, scale=0.8, color=(0.2, 1.0, 0.2))
             
             
             glEnable(GL_TEXTURE_2D)
             glBindTexture(GL_TEXTURE_2D, face_texture_id)
             glColor3f(0, 1, 0) # Green Tint Requested
             
             fw, fh = 200, 200
             fy = panel_y - 120
             
             glBegin(GL_QUADS)
             glTexCoord2f(0, 1); glVertex2f(panel_x, fy)
             glTexCoord2f(1, 1); glVertex2f(panel_x + fw, fy)
             glTexCoord2f(1, 0); glVertex2f(panel_x + fw, fy + fh)
             glTexCoord2f(0, 0); glVertex2f(panel_x, fy + fh)
             glEnd()
             
             glDisable(GL_TEXTURE_2D)
             
             # Green Frame
             glColor3f(0.2, 1.0, 0.2)
             glLineWidth(2)
             glBegin(GL_LINE_LOOP)
             glVertex2f(panel_x, fy)
             glVertex2f(panel_x + fw, fy)
             glVertex2f(panel_x + fw, fy + fh)
             glVertex2f(panel_x, fy + fh)
             glEnd()
             
             # Draw Luminance Indicator below image
             # face_lum is 0-255. Map to %.
             lum_pct = int((face_lum / 255.0) * 100)
             self.draw_string(f"LUM: {lum_pct}%", panel_x, fy - 20, scale=0.8, color=(0.2, 1.0, 0.2))



    def draw_overlays(self, roll, pitch, yaw, gyro_v, active_targets, face_lum=0):
        """Draws 2D elements like numbers and static symbols"""
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, self.display[0], 0, self.display[1])
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        # --- FIXED AIRCRAFT SYMBOL ---
        cx, cy = self.display[0]//2, self.display[1]//2
        size = 30
        space = 15
        
        glLineWidth(3)
        glColor3f(1.0, 1.0, 0.0) # Yellow
        glBegin(GL_LINES)
        glVertex2f(cx - size, cy); glVertex2f(cx - space, cy)
        glVertex2f(cx + space, cy); glVertex2f(cx + size, cy)
        glVertex2f(cx, cy + space); glVertex2f(cx, cy + space + 10)
        glVertex2f(cx - 5, cy); glVertex2f(cx + 5, cy)
        glVertex2f(cx, cy - 5); glVertex2f(cx, cy + 5)
        glEnd()
        
        # --- NEW LAYOUT ---
        w, h = self.display
        
        # 1. R/P/Y (Bottom Left) - BIGGER
        # x=20, y=80..
        self.draw_string(f"ROLL  {int(roll)}", 20, 100, scale=1.0, color=(0.2, 1.0, 0.2))
        self.draw_string(f"PITCH {int(pitch)}", 20, 60, scale=1.0, color=(0.2, 1.0, 0.2))
        self.draw_string(f"YAW   {int(yaw)%360}", 20, 20, scale=1.0, color=(0.2, 1.0, 0.2))
        
        # 2. Rate (Bottom Right)
        # 200 px from right
        xr = w - 240
        if gyro_v is not None:
             gx, gy, gz = gyro_v
             self.draw_string(f"RATE X {gx:>5.2f}", xr, 100, scale=1.0, color=(0.2, 1.0, 0.2))
             self.draw_string(f"RATE Y {gy:>5.2f}", xr, 60, scale=1.0, color=(0.2, 1.0, 0.2))
             self.draw_string(f"RATE Z {gz:>5.2f}", xr, 20, scale=1.0, color=(0.2, 1.0, 0.2))

        # 3. Targets (Right Middle)
        self.draw_target_info(active_targets, self.face_texture_id, face_lum)
        
        # 4. Top Compass (Top Left)
        self.draw_compass_circle(80, h - 100, 60, yaw)
        
        # 5. Heading Tape (Top Center)
        # "flip it so number and label are above the line and numbers and the moving lines are below it"
        # "also include a little bit more space before window border"
        
        center_x = w // 2
        top_y = h - 60 # Shift down by 60
        tape_width = 400
        fov_deg = 60
        
        # HDG Label and Value ABOVE the line
        # Current Value Box
        hdg_val = int(yaw) % 360
        self.draw_string(f"HDG {hdg_val:03d}", center_x, top_y + 25, scale=1.2, color=(0.2, 1.0, 0.2), center=True)
        
        # Center Marker (Triangle pointing down to line)
        glLineWidth(2)
        glColor3f(0.2, 1.0, 0.2)
        glBegin(GL_TRIANGLES)
        glVertex2f(center_x, top_y + 10); glVertex2f(center_x-5, top_y+20); glVertex2f(center_x+5, top_y+20)
        glEnd()
        
        # The Line
        glBegin(GL_LINES)
        glVertex2f(center_x - tape_width/2, top_y)
        glVertex2f(center_x + tape_width/2, top_y)
        glEnd()
        
        # Ticks BELOW the line
        start_deg = int(yaw) - 40
        end_deg = int(yaw) + 40
        
        for d in range(start_deg, end_deg):
            if d % 5 == 0:
                delta = d - yaw
                x_pos = center_x + (delta * (tape_width / fov_deg))
                
                h_tick = 15 if d % 10 == 0 else 8
                
                if center_x - tape_width/2 < x_pos < center_x + tape_width/2:
                     glBegin(GL_LINES)
                     glVertex2f(x_pos, top_y)          # Line y
                     glVertex2f(x_pos, top_y - h_tick) # Downward tick
                     glEnd()
                     
                     if d % 10 == 0:
                         lbl_val = d % 360
                         if lbl_val < 0: lbl_val += 360
                         # Draw Text BELOW ticks
                         self.draw_string(str(lbl_val), x_pos, top_y - 35, scale=0.8, color=(0.2, 1.0, 0.2), center=True)



        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    def update(self, roll, pitch, yaw, gyro_v=None, active_targets=0, face_img=None, face_lum=0):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False
            elif event.type == pygame.VIDEORESIZE:
                self.display = event.size
                pygame.display.set_mode(self.display, DOUBLEBUF | OPENGL | RESIZABLE) # Recreate window? Or just viewport
                glViewport(0, 0, event.w, event.h)
                
                # Update Projection for 3D
                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                gluPerspective(self.fov, (event.w/event.h), 0.1, 100.0)
                glMatrixMode(GL_MODELVIEW)
                
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return False
                if event.key == pygame.K_s:
                    try:
                        pygame.image.save(pygame.display.get_surface(), "hud_screenshot.png")
                        print("Screenshot saved to hud_screenshot.png")
                    except Exception:
                        pass
        
        r, g, b, a = self.bg_color
        glClearColor(r, g, b, a)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        if face_img is not None:
             self.update_face_texture(face_img)

        self.draw_hud_symbology(roll, pitch, yaw)
        self.draw_overlays(roll, pitch, yaw, gyro_v, active_targets, face_lum)
        
        pygame.display.flip()
        return True
