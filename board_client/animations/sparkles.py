import uasyncio
import random

from animations.utils import hsv_to_rgb

async def run(graphics, gu, state, interrupt_event):
    # pleasing sparkles effect
    WIDTH, HEIGHT = graphics.get_bounds()

    MAX_SPARKLES_ON_SCREEN = 75
    NEW_SPARKLES_MIN = 1
    NEW_SPARKLES_MAX = 4
    SPARKLE_SATURATION_MIN = 0.7
    SPARKLE_SATURATION_MAX = 1.0
    SPARKLE_DECAY_MIN = 0.03
    SPARKLE_DECAY_MAX = 0.10
    FRAME_DELAY = 0.05

    sparkles = []

    while not interrupt_event.is_set():
        # update sparkle states (fade and remove)
        next_sparkles = []
        for s in sparkles:
            s['v'] -= s['decay']
            if s['v'] > 0:
                next_sparkles.append(s)
        sparkles = next_sparkles

        # add new sparkles
        num_new = random.randint(NEW_SPARKLES_MIN, NEW_SPARKLES_MAX)
        for _ in range(num_new):
            if len(sparkles) < MAX_SPARKLES_ON_SCREEN:
                new_sparkle = {
                    'x': random.randint(0, WIDTH - 1),
                    'y': random.randint(0, HEIGHT - 1),
                    'h': random.random(),
                    's': random.uniform(SPARKLE_SATURATION_MIN, SPARKLE_SATURATION_MAX),
                    'v': 1.0,
                    'decay': random.uniform(SPARKLE_DECAY_MIN, SPARKLE_DECAY_MAX)
                }
                sparkles.append(new_sparkle)

        # draw
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        for s in sparkles:
            r, g, b = hsv_to_rgb(s['h'], s['s'], s['v'])
            pen = graphics.create_pen(r, g, b)
            graphics.set_pen(pen)
            graphics.pixel(s['x'], s['y'])

        gu.update(graphics)
        await uasyncio.sleep(FRAME_DELAY)
