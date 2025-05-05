import uasyncio
import math

from animations.utils import hsv_to_rgb, fast_sin
from uw.hardware import WIDTH, HEIGHT

async def run(graphics, gu, state, interrupt_event):
    # boring checkerboard pattern with a pulsing effect for testing
    t = 0.0
    checker_size = 3 + (WIDTH + HEIGHT) // 16  # adapt to display size

    while not interrupt_event.is_set():
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # Pulse parameters
        pulse = 0.5 + 0.5 * fast_sin(t * 0.8)
        hue_base = (t * 0.07) % 1.0

        for y in range(HEIGHT):
            for x in range(WIDTH):
                # checkerboard pattern
                checker = ((x // checker_size) + (y // checker_size)) % 2
                # colour and brightness
                hue = (hue_base + 0.12 * checker) % 1.0
                sat = 0.8
                val = 0.3 + 0.7 * (pulse if checker == 0 else 1.0 - pulse)
                r, g, b = hsv_to_rgb(hue, sat, val)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(x, y)

        gu.update(graphics)
        t += 0.03
        await uasyncio.sleep(0.001)
