import uasyncio
import random

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT
from uw.logger import log

async def run(graphics, gu, state, interrupt_event):
    # maze generator and solver. todo: try to use interesting start/endpoints
    cell_w, cell_h = 1, 1
    cols = WIDTH // cell_w
    rows = HEIGHT // cell_h

    DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    def draw_maze(maze, drawer=None, solution=None, t=0.0):
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
        # draw the drawer (maze generator head)
        if drawer:
            dr, dg, db = hsv_to_rgb(0.0, 1.0, 1.0)
            graphics.set_pen(graphics.create_pen(dr, dg, db))
            graphics.pixel(drawer[1], drawer[0])

    while not interrupt_event.is_set():
        # maze grid: 0 = wall, 1 = path
        maze = [[0 for _ in range(cols)] for _ in range(rows)]
        stack = []

        # start at a random cell
        current = (random.randint(0, rows - 1), random.randint(0, cols - 1))
        maze[current[0]][current[1]] = 1
        stack.append(current)

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

        # solve maze once generation complete using bfs
        start = (0, 0)
        end = (rows - 1, cols - 1)

        # find a path from any open cell on the edge to any other open cell on the opposite edge
        # todo: make this better
        edge_cells = [(y, x) for y in [0, rows-1] for x in range(cols) if maze[y][x]] + \
                     [(y, x) for x in [0, cols-1] for y in range(rows) if maze[y][x]]
        if edge_cells:
            start = random.choice(edge_cells)
            end = random.choice([cell for cell in edge_cells if cell != start])
        else:
            start = (0, 0)
            end = (rows - 1, cols - 1)

        prev = {}
        queue = []
        queue.append(start)
        visited = set()
        visited.add(start)
        found = False
        while queue and not found and not interrupt_event.is_set():
            cy, cx = queue.pop(0)
            if (cy, cx) == end:
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
            node = end
            while node != start:
                path.append(node)
                node = prev[node]
            path.append(start)
            path = path[::-1]

        # animate the solution path
        for i in range(len(path)):
            if interrupt_event.is_set():
                break
            graphics.set_pen(graphics.create_pen(0, 0, 0))
            graphics.clear()
            draw_maze(maze, solution=path[:i+1], t=t)
            gu.update(graphics)
            t += 0.03
            await uasyncio.sleep(0.01)

        # animate the drawer walking the solution path. todo: remove?
        if found and path and not interrupt_event.is_set():
            log("starting drawer walk. path length: {}".format(len(path)), "DEBUG")
            try:
                for idx in range(len(path)-1, -1, -1):
                    if interrupt_event.is_set():
                        log("drawer walk interrupted at idx {}".format(idx), "DEBUG")
                        break
                    drawer = path[idx]
                    log("drawer at idx {} position {}".format(idx, drawer), "DEBUG")
                    graphics.set_pen(graphics.create_pen(0, 0, 0))
                    graphics.clear()
                    draw_maze(maze, solution=path, drawer=drawer, t=t)
                    gu.update(graphics)
                    t += 0.02
                    await uasyncio.sleep(0.01)
                log("drawer walk complete", "DEBUG")
            except Exception as e:
                log("exception during drawer walk: {}".format(repr(e)), "ERROR")

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
                    # fade solution path slower. looks better when it's an interesting path.
                    path_fade = min(1.0, fade + 0.3)
                    r, g, b = hsv_to_rgb(0.6, 1.0, path_fade)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(col, row)
            gu.update(graphics)
            await uasyncio.sleep(0.04)

        # slight pause before restarting
        for _ in range(30):
            if interrupt_event.is_set():
                break
            await uasyncio.sleep(0.03)
