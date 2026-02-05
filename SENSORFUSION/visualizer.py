import pygame
from pygame.locals import *
import math
from OpenGL.GL import *
from OpenGL.GLU import *

class Visualizer:
    def __init__(self, width=800, height=600):
        pygame.init()
        self.display = (width, height)
        pygame.display.set_caption("Sensor Fusion Debug")
        pygame.display.set_mode(self.display, DOUBLEBUF | OPENGL)
        
        gluPerspective(45, (self.display[0]/self.display[1]), 0.1, 50.0)
        glTranslatef(0.0, 0.0, -5)
        
        # Cube vertices
        self.vertices = (
            (1, -1, -1),
            (1, 1, -1),
            (-1, 1, -1),
            (-1, -1, -1),
            (1, -1, 1),
            (1, 1, 1),
            (-1, -1, 1),
            (-1, 1, 1)
        )
        
        self.edges = (
            (0,1), (0,3), (0,4),
            (2,1), (2,3), (2,7),
            (6,3), (6,4), (6,7),
            (5,1), (5,4), (5,7)
        )
        
        self.surfaces = (
            (0,1,2,3),
            (3,2,7,6),
            (6,7,5,4),
            (4,5,1,0),
            (1,5,7,2),
            (4,0,3,6)
        )
        
        # Colors for faces
        self.colors = (
            (1,0,0), (0,1,0), (0,0,1), (1,1,0), (1,0,1), (0,1,1),
            (1,0,0), (0,1,0), (0,0,1), (1,1,0), (1,0,1), (0,1,1)
        )

    def draw_cube(self):
        glBegin(GL_QUADS)
        for i, surface in enumerate(self.surfaces):
            # Using i % len(self.colors) to pick a color
            glColor3fv(self.colors[i % len(self.colors)])
            for vertex in surface:
                glVertex3fv(self.vertices[vertex])
        glEnd()
        
        glBegin(GL_LINES)
        glColor3fv((0,0,0)) # Black edges
        for edge in self.edges:
            for vertex in edge:
                glVertex3fv(self.vertices[vertex])
        glEnd()

    def draw_axes(self):
        glLineWidth(3)
        glBegin(GL_LINES)
        
        # X Axis - Red
        glColor3f(1, 0, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(2, 0, 0)
        
        # Y Axis - Green
        glColor3f(0, 1, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 2, 0)
        
        # Z Axis - Blue
        glColor3f(0, 0, 1)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 2)
        
        glEnd()
        glLineWidth(1)

    def update(self, roll, pitch, yaw):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return False

        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        
        # Draw static axes in the background (centered at origin)
        glPushMatrix()
        # No rotation for background axes to show global frame
        self.draw_axes()
        glPopMatrix()

        glPushMatrix()
        
        # Apply rotations
        glRotatef(pitch, 1, 0, 0)
        glRotatef(yaw, 0, 1, 0)
        glRotatef(roll, 0, 0, 1)
        
        self.draw_cube()
        # Draw nested axes that rotate with the cube
        self.draw_axes()
        
        glPopMatrix()
        
        pygame.display.flip()
        return True
