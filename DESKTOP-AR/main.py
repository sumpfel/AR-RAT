import sys
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math

from window_manager import WindowManager
from udp_listener import UDPListener

# Constants
DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 720
SPHERE_RADIUS = 10

def draw_text(x, y, text):
    # Font rendering in 3D is complex in raw OpenGL. 
    # For prototype, we simulate windows as colored quads.
    pass

def draw_window(win, is_focused):
    glPushMatrix()
    
    # Rotate to position on sphere
    glRotatef(win.pitch, -1, 0, 0) # Pitch (X-axis)
    glRotatef(win.yaw, 0, 1, 0)   # Yaw (Y-axis)
    glTranslatef(0, 0, -SPHERE_RADIUS) # Move out to radius
    
    # Draw Window Quad
    w = win.width / 10.0 # Scale visual size
    h = win.height / 10.0 
    
    if is_focused:
        glColor3f(win.color[0], win.color[1], win.color[2]) # Full color
        # Draw border
        glLineWidth(3)
        glBegin(GL_LINE_LOOP)
        glColor3f(1, 1, 1) # White border for focus
        glVertex3f(-w, -h, 0.1)
        glVertex3f(w, -h, 0.1)
        glVertex3f(w, h, 0.1)
        glVertex3f(-w, h, 0.1)
        glEnd()
    else:
        glColor3f(win.color[0]*0.5, win.color[1]*0.5, win.color[2]*0.5) # Dimmed

    glBegin(GL_QUADS)
    # Use win.color set above
    glVertex3f(-w, -h, 0)
    glVertex3f(w, -h, 0)
    glVertex3f(w, h, 0)
    glVertex3f(-w, h, 0)
    glEnd()
    
    glPopMatrix()

def main():
    pygame.init()
    display = (DISPLAY_WIDTH, DISPLAY_HEIGHT)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
    pygame.display.set_caption("DESKTOP-AR Sphere Prototype")

    gluPerspective(45, (display[0]/display[1]), 0.1, 100.0)
    
    wm = WindowManager()
    udp = UDPListener()
    udp.start()
    
    camera_yaw = 0
    camera_pitch = 0
    
    mouse_dragging = False
    last_mouse_pos = (0, 0)

    clock = pygame.time.Clock()

    while True:
        # 1. Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                udp.stop()
                pygame.quit()
                sys.exit()
            
            # Key Controls
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    udp.stop()
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_LEFT:
                    wm.move_focus("left")
                if event.key == pygame.K_RIGHT:
                    wm.move_focus("right")
                if event.key == pygame.K_UP:
                    wm.move_focus("up")
                if event.key == pygame.K_DOWN:
                    wm.move_focus("down")
                if event.key == pygame.K_n:
                    # Test creating window at current cam
                    wm.add_window(len(wm.windows), -camera_yaw, -camera_pitch, 30, 20, (0.5,0.5,0.5), "New")

            # Mouse Camera Control (Middle Button / Wheel)
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 2: # Middle click
                    mouse_dragging = True
                    last_mouse_pos = event.pos
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 2:
                    mouse_dragging = False
            
            if event.type == pygame.MOUSEMOTION:
                if mouse_dragging:
                    dx = event.pos[0] - last_mouse_pos[0]
                    dy = event.pos[1] - last_mouse_pos[1]
                    camera_yaw -= dx * 0.2
                    camera_pitch -= dy * 0.2
                    last_mouse_pos = event.pos

        # 2. UDP Command Handling
        while True:
            cmd = udp.get_command()
            if not cmd:
                break
            
            if cmd['cmd'] == "move_focus":
                wm.move_focus(cmd['dir'])
            elif cmd['cmd'] == "move_window":
                wm.move_current_window(cmd.get('dx',0), cmd.get('dy',0))
            elif cmd['cmd'] == "resize_window":
                wm.resize_current_window(cmd.get('dw',0), cmd.get('dh',0))

        # 3. Rendering
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        # Camera Transform (Inverse of camera position)
        glRotatef(camera_pitch, 1, 0, 0)
        glRotatef(camera_yaw, 0, 1, 0)
        
        # Draw all windows
        for i, win in enumerate(wm.windows):
            is_focused = (i == wm.focused_window_idx)
            draw_window(win, is_focused)
            
        # Draw a reference grid/wireframe sphere?
        # glColor3f(0.2, 0.2, 0.2)
        # gluSphere(gluNewQuadric(), SPHERE_RADIUS + 1, 10, 10)

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
