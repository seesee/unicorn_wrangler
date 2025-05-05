import uasyncio
import math

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

BASE_SIZE_FACTOR = 0.8
MIN_SCALE_FACTOR = 1.0
MAX_SCALE_FACTOR = 2.5
SCALE_SPEED = 0.25
DRIFT_SPEED_X = 0.18
DRIFT_SPEED_Y = 0.22
DRIFT_AMP_X_FACTOR = 0.10
DRIFT_AMP_Y_FACTOR = 0.08

FAILSAFE_VALUE = 1.0
FAILSAFE_SAT = 1.0
FAILSAFE_DIAGONAL_SPEED = 0.4  # speed for failsafe pattern

DIAGONAL_FREQ = 0.01 # background rainbow bands (lower=wider)
BACKGROUND_VALUE = 0.15
BACKGROUND_SAT = 0.8
BACKGROUND_DIAGONAL_SPEED = 0.1 # speed for background pattern

failsafe_bitmap = [
    (6, 0), (18, 0), (5, 1), (7, 1), (17, 1), (19, 1), (4, 2), (8, 2),
    (16, 2), (20, 2), (0, 3), (1, 3), (3, 3), (9, 3), (10, 3), (14, 3),
    (15, 3), (21, 3), (23, 3), (24, 3), (0, 4), (1, 4), (2, 4), (9, 4),
    (10, 4), (14, 4), (15, 4), (22, 4), (23, 4), (24, 4), (3, 5), (4, 5),
    (20, 5), (21, 5), (3, 6), (5, 6), (6, 6), (18, 6), (19, 6), (21, 6),
    (3, 7), (7, 7), (8, 7), (16, 7), (17, 7), (21, 7), (4, 8), (9, 8),
    (10, 8), (14, 8), (15, 8), (20, 8), (5, 9), (11, 9), (13, 9), (19, 9),
    (6, 10), (12, 10), (18, 10), (5, 11), (7, 11), (17, 11), (18, 11),
    (19, 11), (4, 12), (8, 12), (16, 12), (17, 12), (18, 12), (19, 12),
    (20, 12), (5, 13), (7, 13), (12, 13), (17, 13), (18, 13), (19, 13),
    (6, 14), (11, 14), (13, 14), (15, 14), (16, 14), (18, 14), (10, 15),
    (14, 15), (10, 16), (12, 16), (14, 16), (10, 17), (14, 17), (11, 18),
    (13, 18), (12, 19)
]

GRID_WIDTH = max(x for x, y in failsafe_bitmap) + 1
GRID_HEIGHT = max(y for x, y in failsafe_bitmap) + 1

def transform_point(grid_x, grid_y, grid_w, grid_h, center_x, center_y, scale):
    relative_x = grid_x - grid_w / 2.0
    relative_y = grid_y - grid_h / 2.0
    scaled_x = relative_x * scale
    scaled_y = relative_y * scale
    screen_x = int(center_x + scaled_x)
    screen_y = int(center_y + scaled_y)
    return screen_x, screen_y

async def run(graphics, gu, state, interrupt_event):
	# failsafe effect for friends of mara
    t = 0.0
    max_drift_x = WIDTH * DRIFT_AMP_X_FACTOR
    max_drift_y = HEIGHT * DRIFT_AMP_Y_FACTOR

    margin = 1
    base_scale_w = (WIDTH - 2 * margin) / GRID_WIDTH if GRID_WIDTH > 0 else 1
    base_scale_h = (HEIGHT - 2 * margin) / GRID_HEIGHT if GRID_HEIGHT > 0 else 1
    base_pixel_scale = min(base_scale_w, base_scale_h) * BASE_SIZE_FACTOR

    while not interrupt_event.is_set():
        scale_phase = (fast_sin(t * SCALE_SPEED) + 1.0) / 2.0
        current_scale_factor = MIN_SCALE_FACTOR + scale_phase * (MAX_SCALE_FACTOR - MIN_SCALE_FACTOR)
        final_pixel_scale = base_pixel_scale * current_scale_factor

        center_x = WIDTH / 2 + fast_cos(t * DRIFT_SPEED_X) * max_drift_x
        center_y = HEIGHT / 2 + fast_sin(t * DRIFT_SPEED_Y) * max_drift_y

        for y in range(HEIGHT):
            for x in range(WIDTH):
                diagonal_value = x + y
                current_hue = (diagonal_value * DIAGONAL_FREQ - t * BACKGROUND_DIAGONAL_SPEED) % 1.0
                r, g, b = hsv_to_rgb(current_hue, BACKGROUND_SAT, BACKGROUND_VALUE)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(x, y)

        for grid_x, grid_y in failsafe_bitmap:
            corners_grid = [
                (grid_x, grid_y), (grid_x + 1, grid_y),
                (grid_x + 1, grid_y + 1), (grid_x, grid_y + 1)
            ]
            corners_screen = [
                transform_point(gx, gy, GRID_WIDTH, GRID_HEIGHT, center_x, center_y, final_pixel_scale)
                for gx, gy in corners_grid
            ]

            block_center_x = (corners_screen[0][0] + corners_screen[2][0]) / 2.0
            block_center_y = (corners_screen[0][1] + corners_screen[2][1]) / 2.0
            diagonal_value = block_center_x + block_center_y
            current_hue = (diagonal_value * DIAGONAL_FREQ - t * FAILSAFE_DIAGONAL_SPEED) % 1.0
            r, g, b = hsv_to_rgb(current_hue, FAILSAFE_SAT, FAILSAFE_VALUE)
            pen = graphics.create_pen(r, g, b)
            graphics.set_pen(pen)

            min_x = min(p[0] for p in corners_screen)
            max_x = max(p[0] for p in corners_screen)
            min_y = min(p[1] for p in corners_screen)
            max_y = max(p[1] for p in corners_screen)

            for y in range(max(0, min_y), min(HEIGHT, max_y + 1)):
                 draw_min_x = max(0, min_x)
                 draw_max_x = min(WIDTH - 1, max_x)
                 if draw_max_x >= draw_min_x:
                     graphics.line(draw_min_x, y, draw_max_x, y)

        t += 0.05

        gu.update(graphics)
        await uasyncio.sleep(0.02)
