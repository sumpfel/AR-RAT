import pygame
import pygame.freetype

try:
    pygame.init()
    if not pygame.freetype.get_init():
        pygame.freetype.init()
    print("Pygame Freetype initialized successfully")
    f = pygame.freetype.SysFont('Arial', 24)
    print("Font loaded:", f)
    # Test rendering
    surf, rect = f.render("Hello World", (255, 255, 255))
    print("Rendered surface:", surf)
except Exception as e:
    print("Error:", e)
    import traceback
    traceback.print_exc()
