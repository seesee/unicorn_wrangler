import uasyncio
import math
import random
import time

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT, MODEL

# Constants for red
BASE_RED_HUE = 0.0  # HSV red
BASE_RED_SAT = 1.0
BASE_RED_VAL = 1.0

BORDER_WIDTH = 1

def get_text_lines_and_font(graphics):
    """Determine text lines and font size for the current model."""
    if MODEL == "galactic":
        # Single line, as large as possible
        font = "bitmap8"
        text = "ON AIR"
        graphics.set_font(font)
        text_width = graphics.measure_text(text, 1)
        if text_width + 2 * BORDER_WIDTH > WIDTH:
            font = "bitmap6"
            graphics.set_font(font)
        return [text], font
    else:
        # Two lines, as large as possible
        font = "bitmap8"
        graphics.set_font(font)
        text1 = "ON"
        text2 = "AIR"
        text1_width = graphics.measure_text(text1, 1)
        text2_width = graphics.measure_text(text2, 1)
        font_height = 8
        total_height = 2 * font_height + 1  # 1 pixel gap
        if (text1_width > WIDTH - 2 * BORDER_WIDTH or
            text2_width > WIDTH - 2 * BORDER_WIDTH or
            total_height > HEIGHT - 2 * BORDER_WIDTH):
            font = "bitmap6"
            graphics.set_font(font)
        return ["ON", "AIR"], font

def draw_border(graphics, border_pen):
    # Top and bottom
    for x in range(WIDTH):
        graphics.set_pen(border_pen)
        graphics.pixel(x, 0)
        graphics.pixel(x, HEIGHT - 1)
    # Left and right
    for y in range(HEIGHT):
        graphics.set_pen(border_pen)
        graphics.pixel(0, y)
        graphics.pixel(WIDTH - 1, y)

def get_breathing_brightness(t, period=45.0, min_b=0.5, max_b=1.0):
    # Sine-based breathing effect, period in seconds
    phase = (t / period) * 2 * math.pi
    return min_b + (max_b - min_b) * (0.5 + 0.5 * math.sin(phase))

def get_wave_brightness(x, y, t, sweep_period, min_b=0.6, max_b=1.2):
    # Diagonal wave: phase depends on (x + y)
    diag = x + y
    phase = (diag / (WIDTH + HEIGHT) * 2 * math.pi) - (t / sweep_period) * 2 * math.pi
    return min_b + (max_b - min_b) * (0.5 + 0.5 * math.sin(phase))

async def run(graphics, gu, state, interrupt_event):
    # Randomize sweep period for each run
    sweep_period = random.uniform(15, 30)
    breathing_period = random.uniform(30, 60)  # much slower breathing

    # Precompute text lines and font
    text_lines, font = get_text_lines_and_font(graphics)
    graphics.set_font(font)
    font_height = 8 if font == "bitmap8" else 6

    # Precompute text positions
    text_positions = []
    if MODEL == "galactic":
        # Single line, center horizontally and vertically
        text = text_lines[0]
        text_width = graphics.measure_text(text, 1)
        x = (WIDTH - text_width) // 2
        y = (HEIGHT - font_height) // 2 + 1
        text_positions.append((text, x, y))
    else:
        # Two lines, center each line horizontally, both vertically
        total_text_height = 2 * font_height + 1  # 1 pixel gap
        y0 = (HEIGHT - total_text_height) // 2 + 1
        for i, line in enumerate(text_lines):
            text_width = graphics.measure_text(line, 1)
            x = (WIDTH - text_width) // 2
            y = y0 + i * (font_height + 1)
            text_positions.append((line, x, y))

    t0 = time.time()
    while not interrupt_event.is_set():
        t = time.time() - t0

        # --- Border breathing effect ---
        border_brightness = get_breathing_brightness(t, period=breathing_period, min_b=0.5, max_b=1.0)
        border_r, border_g, border_b = hsv_to_rgb(BASE_RED_HUE, BASE_RED_SAT, border_brightness)
        border_pen = graphics.create_pen(border_r, border_g, border_b)

        # --- Clear background ---
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # --- Draw border ---
        draw_border(graphics, border_pen)

        # --- Draw text with diagonal wave ---
        for line, x0, y0 in text_positions:
            for i, char in enumerate(line):
                char_x = x0 + graphics.measure_text(line[:i], 1)
                char_y = y0
                # Use the center of the char cell for the wave
                char_width = graphics.measure_text(char, 1)
                px = char_x + char_width // 2
                py = char_y + font_height // 2
                # Only draw if this char is inside the border
                if (BORDER_WIDTH <= char_x < WIDTH - BORDER_WIDTH and
                    BORDER_WIDTH <= char_y < HEIGHT - BORDER_WIDTH):
                    wave_brightness = get_wave_brightness(px, py, t, sweep_period)
                    base_r, base_g, base_b = hsv_to_rgb(BASE_RED_HUE, BASE_RED_SAT, BASE_RED_VAL)
                    r = min(255, int(base_r * wave_brightness))
                    g = min(255, int(base_g * wave_brightness))
                    b = min(255, int(base_b * wave_brightness))
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.text(char, char_x, char_y, -1, 1)

        gu.update(graphics)
        await uasyncio.sleep(0.03)
