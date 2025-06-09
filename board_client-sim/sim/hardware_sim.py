import os
import pygame
import sys

# Model selection (default: cosmic)
MODEL = os.environ.get("UNICORN_SIM_MODEL", "cosmic").lower()
if MODEL == "cosmic":
    WIDTH, HEIGHT = 32, 32
elif MODEL == "galactic":
    WIDTH, HEIGHT = 53, 11
elif MODEL == "stellar":
    WIDTH, HEIGHT = 16, 16
else:
    raise RuntimeError(f"Unknown model: {MODEL}")

PIXEL_SIZE = 18  # Size of each LED "pixel" in the window

class GraphicsSim:
    def __init__(self):
        self.width = WIDTH
        self.height = HEIGHT
        self.buffer = [[(0, 0, 0) for _ in range(HEIGHT)] for _ in range(WIDTH)]
        self.current_pen = (255, 255, 255)
    def create_pen(self, r, g, b):
        return (int(r), int(g), int(b))
    def set_pen(self, pen):
        self.current_pen = pen
    def pixel(self, x, y):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            self.buffer[x][y] = self.current_pen
    def clear(self):
        for x in range(WIDTH):
            for y in range(HEIGHT):
                self.buffer[x][y] = (0, 0, 0)
    def get_bounds(self):
        return (WIDTH, HEIGHT)
    def set_font(self, font): pass
    def measure_text(self, text, scale=1): return len(text) * 8 * scale
    def cleanup_text_cache(self): pass
    def text(self, text, x, y, wordwrap=-1, scale=1):
        # Simple text rendering: just draw each char as a colored block
        for i, char in enumerate(text):
            px = int(x + i * 8 * scale)
            py = int(y)
            for dx in range(6 * scale):
                for dy in range(8 * scale):
                    if 0 <= px + dx < WIDTH and 0 <= py + dy < HEIGHT:
                        self.buffer[px + dx][py + dy] = self.current_pen
    
    def line(self, x1, y1, x2, y2):
        """Draw a line using Bresenham's algorithm."""
        x1, y1, x2, y2 = int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        x, y = x1, y1
        while True:
            self.pixel(x, y)
            if x == x2 and y == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

class GUISim:
    def __init__(self, graphics):
        self.graphics = graphics
        pygame.init()
        self.screen = pygame.display.set_mode(
            (WIDTH * PIXEL_SIZE, HEIGHT * PIXEL_SIZE)
        )
        pygame.display.set_caption(
            f"Unicorn Wrangler Simulator - {MODEL.capitalize()} ({WIDTH}x{HEIGHT})"
        )
        self.clock = pygame.time.Clock()
        self._brightness = 1.0
        self.running = True
    def update(self, graphics):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
        for x in range(WIDTH):
            for y in range(HEIGHT):
                r, g, b = graphics.buffer[x][y]
                # Apply brightness
                r = int(r * self._brightness)
                g = int(g * self._brightness)
                b = int(b * self._brightness)
                color = (r, g, b)
                rect = pygame.Rect(
                    x * PIXEL_SIZE, y * PIXEL_SIZE, PIXEL_SIZE, PIXEL_SIZE
                )
                pygame.draw.rect(self.screen, color, rect)
        pygame.display.flip()
        self.clock.tick(60)  # Limit to 60 FPS
    def clear_display(self):
        self.graphics.clear()
        self.update(self.graphics)
    def set_brightness(self, level):
        self._brightness = max(0.0, min(1.0, float(level)))
    def is_pressed(self, button):
        # No button support in sim
        return False

graphics = GraphicsSim()
gu = GUISim(graphics)

def set_brightness(level):
    gu.set_brightness(level)

