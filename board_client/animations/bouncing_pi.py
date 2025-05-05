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

async def run(graphics, gu, state, interrupt_event):
    # bouncing pi symbol like the old dvd scrreensaver animation
    # choose random position and direction to start
    x = random.randint(0, WIDTH - PI_W)
    y = random.randint(0, HEIGHT - PI_H)
    dx = random.choice([-1, 1])
    dy = random.choice([-1, 1])
    speed = 0.7 + random.random() * 0.5

    hue = random.random()

    while not interrupt_event.is_set():
        # move
        x += dx * speed
        y += dy * speed

        bounced = False

        # boing
        if x < 0:
            x = 0
            dx = abs(dx)
            bounced = True
        elif x > WIDTH - PI_W:
            x = WIDTH - PI_W
            dx = -abs(dx)
            bounced = True

        if y < 0:
            y = 0
            dy = abs(dy)
            bounced = True
        elif y > HEIGHT - PI_H:
            y = HEIGHT - PI_H
            dy = -abs(dy)
            bounced = True

        # change colour on bounce
        if bounced:
            hue = (hue + 0.18 + random.uniform(0, 0.2)) % 1.0

        # black background
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # draw symbol from pixel map at calculated position/colour
        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
        pen = graphics.create_pen(r, g, b)
        for row in range(PI_H):
            for col in range(PI_W):
                if PI_BITMAP[row][col]:
                    px = int(x) + col
                    py = int(y) + row
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        graphics.set_pen(pen)
                        graphics.pixel(px, py)

        gu.update(graphics)
        await uasyncio.sleep(0.133)
