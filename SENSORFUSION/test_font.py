import pygame
import pygame.font

try:
    pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
    print("Pygame Font initialized successfully")
    f = pygame.font.SysFont('Arial', 24)
    print("Font loaded:", f)
except Exception as e:
    print("Error:", e)
