import uasyncio
import random
import micropython

from animations.utils import hsv_to_rgb
from uw.hardware import MODEL

@micropython.native
async def run(graphics, gu, state, interrupt_event):
    WIDTH, HEIGHT = graphics.get_bounds()

    # Pre-calculate pens
    fire_colours = [
        graphics.create_pen(0, 0, 0),
        graphics.create_pen(20, 20, 20),
        graphics.create_pen(180, 30, 0),
        graphics.create_pen(220, 160, 0),
        graphics.create_pen(255, 255, 180)
    ]

    width = WIDTH + 2
    height = HEIGHT + 4

    heat = [[0.0 for _ in range(height)] for _ in range(width)]

    # Adjust for small displays
    if MODEL in ("stellar", "uhd") or (WIDTH == 16 and HEIGHT == 16):
        fire_spawns = 3  # fewer spawns
        spawn_rows = [height - 1]  # only bottom row
    else:
        fire_spawns = 5
        spawn_rows = [height - 1, height - 2] 

    damping_factor = 0.97

    while not interrupt_event.is_set():
        for x in range(width):
            for row in spawn_rows:
                heat[x][row] = 0.0

        for c in range(fire_spawns):
            x = random.randint(0, width - 4) + 2
            for row in spawn_rows:
                heat[x + 0][row] = 1.0
                heat[x + 1][row] = 1.0
                heat[x - 1][row] = 1.0

        for y in range(0, height - 2):
            for x in range(1, width - 1):
                average = (
                    heat[x][y] + heat[x][y + 1] + heat[x][y + 2] +
                    heat[x - 1][y + 1] + heat[x + 1][y + 1]
                ) / 5.0
                average *= damping_factor
                heat[x][y] = average

        # draw fire
        for y in range(HEIGHT):
            for x in range(WIDTH):
                value = heat[x + 1][y]
                if value < 0.15:
                    graphics.set_pen(fire_colours[0])
                elif value < 0.25:
                    graphics.set_pen(fire_colours[1])
                elif value < 0.35:
                    graphics.set_pen(fire_colours[2])
                elif value < 0.45:
                    graphics.set_pen(fire_colours[3])
                else:
                    graphics.set_pen(fire_colours[4])
                graphics.pixel(x, y)

        gu.update(graphics)
        await uasyncio.sleep(0.001)
