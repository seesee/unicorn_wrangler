import uasyncio
import math

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

# Configurable parameters
TRAIL_LENGTH = 24      # trail points
TRAIL_FADE_STEP = 0.03 # brightness drop/trail point

async def run(graphics, gu, state, interrupt_event):
    # lissajous parameters (todo: randomise for variety?)
    a = 2  # x frequency
    b = 3  # y frequency
    delta = math.pi / 2  # phase difference

    center_x = (WIDTH - 1) / 2
    center_y = (HEIGHT - 1) / 2
    amp_x = (WIDTH - 1) / 2
    amp_y = (HEIGHT - 1) / 2

    t = 0.0
    hue = 0.0

    while not interrupt_event.is_set():
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # Calculate dot position
        x = int(round(center_x + amp_x * fast_sin(a * t + delta)))
        y = int(round(center_y + amp_y * fast_sin(b * t)))

        # Colour cycles with time
        hue = (hue + 0.008) % 1.0

        # draw a fading trail...
        for i in range(1, TRAIL_LENGTH + 1):
            trail_t = t - i * 0.07
            tx = int(round(center_x + amp_x * fast_sin(a * trail_t + delta)))
            ty = int(round(center_y + amp_y * fast_sin(b * trail_t)))
            fade = max(0.0, 1.0 - i * TRAIL_FADE_STEP)
            tr, tg, tb = hsv_to_rgb(hue, 1.0, fade)
            graphics.set_pen(graphics.create_pen(tr, tg, tb))
            if 0 <= tx < WIDTH and 0 <= ty < HEIGHT:
                graphics.pixel(tx, ty)

        # draw the main dot as a single, full-brightness pixel
        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
        graphics.set_pen(graphics.create_pen(r, g, b))
        graphics.pixel(x, y)

        gu.update(graphics)
        t += 0.045
        await uasyncio.sleep(0.01)
