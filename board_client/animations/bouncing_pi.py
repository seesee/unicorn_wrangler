import uasyncio
import random

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT

# 9x5 pixel "pi" symbol (1 = pixel on, 0 = pixel off)
PI_BITMAP = [
    [0,1,0,1,1,1,1,1,1],
    [1,0,1,0,0,0,1,0,0],
    [0,0,1,0,0,0,1,0,0],
    [0,0,1,0,0,0,1,0,1],
    [0,1,0,0,0,0,1,1,0],
]

PI_W = len(PI_BITMAP[0])
PI_H = len(PI_BITMAP)

def _draw_pi(graphics, x, y, pen):
    graphics.set_pen(pen)
    for row in range(PI_H):
        for col in range(PI_W):
            if PI_BITMAP[row][col]:
                px = x + col
                py = y + row
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.pixel(px, py)


from collections import deque

# The number of trail steps to blend through
TRAIL_LENGTH = 4
BRIGHTNESS_FALLOFF = 0.2


# 9x5 pixel "pi" symbol (1 = pixel on, 0 = pixel off)
PI_BITMAP = [
    [0,1,0,1,1,1,1,1,1],
    [1,0,1,0,0,0,1,0,0],
    [0,0,1,0,0,0,1,0,0],
    [0,0,1,0,0,0,1,0,1],
    [0,1,0,0,0,0,1,1,0],
]

PI_W = len(PI_BITMAP[0])
PI_H = len(PI_BITMAP)

def _draw_pi(graphics, x, y, pen):
    graphics.set_pen(pen)
    for row in range(PI_H):
        for col in range(PI_W):
            if PI_BITMAP[row][col]:
                px = x + col
                py = y + row
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.pixel(px, py)


async def run(graphics, gu, state, interrupt_event):
    trail = deque((), TRAIL_LENGTH)

    x = random.randint(0, WIDTH - PI_W)
    y = random.randint(0, HEIGHT - PI_H)
    dx = random.choice([-1, 1])
    dy = random.choice([-1, 1])

    hue = random.random()

    black_pen = graphics.create_pen(0, 0, 0)

    while not interrupt_event.is_set():
        trail.append((x, y))

        x += dx
        y += dy

        bounced = False

        if x < 0:
            x = 0
            dx = 1
            bounced = True
        elif x > WIDTH - PI_W:
            x = WIDTH - PI_W
            dx = -1
            bounced = True

        if y < 0:
            y = 0
            dy = 1
            bounced = True
        elif y > HEIGHT - PI_H:
            y = HEIGHT - PI_H
            dy = -1
            bounced = True

        # change colour on bounce
        if bounced:
            hue = (hue + 0.18 + random.uniform(0, 0.2)) % 1.0

        graphics.set_pen(black_pen)
        graphics.clear()

        for i, (trail_x, trail_y) in enumerate(trail):
            # Fade the trail out
            v = BRIGHTNESS_FALLOFF ** (len(trail) - i)
            r, g, b = hsv_to_rgb(hue, 1.0, v)
            trail_pen = graphics.create_pen(r, g, b)
            _draw_pi(graphics, trail_x, trail_y, trail_pen)

        # Draw the new pi
        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
        color_pen = graphics.create_pen(r, g, b)
        _draw_pi(graphics, x, y, color_pen)

        gu.update(graphics)
        await uasyncio.sleep(0.12)
