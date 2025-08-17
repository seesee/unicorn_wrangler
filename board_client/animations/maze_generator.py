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

    def draw_maze(maze, drawer=None, solution=None, entrance_pos=None, exit_pos=None, exit_fade=1.0, t=0.0, explored_cells=None):
        for y in range(rows):
            for x in range(cols):
                if maze[y][x]:
                    hue = ((x + y) * 0.03 + t * 0.08) % 1.0
                    
                    # Check if this cell has been explored by the avatar
                    if explored_cells and (y, x) in explored_cells:
                        # Use inverted hue for explored paths
                        inverted_hue = (hue + 0.5) % 1.0  # Invert on HSV wheel
                        r, g, b = hsv_to_rgb(inverted_hue, 0.8, 0.7)  # Slightly dimmer for contrast
                    else:
                        # Normal maze colors
                        r, g, b = hsv_to_rgb(hue, 0.7, 1.0)
                    
                    graphics.set_pen(graphics.create_pen(r, g, b))
                else:
                    graphics.set_pen(graphics.create_pen(0, 0, 0))
                graphics.pixel(x, y)
        # draw entrance (bright yellow) - can be outside grid bounds
        if entrance_pos:
            ey, ex = entrance_pos  # (row, col)
            graphics.set_pen(graphics.create_pen(255, 255, 0))  # Bright yellow entrance
            # Clamp to screen bounds for drawing
            draw_x = max(0, min(cols-1, ex))
            draw_y = max(0, min(rows-1, ey))
            graphics.pixel(draw_x, draw_y)
        # draw solution path if present
        if solution:
            for row, col in solution:
                graphics.set_pen(graphics.create_pen(0, 80, 255))  # Blue
                graphics.pixel(col, row)
        # draw the drawer (maze solver avatar) as red dot
        if drawer:
            graphics.set_pen(graphics.create_pen(255, 0, 0))  # Bright red avatar
            graphics.pixel(drawer[1], drawer[0])
        # draw the exit (fade in as green) - can be outside grid bounds
        if exit_pos:
            ey, ex = exit_pos  # (row, col) 
            r, g, b = hsv_to_rgb(0.33, 1.0, exit_fade)
            graphics.set_pen(graphics.create_pen(int(r), int(g), int(b)))
            # Clamp to screen bounds for drawing
            draw_x = max(0, min(cols-1, ex))
            draw_y = max(0, min(rows-1, ey))
            graphics.pixel(draw_x, draw_y)

    while not interrupt_event.is_set():
        # maze grid: 0 = wall, 1 = path
        maze = [[0 for _ in range(cols)] for _ in range(rows)]
        stack = []

        # start at a random cell
        start = (random.randint(0, rows - 1), random.randint(0, cols - 1))  # (row, col)
        maze[start[0]][start[1]] = 1
        stack.append(start)

        t = 0.0

        # maze generation loop - show drawing process but not backtracking
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
                
                # Show the maze generation progress (only when carving new paths)
                graphics.set_pen(graphics.create_pen(0, 0, 0))
                graphics.clear()
                draw_maze(maze, t=t)
                gu.update(graphics)
                t += 0.03
                await uasyncio.sleep(0.01)  # Fast generation
            else:
                # Backtrack silently (don't show this step)
                stack.pop()

        # Brief pause to show the completed maze
        await uasyncio.sleep(0.3)

        # Create entrance and exit in unused border areas, as far apart as possible
        # Find all edge cells that connect to paths
        edge_connections = []
        
        # Top and bottom edges
        for x in range(cols):
            if maze[0][x]:  # path at top edge
                edge_connections.append(("top", x, (0, x)))
            if maze[rows-1][x]:  # path at bottom edge  
                edge_connections.append(("bottom", x, (rows-1, x)))
        
        # Left and right edges
        for y in range(rows):
            if maze[y][0]:  # path at left edge
                edge_connections.append(("left", y, (y, 0)))
            if maze[y][cols-1]:  # path at right edge
                edge_connections.append(("right", y, (y, cols-1)))
        
        if len(edge_connections) < 2:
            # Fallback if not enough connections
            entrance = start
            exit_in_maze = start
        else:
            # Find two edge connections that are furthest apart
            max_distance = -1
            best_entrance = None
            best_exit = None
            
            for i, (side1, pos1, conn1) in enumerate(edge_connections):
                for j, (side2, pos2, conn2) in enumerate(edge_connections[i+1:], i+1):
                    # Calculate distance between the two edge connections
                    dx = conn2[1] - conn1[1]
                    dy = conn2[0] - conn1[0]
                    distance = dx * dx + dy * dy
                    
                    if distance > max_distance:
                        max_distance = distance
                        best_entrance = (side1, pos1, conn1)
                        best_exit = (side2, pos2, conn2)
            
            # Create entrance and exit in the border areas outside the maze
            if best_entrance and best_exit:
                # Entrance: place in border outside the maze connection
                side1, pos1, conn1 = best_entrance
                if side1 == "top":
                    entrance = (-1, pos1)  # Above the maze
                    entrance_connection = conn1
                elif side1 == "bottom":
                    entrance = (rows, pos1)  # Below the maze
                    entrance_connection = conn1
                elif side1 == "left":
                    entrance = (pos1, -1)  # Left of the maze
                    entrance_connection = conn1
                else:  # right
                    entrance = (pos1, cols)  # Right of the maze
                    entrance_connection = conn1
                
                # Exit: place in border outside the maze connection
                side2, pos2, conn2 = best_exit
                if side2 == "top":
                    exit_in_maze = (-1, pos2)  # Above the maze
                    exit_connection = conn2
                elif side2 == "bottom":
                    exit_in_maze = (rows, pos2)  # Below the maze
                    exit_connection = conn2
                elif side2 == "left":
                    exit_in_maze = (pos2, -1)  # Left of the maze
                    exit_connection = conn2
                else:  # right
                    exit_in_maze = (pos2, cols)  # Right of the maze
                    exit_connection = conn2
            else:
                # Fallback
                entrance = start
                entrance_connection = start
                exit_in_maze = start
                exit_connection = start

        # Show entrance and fade in the exit
        for fade_step in range(12):
            if interrupt_event.is_set():
                break
            fade = (fade_step + 1) / 12.0
            graphics.set_pen(graphics.create_pen(0, 0, 0))
            graphics.clear()
            draw_maze(maze, entrance_pos=entrance, exit_pos=exit_in_maze, exit_fade=fade, t=t)
            gu.update(graphics)
            t += 0.03
            await uasyncio.sleep(0.04)

        # Find the optimal solution path for later blue line drawing (using BFS)
        # Use connection points instead of entrance/exit positions
        prev = {}
        queue = []
        queue.append(entrance_connection)
        visited = set()
        visited.add(entrance_connection)
        found = False
        while queue and not found and not interrupt_event.is_set():
            cy, cx = queue.pop(0)
            if (cy, cx) == exit_connection:
                found = True
                break
            for dy, dx in DIRS:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < rows and 0 <= nx < cols and maze[ny][nx] and (ny, nx) not in visited:
                    prev[(ny, nx)] = (cy, cx)
                    queue.append((ny, nx))
                    visited.add((ny, nx))

        # Reconstruct optimal solution path
        solution_path = []
        if found:
            node = exit_connection
            while node != entrance_connection:
                solution_path.append(node)
                if node not in prev:
                    solution_path = []
                    break
                node = prev[node]
            if solution_path:
                solution_path.append(entrance_connection)
                solution_path = solution_path[::-1]

        # Animate realistic maze solving with exploration and backtracking
        if found and not interrupt_event.is_set():
            avatar_pos = entrance_connection
            explored_path = [avatar_pos]  # Track where avatar has been
            avatar_stack = [avatar_pos]  # Stack for backtracking - represents current path
            visited_cells = {avatar_pos}
            
            while avatar_pos != exit_connection and not interrupt_event.is_set():
                # Get available neighbors (not visited, in bounds, and path)
                neighbors = []
                for dy, dx in DIRS:
                    ny, nx = avatar_pos[0] + dy, avatar_pos[1] + dx
                    if (0 <= ny < rows and 0 <= nx < cols and 
                        maze[ny][nx] and (ny, nx) not in visited_cells):
                        neighbors.append((ny, nx))
                
                if neighbors:
                    # Choose next move - slightly bias toward exit direction but still explore
                    if random.random() < 0.7 and len(neighbors) > 1:
                        # Sometimes choose randomly to make mistakes
                        next_pos = random.choice(neighbors)
                    else:
                        # Choose neighbor closest to exit
                        best_pos = neighbors[0]
                        best_dist = float('inf')
                        for ny, nx in neighbors:
                            dist = (nx - exit_connection[1])**2 + (ny - exit_connection[0])**2
                            if dist < best_dist:
                                best_dist = dist
                                best_pos = (ny, nx)
                        next_pos = best_pos
                    
                    avatar_pos = next_pos
                    explored_path.append(avatar_pos)
                    avatar_stack.append(avatar_pos)
                    visited_cells.add(avatar_pos)
                else:
                    # Dead end - backtrack
                    if len(avatar_stack) > 1:
                        avatar_stack.pop()  # Remove current position
                        avatar_pos = avatar_stack[-1]  # Go back to previous
                        explored_path.append(avatar_pos)  # Show the backtrack move
                    else:
                        break  # Shouldn't happen in a proper maze
                
                # Draw the avatar exploring with current path highlighted
                # Convert avatar_stack to set for faster lookup
                current_path_set = set(avatar_stack)
                graphics.set_pen(graphics.create_pen(0, 0, 0))
                graphics.clear()
                draw_maze(maze, drawer=avatar_pos, entrance_pos=entrance, exit_pos=exit_in_maze, exit_fade=1.0, t=t, explored_cells=current_path_set)
                gu.update(graphics)
                t += 0.02
                await uasyncio.sleep(0.02)  # Much faster avatar movement

        # Animate the blue optimal solution path appearing
        if solution_path and found:
            for i in range(len(solution_path)):
                if interrupt_event.is_set():
                    break
                graphics.set_pen(graphics.create_pen(0, 0, 0))
                graphics.clear()
                draw_maze(maze, solution=solution_path[:i+1], entrance_pos=entrance, exit_pos=exit_in_maze, exit_fade=1.0, t=t)
                gu.update(graphics)
                t += 0.03
                await uasyncio.sleep(0.01)  # Faster blue path animation

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
            if found and solution_path:
                for idx, (row, col) in enumerate(solution_path):
                    path_fade = min(1.0, fade + 0.3)
                    r, g, b = hsv_to_rgb(0.6, 1.0, path_fade)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(col, row)
            # keep entrance visible (yellow)
            if entrance:
                ey, ex = entrance
                draw_x = max(0, min(cols-1, ex))
                draw_y = max(0, min(rows-1, ey))
                graphics.set_pen(graphics.create_pen(int(255 * (fade + 0.3)), int(255 * (fade + 0.3)), 0))
                graphics.pixel(draw_x, draw_y)
            # keep exit visible (green)
            if exit_in_maze:
                ey, ex = exit_in_maze
                draw_x = max(0, min(cols-1, ex))
                draw_y = max(0, min(rows-1, ey))
                r, g, b = hsv_to_rgb(0.33, 1.0, fade + 0.3)
                graphics.set_pen(graphics.create_pen(int(r), int(g), int(b)))
                graphics.pixel(draw_x, draw_y)
            gu.update(graphics)
            await uasyncio.sleep(0.04)

        # slight pause before restarting
        for _ in range(30):
            if interrupt_event.is_set():
                break
            await uasyncio.sleep(0.03)
