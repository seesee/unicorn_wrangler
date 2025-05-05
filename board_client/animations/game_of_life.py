import uasyncio
import math
import random
import gc

from animations.utils import hsv_to_rgb

async def run(graphics, gu, state, interrupt_event):
    # conway's game of life + coloured, merging cells.
    WIDTH, HEIGHT = graphics.get_bounds()
    INITIAL_DENSITY = 0.25
    SATURATION = 1.0
    VALUE = 1.0
    UPDATE_INTERVAL = 0.15
    RESET_ITERATIONS = 200
    RESET_MIN_CELLS = 5

    def average_hues(hues):
        if not hues:
            return random.random()
        num_hues = len(hues)
        sum_x = 0.0
        sum_y = 0.0
        for hue in hues:
            angle = hue * 2.0 * math.pi
            sum_x += math.cos(angle)
            sum_y += math.sin(angle)
        avg_x = sum_x / num_hues
        avg_y = sum_y / num_hues
        avg_angle = math.atan2(avg_y, avg_x)
        avg_hue = avg_angle / (2.0 * math.pi)
        if avg_hue < 0.0:
            avg_hue += 1.0
        return avg_hue

    cells = [[
        random.random() if random.random() < INITIAL_DENSITY else None
        for _ in range(WIDTH)
    ] for _ in range(HEIGHT)]
    iteration = 0
    black_pen = graphics.create_pen(0, 0, 0)

    while not interrupt_event.is_set():
        new_cells = [[None for _ in range(WIDTH)] for _ in range(HEIGHT)]
        live_cell_count = 0

        for y in range(HEIGHT):
            for x in range(WIDTH):
                neighbor_count = 0
                neighbor_hues = []
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        nx = (x + dx) % WIDTH
                        ny = (y + dy) % HEIGHT
                        neighbor_hue = cells[ny][nx]
                        if neighbor_hue is not None:
                            neighbor_count += 1
                            neighbor_hues.append(neighbor_hue)
                current_hue = cells[y][x]
                is_alive = current_hue is not None
                if is_alive:
                    if neighbor_count == 2 or neighbor_count == 3:
                        new_cells[y][x] = current_hue
                        live_cell_count += 1
                else:
                    if neighbor_count == 3:
                        new_cells[y][x] = average_hues(neighbor_hues)
                        live_cell_count += 1

        graphics.set_pen(black_pen)
        graphics.clear()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                hue = cells[y][x]
                if hue is not None:
                    r, g, b = hsv_to_rgb(hue, SATURATION, VALUE)
                    pen = graphics.create_pen(r, g, b)
                    graphics.set_pen(pen)
                    graphics.pixel(x, y)

        gu.update(graphics)
        cells = new_cells
        iteration += 1

        if iteration > RESET_ITERATIONS or live_cell_count < RESET_MIN_CELLS:
            cells = [[
                random.random() if random.random() < INITIAL_DENSITY else None
                for _ in range(WIDTH)
            ] for _ in range(HEIGHT)]
            iteration = 0
            gc.collect()

        await uasyncio.sleep(UPDATE_INTERVAL)
