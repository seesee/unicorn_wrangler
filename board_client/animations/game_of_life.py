import uasyncio
import math
import random
import gc

from animations.utils import (
    uwPrng, hsv_to_rgb 
)

prng = uwPrng()

async def run(graphics, gu, state, interrupt_event):
    # conway's game of life + coloured, merging cells.
    WIDTH, HEIGHT = graphics.get_bounds()
    INITIAL_DENSITY = prng.randfloat(0.20, 0.30)
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

    # Double buffering with pre-allocated grids (Item 37)
    cells = [[
        random.random() if random.random() < INITIAL_DENSITY else None
        for _ in range(WIDTH)
    ] for _ in range(HEIGHT)]
    
    # Pre-allocate second buffer to avoid GC pressure
    next_cells = [[None for _ in range(WIDTH)] for _ in range(HEIGHT)]
    
    iteration = 0
    black_pen = graphics.create_pen(0, 0, 0)
    
    # Add boundary padding for optimized neighbor counting (Item 38)
    # Expand grid size to eliminate modulo operations
    padded_width = WIDTH + 2
    padded_height = HEIGHT + 2
    padded_cells = [[None for _ in range(padded_width)] for _ in range(padded_height)]
    padded_next = [[None for _ in range(padded_width)] for _ in range(padded_height)]
    
    def sync_to_padded():
        """Copy main grid to padded grid with boundary wrapping"""
        # Copy interior
        for y in range(HEIGHT):
            for x in range(WIDTH):
                padded_cells[y + 1][x + 1] = cells[y][x]
        
        # Wrap boundaries
        for x in range(WIDTH):
            padded_cells[0][x + 1] = cells[HEIGHT - 1][x]  # top edge
            padded_cells[padded_height - 1][x + 1] = cells[0][x]  # bottom edge
        for y in range(HEIGHT):
            padded_cells[y + 1][0] = cells[y][WIDTH - 1]  # left edge
            padded_cells[y + 1][padded_width - 1] = cells[y][0]  # right edge
        
        # Wrap corners
        padded_cells[0][0] = cells[HEIGHT - 1][WIDTH - 1]
        padded_cells[0][padded_width - 1] = cells[HEIGHT - 1][0]
        padded_cells[padded_height - 1][0] = cells[0][WIDTH - 1]
        padded_cells[padded_height - 1][padded_width - 1] = cells[0][0]
    
    def sync_from_padded():
        """Copy padded grid interior back to main grid"""
        for y in range(HEIGHT):
            for x in range(WIDTH):
                next_cells[y][x] = padded_next[y + 1][x + 1]

    while not interrupt_event.is_set():
        # Use double buffering - clear the buffer instead of allocating (Item 37)
        for y in range(HEIGHT):
            for x in range(WIDTH):
                next_cells[y][x] = None
        
        live_cell_count = 0
        
        # Sync current state to padded grid (Item 38)
        sync_to_padded()
        
        # Clear padded next buffer
        for y in range(padded_height):
            for x in range(padded_width):
                padded_next[y][x] = None

        # Optimized neighbor counting with boundary padding (Item 38)
        for y in range(1, padded_height - 1):  # Skip boundary rows
            for x in range(1, padded_width - 1):  # Skip boundary columns
                neighbor_count = 0
                neighbor_hues = []
                
                # Direct access without modulo operations
                neighbors = [
                    padded_cells[y-1][x-1], padded_cells[y-1][x], padded_cells[y-1][x+1],
                    padded_cells[y][x-1],                         padded_cells[y][x+1],
                    padded_cells[y+1][x-1], padded_cells[y+1][x], padded_cells[y+1][x+1]
                ]
                
                for neighbor_hue in neighbors:
                    if neighbor_hue is not None:
                        neighbor_count += 1
                        neighbor_hues.append(neighbor_hue)
                
                current_hue = padded_cells[y][x]
                is_alive = current_hue is not None
                
                if is_alive:
                    if neighbor_count == 2 or neighbor_count == 3:
                        padded_next[y][x] = current_hue
                        live_cell_count += 1
                else:
                    if neighbor_count == 3:
                        padded_next[y][x] = average_hues(neighbor_hues)
                        live_cell_count += 1
        
        # Copy results back to next_cells buffer
        sync_from_padded()
        
        # Display the computed next generation
        graphics.set_pen(black_pen)
        graphics.clear()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                hue = next_cells[y][x]
                if hue is not None:
                    r, g, b = hsv_to_rgb(hue, SATURATION, VALUE)
                    pen = graphics.create_pen(r, g, b)
                    graphics.set_pen(pen)
                    graphics.pixel(x, y)

        gu.update(graphics)
        
        # Swap buffers AFTER displaying to prepare for next iteration (Item 37)
        cells, next_cells = next_cells, cells
        iteration += 1

        if iteration > RESET_ITERATIONS or live_cell_count < RESET_MIN_CELLS:
            # Clear existing grids instead of reallocating (Item 37)
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    cells[y][x] = random.random() if random.random() < INITIAL_DENSITY else None
                    next_cells[y][x] = None
            iteration = 0
            gc.collect()

        await uasyncio.sleep(UPDATE_INTERVAL)
