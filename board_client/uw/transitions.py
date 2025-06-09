import uasyncio
import random
import utime
import uasyncio

from uw.hardware import graphics, gu, WIDTH, HEIGHT
from uw.logger import log
from animations.utils import hsv_to_rgb

async def melt_off():
    cleared = [[False for _ in range(HEIGHT)] for _ in range(WIDTH)]
    total = WIDTH * HEIGHT
    cleared_count = 0
    black_pen = graphics.create_pen(0, 0, 0)
    graphics.set_pen(black_pen)
    log("Melting off", "INFO")

    while cleared_count < total:
        for _ in range(10):  # Clear 10 pixels per frame for speed
            x = random.randint(0, WIDTH - 1)
            y = random.randint(0, HEIGHT - 1)
            if not cleared[x][y]:
                cleared[x][y] = True
                graphics.pixel(x, y)
                cleared_count += 1
        gu.update(graphics)
        await uasyncio.sleep(0.02)
    graphics.set_pen(black_pen)
    graphics.clear()
    gu.update(graphics)

async def countdown():

    digits = [str(i) for i in range(10, 0, -1)]
    duration_per_digit = 0.6  # seconds per digit

    graphics.set_font("bitmap8")
    font_height = 8  # bitmap8 is 8 pixels high
    log("Counting down...", "INFO")

    for index, digit in enumerate(digits):
        # colour cycle based on time + digit index
        hue = ((utime.ticks_ms() / 3000.0) + index * 0.08) % 1.0
        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
        digit_pen = graphics.create_pen(r, g, b)
        black_pen = graphics.create_pen(0, 0, 0)

        # invert every other digit
        invert = (index % 2 == 1)
        fg_pen = digit_pen if not invert else black_pen
        bg_pen = black_pen if not invert else digit_pen

        # centre digit
        w = graphics.measure_text(digit, 1)
        x = (WIDTH - w) // 2
        
        # centre vertically, then nudge down by 1 pixel for better visual centering
        y = (HEIGHT - font_height) // 2 + 1

        digit_start_time = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), digit_start_time) < duration_per_digit * 1000:
            # fill background
            graphics.set_pen(bg_pen)
            graphics.clear()

            # draw digit
            graphics.set_pen(fg_pen)
            graphics.text(digit, x, y, -1, 1)
            gu.update(graphics)
            await uasyncio.sleep(0.02)

    # clear display
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    gu.update(graphics)
