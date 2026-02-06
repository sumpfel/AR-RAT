import pygame
from pygame.locals import *
import math
from OpenGL.GL import *
from OpenGL.GLU import *

class Visualizer:
    def __init__(self, width=1024, height=768, fullscreen=False, bg_color=(0, 0, 0, 0)):
        pygame.init()
        # pygame.font.init() # DISABLED
        
        # Request Alpha Channel for transparency
        pygame.display.gl_set_attribute(pygame.GL_ALPHA_SIZE, 8)
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 16)
        pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)

        flags = DOUBLEBUF | OPENGL
        if fullscreen:
            flags |= FULLSCREEN
            self.display = (0, 0) # Auto monitor res
        else:
            if bg_color[3] == 0: # If transparent requested
                 flags |= NOFRAME # Often required for transparency
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


    # --- VECTOR FONT IMPLEMENTATION ---
    def draw_char(self, char, x, y, scale=1.0):
        """Draws a character using GL_LINES at (x,y) with given scale"""
        glPushMatrix()
        glTranslatef(x, y, 0)
        glScalef(scale, scale, 1)
        
        # Char width approx 10, height 16
        # Coordinates relative to bottom-left of char
        
        glBegin(GL_LINES)
        
        if char in '0123456789':
            # 0
            if char in '02356789': # Top
                glVertex2f(0, 16); glVertex2f(10, 16)
            if char in '045689': # Top Left
                glVertex2f(0, 8); glVertex2f(0, 16)
            if char in '01234789': # Top Right
                glVertex2f(10, 8); glVertex2f(10, 16)
            if char in '2345689': # Middle
                glVertex2f(0, 8); glVertex2f(10, 8)
            if char in '0268': # Bottom Left
                glVertex2f(0, 0); glVertex2f(0, 8)
            if char in '013456789': # Bottom Right
                glVertex2f(10, 0); glVertex2f(10, 8)
            if char in '0235689': # Bottom
                glVertex2f(0, 0); glVertex2f(10, 0)
                
        elif char == 'P':
            glVertex2f(0, 0); glVertex2f(0, 16) # Left
            glVertex2f(0, 16); glVertex2f(10, 16) # Top
            glVertex2f(10, 16); glVertex2f(10, 8) # Right
            glVertex2f(10, 8); glVertex2f(0, 8) # Middle
        elif char == 'R':
            glVertex2f(0, 0); glVertex2f(0, 16) # Left
            glVertex2f(0, 16); glVertex2f(10, 16) # Top
            glVertex2f(10, 16); glVertex2f(10, 8) # Right
            glVertex2f(10, 8); glVertex2f(0, 8) # Middle
            glVertex2f(0, 8); glVertex2f(10, 0) # Diagonal
        elif char == 'L':
            glVertex2f(0, 0); glVertex2f(0, 16) # Left
            glVertex2f(0, 0); glVertex2f(10, 0) # Bottom
        elif char == 'H':
            glVertex2f(0, 0); glVertex2f(0, 16) # Left
            glVertex2f(10, 0); glVertex2f(10, 16) # Right
            glVertex2f(0, 8); glVertex2f(10, 8) # Middle
        elif char == 'D':
            glVertex2f(0, 0); glVertex2f(0, 16) # Left
            glVertex2f(0, 16); glVertex2f(8, 16) # Top
            glVertex2f(8, 16); glVertex2f(10, 14) # Corner TR
            glVertex2f(10, 14); glVertex2f(10, 2) # Right
            glVertex2f(10, 2); glVertex2f(8, 0) # Corner BR
            glVertex2f(8, 0); glVertex2f(0, 0) # Bottom
        elif char == 'G':
            glVertex2f(10, 16); glVertex2f(0, 16) # Top
            glVertex2f(0, 16); glVertex2f(0, 0) # Left
            glVertex2f(0, 0); glVertex2f(10, 0) # Bottom
            glVertex2f(10, 0); glVertex2f(10, 8) # Right Lower
            glVertex2f(10, 8); glVertex2f(5, 8) # Middle In
        elif char == '-':
            glVertex2f(0, 8); glVertex2f(10, 8)
        
        glEnd()
        glPopMatrix()
        return 14 # Advance width

    def draw_string(self, text, x, y, scale=1.0, color=(0, 1, 0)):
        glColor3fv(color)
        current_x = x
        for char in text:
            if char == ' ':
                current_x += 10 * scale
            else:
                current_x += self.draw_char(char.upper(), current_x, y, scale) * scale

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
            glPopMatrix()

        glPopMatrix()

    def draw_overlays(self, roll, pitch, yaw):
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
        
        # --- VECTOR TEXT INFO ---
        # Scale 1.5 for Text
        s = 1.5
        
        # HDG
        heading_val = int(yaw) % 360
        self.draw_string(f"HDG {heading_val:03d}", cx - 60, self.display[1] - 50, scale=s)
        
        # Pitch/Roll
        self.draw_string(f"P {int(pitch)}", 20, self.display[1] - 100, scale=s)
        self.draw_string(f"R {int(roll)}", 20, self.display[1] - 130, scale=s)

        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    def update(self, roll, pitch, yaw):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False
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
        
        self.draw_hud_symbology(roll, pitch, yaw)
        self.draw_overlays(roll, pitch, yaw)
        
        pygame.display.flip()
        return True
