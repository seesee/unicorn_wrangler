import uasyncio
import random
import math

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT
from uw.logger import log

async def run(graphics, gu, state, interrupt_event):
    cell_w, cell_h = 1, 1
    cols = WIDTH // cell_w
    rows = HEIGHT // cell_h

    DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # (dy, dx)

    def draw_maze(maze, drawer=None, solution=None, exit_pos=None, exit_fade=1.0, t=0.0):
        for y in range(rows):
            for x in range(cols):
                if maze[y][x]:
                    hue = ((x + y) * 0.03 + t * 0.08) % 1.0
                    r, g, b = hsv_to_rgb(hue, 0.7, 1.0)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                else:
                    graphics.set_pen(graphics.create_pen(0, 0, 0))
                graphics.pixel(x, y)
        # draw solution path if present
        if solution:
            for row, col in solution:
                graphics.set_pen(graphics.create_pen(0, 80, 255))  # Blue
                graphics.pixel(col, row)
        # draw the drawer (maze solver head)
        if drawer:
            dr, dg, db = hsv_to_rgb(0.0, 1.0, 1.0)
            graphics.set_pen(graphics.create_pen(dr, dg, db))
            graphics.pixel(drawer[1], drawer[0])
        # draw the exit (fade in as green)
        if exit_pos:
            ex, ey = exit_pos[1], exit_pos[0]  # (col, row)
            r, g, b = hsv_to_rgb(0.33, 1.0, exit_fade)
            graphics.set_pen(graphics.create_pen(int(r), int(g), int(b)))
            if 0 <= ex < cols and 0 <= ey < rows:
                graphics.pixel(ex, ey)

    while not interrupt_event.is_set():
        # maze grid: 0 = wall, 1 = path
        maze = [[0 for _ in range(cols)] for _ in range(rows)]
        stack = []

        # start at a random cell
        start = (random.randint(0, rows - 1), random.randint(0, cols - 1))  # (row, col)
        maze[start[0]][start[1]] = 1
        stack.append(start)

        t = 0.0

        # maze generation loop
        while stack and not interrupt_event.is_set():
            y, x = stack[-1]
            # find unvisited neighbors
            neighbors = []
            for dy, dx in DIRS:
                ny, nx = y + dy * 2, x + dx * 2
                if 0 <= ny < rows and 0 <= nx < cols and maze[ny][nx] == 0:
                    neighbors.append((ny, nx, dy, dx))
            if neighbors:
                ny, nx, dy, dx = random.choice(neighbors)
                # carve path
                maze[y + dy][x + dx] = 1
                maze[ny][nx] = 1
                stack.append((ny, nx))
            else:
                stack.pop()

            graphics.set_pen(graphics.create_pen(0, 0, 0))
            graphics.clear()
            drawer = (y, x)
            draw_maze(maze, drawer=drawer, t=t)
            gu.update(graphics)
            t += 0.03
            await uasyncio.sleep(0.01)

        # Find the furthest out-of-bounds exit from the start
        def get_out_of_bounds_exits(maze):
            exits = []
            for x in range(cols):
                if maze[0][x]:
                    exits.append((x, -1))  # top
                if maze[rows-1][x]:
                    exits.append((x, rows))  # bottom
            for y in range(rows):
                if maze[y][0]:
                    exits.append((-1, y))  # left
                if maze[y][cols-1]:
                    exits.append((cols, y))  # right
            return exits

        # Find the closest in-bounds cell to each exit, always return (row, col)
        def in_bounds_neighbour(exit_pos):
            x, y = exit_pos
            if x == -1:
                return (y, 0)
            if x == cols:
                return (y, cols-1)
            if y == -1:
                return (0, x)
            if y == rows:
                return (rows-1, x)
            return (y, x)

        # Find the furthest exit from the start
        exits = get_out_of_bounds_exits(maze)
        if not exits:
            # fallback: just use a random edge cell
            exits = [(-1, start[0])]
        max_dist = -1
        chosen_exit = exits[0]
        for ex in exits:
            iy, ix = in_bounds_neighbour(ex)  # (row, col)
            dx = ix - start[1]
            dy = iy - start[0]
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > max_dist:
                max_dist = dist
                chosen_exit = ex

        exit_pos = chosen_exit
        exit_in_maze = in_bounds_neighbour(exit_pos)  # (row, col)

        # Fade in the exit as a green point
        for fade_step in range(12):
            if interrupt_event.is_set():
                break
            fade = (fade_step + 1) / 12.0
            graphics.set_pen(graphics.create_pen(0, 0, 0))
            graphics.clear()
            draw_maze(maze, exit_pos=exit_in_maze, exit_fade=fade, t=t)
            gu.update(graphics)
            t += 0.03
            await uasyncio.sleep(0.04)

        # Solve the maze from start to exit_in_maze using BFS
        prev = {}
        queue = []
        queue.append(start)
        visited = set()
        visited.add(start)
        found = False
        while queue and not found and not interrupt_event.is_set():
            cy, cx = queue.pop(0)
            if (cy, cx) == exit_in_maze:
                found = True
                break
            for dy, dx in DIRS:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < rows and 0 <= nx < cols and maze[ny][nx] and (ny, nx) not in visited:
                    prev[(ny, nx)] = (cy, cx)
                    queue.append((ny, nx))
                    visited.add((ny, nx))

        # reconstruct path
        path = []
        if found:
            node = exit_in_maze
            while node != start:
                path.append(node)
                if node not in prev:
                    # Path reconstruction failed, break out to avoid KeyError
                    path = []
                    break
                node = prev[node]
            if path:
                path.append(start)
                path = path[::-1]

        # Animate the man/dot escaping to the exit
        if found and path and not interrupt_event.is_set():
            for idx, drawer in enumerate(path):
                if interrupt_event.is_set():
                    break
                graphics.set_pen(graphics.create_pen(0, 0, 0))
                graphics.clear()
                draw_maze(maze, drawer=drawer, exit_pos=exit_in_maze, exit_fade=1.0, t=t)
                gu.update(graphics)
                t += 0.02
                await uasyncio.sleep(0.01)

        # Animate the blue fill showing the escape path
        for i in range(len(path)):
            if interrupt_event.is_set():
                break
            graphics.set_pen(graphics.create_pen(0, 0, 0))
            graphics.clear()
            draw_maze(maze, solution=path[:i+1], exit_pos=exit_in_maze, exit_fade=1.0, t=t)
            gu.update(graphics)
            t += 0.03
            await uasyncio.sleep(0.01)

        # fade out the maze leaving "solution" path
        fade_steps = 20
        for step in range(fade_steps):
            if interrupt_event.is_set():
                break
            fade = 1.0 - (step + 1) / fade_steps
            graphics.set_pen(graphics.create_pen(0, 0, 0))
            graphics.clear()
            for y in range(rows):
                for x in range(cols):
                    if maze[y][x]:
                        hue = ((x + y) * 0.03 + t * 0.08) % 1.0
                        r, g, b = hsv_to_rgb(hue, 0.7, fade)
                        graphics.set_pen(graphics.create_pen(r, g, b))
                        graphics.pixel(x, y)
            if found and path:
                for idx, (row, col) in enumerate(path):
                    path_fade = min(1.0, fade + 0.3)
                    r, g, b = hsv_to_rgb(0.6, 1.0, path_fade)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(col, row)
            # keep exit visible
            if exit_in_maze:
                ex, ey = exit_in_maze[1], exit_in_maze[0]
                r, g, b = hsv_to_rgb(0.33, 1.0, fade)
                graphics.set_pen(graphics.create_pen(int(r), int(g), int(b)))
                graphics.pixel(ex, ey)
            gu.update(graphics)
            await uasyncio.sleep(0.04)

        # slight pause before restarting
        for _ in range(30):
            if interrupt_event.is_set():
                break
            await uasyncio.sleep(0.03)
