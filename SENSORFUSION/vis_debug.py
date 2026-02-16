import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math

class DebugVisualizer:
    def __init__(self, width=800, height=600):
        pygame.init()
        self.display = (width, height)
        pygame.display.set_caption("Sensor Fusion Debug - 3D Cube")
        self.screen = pygame.display.set_mode(self.display, DOUBLEBUF | OPENGL | RESIZABLE)

        glEnable(GL_DEPTH_TEST) 
        glMatrixMode(GL_PROJECTION)
        gluPerspective(45, (self.display[0]/self.display[1]), 0.1, 50.0)
        glMatrixMode(GL_MODELVIEW)
        glTranslatef(0.0, 0.0, -5)

    def draw_cube(self):
        glBegin(GL_LINES)
        
        # Edges
        vertices = [
            (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, -1),
            (1, -1, 1), (1, 1, 1), (-1, -1, 1), (-1, 1, 1)
        ]
        
        edges = (
            (0,1), (0,3), (0,4), (2,1), (2,3), (2,7), (6,3), (6,4), (6,7), (5,1), (5,4), (5,7)
        )
        
        glColor3f(1, 1, 1) # White Lines
        for edge in edges:
            for vertex in edge:
                glVertex3fv(vertices[vertex])
        glEnd()
        
        # Faces (Semi-transparent)
        # Faces (Solid Colors for Orientation)
        glBegin(GL_QUADS)
        
        faces = (
            (0,1,2,3), (3,2,7,6), (6,7,5,4), (4,5,1,0), (1,5,7,2), (4,0,3,6)
        )
        colors = (
            (1,0,0), # Red (Front)
            (0,1,0), # Green (Back)
            (0,0,1), # Blue (Right)
            (1,1,0), # Yellow (Left)
            (0,1,1), # Cyan (Top)
            (1,0,1)  # Magenta (Bottom)
        )
        
        for i, face in enumerate(faces):
            glColor3fv(colors[i])
            for vertex in face:
                glVertex3fv(vertices[vertex])
        glEnd()

    def draw_letter(self, char, x, y, z, scale=0.5):
        glPushMatrix()
        glTranslatef(x, y, z)
        glScalef(scale, scale, scale)
        glBegin(GL_LINES)
        if char == 'X':
            glVertex3f(0, 0, 0); glVertex3f(0, 1, 0) # Up? No, X is crossed
            # Draw X on Z-plane? Or billboards? Just 3D lines
            # A 2D X in 3D space
            glVertex3f(0,0,0); glVertex3f(1,1,0)
            glVertex3f(0,1,0); glVertex3f(1,0,0)
        elif char == 'Y':
            glVertex3f(0,1,0); glVertex3f(0.5,0.5,0)
            glVertex3f(1,1,0); glVertex3f(0.5,0.5,0)
            glVertex3f(0.5,0.5,0); glVertex3f(0.5,0,0)
        elif char == 'Z':
            glVertex3f(0,1,0); glVertex3f(1,1,0)
            glVertex3f(1,1,0); glVertex3f(0,0,0)
            glVertex3f(0,0,0); glVertex3f(1,0,0)
        glEnd()
        glPopMatrix()

    def draw_axes(self):
        glLineWidth(3)
        glBegin(GL_LINES)
        
        # X Axis - Red
        glColor3f(1, 0, 0)
        glVertex3f(0, 0, 0); glVertex3f(2, 0, 0)
        
        # Y Axis - Green
        glColor3f(0, 1, 0)
        glVertex3f(0, 0, 0); glVertex3f(0, 2, 0)
        
        # Z Axis - Blue
        glColor3f(0, 0, 1)
        glVertex3f(0, 0, 0); glVertex3f(0, 0, 2)
        
        glEnd()
        
        # Draw Labels
        glColor3f(1, 0, 0) # Red X
        self.draw_letter('X', 2.2, 0, 0)
        
        glColor3f(0, 1, 0) # Green Y
        self.draw_letter('Y', 0, 2.2, 0)
        
        glColor3f(0, 0, 1) # Blue Z
        self.draw_letter('Z', 0, 0, 2.2)

    def draw_ground_grid(self):
        glColor3f(0.3, 0.3, 0.3)
        glLineWidth(1)
        glBegin(GL_LINES)
        for i in range(-10, 11):
            glVertex3f(i, -2, -10); glVertex3f(i, -2, 10)
            glVertex3f(-10, -2, i); glVertex3f(10, -2, i)
        glEnd()

    def update(self, roll, pitch, yaw, gyro_v=None, active_targets=0, face_img=None, face_lum=0):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return False
            if event.type == pygame.VIDEORESIZE:
                glViewport(0, 0, event.w, event.h)
                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                gluPerspective(45, (event.w/event.h), 0.1, 50.0)
                glMatrixMode(GL_MODELVIEW)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(0.0, 0.0, -8) # Move back camera
        
        # Rotate World to be Z-Up (User Preference)
        # Originally Y is Up. Rotate -90 around X brings Y to Z.
        glRotatef(-90, 1, 0, 0)
        
        # Draw Ground Fixed
        self.draw_ground_grid()
        
        # Apply Rotation for Object
        # New Z-Up Frame:
        # Z is Up (Blue)
        # X is Right (Red)
        # Y is Forward (Green)
        
        # Rotations:
        # Heading (Yaw) -> Around Z (Up)
        # Pitch -> Around X (Right)
        # Roll -> Around Y (Forward)
        
        glRotatef(pitch, 1, 0, 0) # Pitch around X (Right)
        glRotatef(-yaw, 0, 0, 1)  # Yaw around Z (Up)
        glRotatef(-roll, 0, 1, 0)  # Roll around Y (Forward)
        
        self.draw_axes()
        self.draw_cube()
        
        pygame.display.flip()
        return True
