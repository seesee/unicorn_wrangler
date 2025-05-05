import uasyncio
import math
import random
import utime

from uw.hardware import WIDTH, HEIGHT

# alien numbers due to space constraints
DIGITS_3x3 = [
    ["###", "# #", "###"],  # 0
    [" # ", " # ", " # "],  # 1
    ["###", " # ", "###"],  # 2
    ["# #", " ##", "# #"],  # 3
    ["# #", "###", "  #"],  # 4
    ["###", " # ", "###"],  # 5
    [" ##", "#  ", "## "],  # 6
    ["###", "  #", "  #"],  # 7
    ["# #", "# #", "# #"],  # 8
    ["###", "#  ", "#  "],  # 9
]

def draw_small_digit(graphics, digit, x, y, color):
    # draw individual countdown/distance "digits"
    if 0 <= digit <= 9:
        pattern = DIGITS_3x3[digit]
        for row, line in enumerate(pattern):
            for col, ch in enumerate(line):
                if ch == "#":
                    px = x + col
                    py = y + row
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        graphics.set_pen(color)
                        graphics.pixel(px, py)

def draw_countdown(graphics, value, color, y=1):
    # draw full countdown with height offset
    num_str = str(value)
    num_str = "0" * (3 - len(num_str)) + num_str
    digit_w = 3
    digit_h = 3
    spacing = 1
    total_w = 3 * digit_w + 2 * spacing
    start_x = (WIDTH - total_w) // 2
    for i, ch in enumerate(num_str):
        draw_small_digit(graphics, int(ch), start_x + i * (digit_w + spacing), y, color)

async def run(graphics, gu, state, interrupt_event):
    MAX_RUNTIME = getattr(state, "max_runtime_s", 60)
    LAUNCH_SECONDS_BEFORE_END = 10

    IS_WIDE = WIDTH > HEIGHT * 1.5
    SEGMENTS = 12
    SPEED = 0.25 if IS_WIDE else 0.2

    vanishing_x = WIDTH // 2
    vanishing_y = HEIGHT // 2 + HEIGHT // 4  # lower vanishing point

    grid_spacing = 2.0
    trench_width = 0.6
    wall_height = 0.8

    towers = []
    lasers = []

    torpedo_launched = False
    torpedo_z = 0.5
    torpedo_x = 0.0
    explosion_active = False
    explosion_start = 0

    # setup countdown
    start_time = utime.ticks_ms()
    total_countdown_time = MAX_RUNTIME - LAUNCH_SECONDS_BEFORE_END
    min_count = 100
    max_count = 200
    # pick a suitable countdown starting point 
    for candidate in range(max_count, min_count - 1, -1):
        if total_countdown_time / candidate >= 0.2:
            countdown_start = candidate
            break
    else:
        countdown_start = min_count
    countdown = countdown_start
    countdown_interval = total_countdown_time / countdown_start if countdown_start > 0 else 1
    last_countdown_update = utime.ticks_ms()

    def project(x, y, z):
        z = max(0.1, z)
        scale = 8.0 / z
        screen_x = vanishing_x + int(x * scale * WIDTH * 0.4)
        screen_y = vanishing_y + int(-y * scale * HEIGHT * 0.3)
        return screen_x, screen_y

    current_offset = 0.0

    while not interrupt_event.is_set():
        current_time = utime.ticks_ms()
        elapsed = utime.ticks_diff(current_time, start_time) / 1000.0
        time_remaining = MAX_RUNTIME - elapsed

        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        if not explosion_active:
            current_offset = (current_offset + SPEED) % grid_spacing

            # floor corners (bottom of display)
            floor_y = HEIGHT - 2
            left_floor_x = 0
            right_floor_x = WIDTH - 1

            # project trench floor corners
            z_far = 0.5 + (SEGMENTS - 1) * grid_spacing - (current_offset % grid_spacing)
            left_trench_far_x, left_trench_far_y = project(-trench_width, 0.0, z_far)
            right_trench_far_x, right_trench_far_y = project(trench_width, 0.0, z_far)

            # project closest trench floor corners to bottom
            z_near = 0.5
            left_trench_x, left_trench_y = project(-trench_width, 0.0, z_near)
            right_trench_x, right_trench_y = project(trench_width, 0.0, z_near)

            # draw lower floor (bottom of display)
            graphics.set_pen(graphics.create_pen(180, 180, 180))
            graphics.line(left_floor_x, floor_y, right_floor_x, floor_y)

            # connect trench wall to lower floor corners
            graphics.line(left_trench_far_x, left_trench_far_y, left_floor_x, floor_y)
            graphics.line(right_trench_far_x, right_trench_far_y, right_floor_x, floor_y)

            # connect trench floor to lower floor corners (for speed lines)
            graphics.line(left_trench_x, left_trench_y, left_floor_x, floor_y)
            graphics.line(right_trench_x, right_trench_y, right_floor_x, floor_y)

            # draw trench grid lines (with gap in the middle)
            for i in range(SEGMENTS):
                z_pos = 0.5 + i * grid_spacing - (current_offset % grid_spacing)
                left_x1, left_y1 = project(-trench_width, 0.0, z_pos)
                left_x2, left_y2 = project(-0.15, 0.0, z_pos)
                right_x1, right_y1 = project(0.15, 0.0, z_pos)
                right_x2, right_y2 = project(trench_width, 0.0, z_pos)
                brightness = max(60, int(255 * (1.0 - i / SEGMENTS)))
                graphics.set_pen(graphics.create_pen(brightness, brightness, brightness))
                graphics.line(left_x1, left_y1, left_x2, left_y2)
                graphics.line(right_x1, right_y1, right_x2, right_y2)

                # connect outer grid lines to lower floor
                if i == 0:
                    graphics.line(left_x1, left_y1, left_floor_x, floor_y)
                    graphics.line(right_x2, right_y2, right_floor_x, floor_y)
                # Connect distant wall to lower floor
                if i == SEGMENTS - 1:
                    graphics.line(left_x1, left_y1, left_floor_x, floor_y)
                    graphics.line(right_x2, right_y2, right_floor_x, floor_y)

            # draw side walls (vertical lines)
            for i in range(SEGMENTS):
                z_pos = 0.5 + i * grid_spacing - (current_offset % grid_spacing)
                left_bottom_x, left_bottom_y = project(-trench_width, 0.0, z_pos)
                left_top_x, left_top_y = project(-trench_width, wall_height, z_pos)
                right_bottom_x, right_bottom_y = project(trench_width, 0.0, z_pos)
                right_top_x, right_top_y = project(trench_width, wall_height, z_pos)
                brightness = max(60, int(255 * (1.0 - i / SEGMENTS)))
                graphics.set_pen(graphics.create_pen(brightness, brightness, brightness))
                graphics.line(left_bottom_x, left_bottom_y, left_top_x, left_top_y)
                graphics.line(right_bottom_x, right_bottom_y, right_top_x, right_top_y)

                # connect outer wall lines to lower floor
                if i == 0:
                    graphics.line(left_bottom_x, left_bottom_y, left_floor_x, floor_y)
                    graphics.line(right_bottom_x, right_bottom_y, right_floor_x, floor_y)
                if i == SEGMENTS - 1:
                    graphics.line(left_bottom_x, left_bottom_y, left_floor_x, floor_y)
                    graphics.line(right_bottom_x, right_bottom_y, right_floor_x, floor_y)

            # draw wall lines along trench length (bottom and top edges)
            for side in [-1, 1]:
                x_pos = side * trench_width
                prev_x, prev_y = None, None
                for i in range(SEGMENTS):
                    z_pos = 0.5 + i * grid_spacing - (current_offset % grid_spacing)
                    x, y = project(x_pos, 0.0, z_pos)
                    if prev_x is not None:
                        brightness = max(60, int(255 * (1.0 - i / SEGMENTS)))
                        graphics.set_pen(graphics.create_pen(brightness, brightness, brightness))
                        graphics.line(prev_x, prev_y, x, y)
                    prev_x, prev_y = x, y
                prev_x, prev_y = None, None
                for i in range(SEGMENTS):
                    z_pos = 0.5 + i * grid_spacing - (current_offset % grid_spacing)
                    x, y = project(x_pos, wall_height, z_pos)
                    if prev_x is not None:
                        brightness = max(60, int(255 * (1.0 - i / SEGMENTS)))
                        graphics.set_pen(graphics.create_pen(brightness, brightness, brightness))
                        graphics.line(prev_x, prev_y, x, y)
                    prev_x, prev_y = x, y

            # add random towers to sides todo: improve
            if random.random() < 0.05 and len(towers) < 6:
                side = random.choice([-1, 1])
                towers.append({
                    "z": 0.5 + SEGMENTS * grid_spacing,
                    "x": side * trench_width * 0.9,
                    "height": random.uniform(0.2, 0.4) * wall_height,
                    "hit": False
                })

            # update/draw towers
            for tower in towers:
                tower["z"] -= SPEED
                if tower["z"] > 0:
                    tx_bottom, ty_bottom = project(tower["x"], 0.0, tower["z"])
                    tx_top, ty_top = project(tower["x"], tower["height"], tower["z"])
                    if tower["hit"]:
                        graphics.set_pen(graphics.create_pen(255, 50, 50))
                    else:
                        brightness = max(80, int(255 * (1.0 - tower["z"] / (SEGMENTS * grid_spacing))))
                        graphics.set_pen(graphics.create_pen(brightness, brightness, brightness))
                    graphics.line(tx_bottom, ty_bottom, tx_top, ty_top)
            towers = [t for t in towers if t["z"] > 0]

            # create random enemy laser fire
            if random.random() < 0.04 and len(lasers) < 2:
                side = random.choice([-1, 1])
                z_pos = 0.5 + random.uniform(grid_spacing * 2, grid_spacing * 6)
                lasers.append({
                    "start_x": side * trench_width * 0.9,
                    "end_x": -side * trench_width * 0.9,
                    "z": z_pos,
                    "progress": 0.0
                })

            # update/draw lasers
            for laser in lasers:
                laser["progress"] += 0.1
                prog = min(1.0, laser["progress"])
                start_x, start_y = project(laser["start_x"], 0.3, laser["z"])
                current_x = laser["start_x"] + (laser["end_x"] - laser["start_x"]) * prog
                current_point_x, current_point_y = project(current_x, 0.3, laser["z"])
                graphics.set_pen(graphics.create_pen(255, 30, 30))
                graphics.line(start_x, start_y, current_point_x, current_point_y)
            lasers = [l for l in lasers if l["progress"] < 1.0]

            # update countdown timer
            if not torpedo_launched and countdown > 0:
                now = utime.ticks_ms()
                if utime.ticks_diff(now, last_countdown_update) >= int(countdown_interval * 1000):
                    countdown -= 1
                    last_countdown_update = now

            # launch torpedo when countdown reaches 0
            if countdown <= 0 and not torpedo_launched:
                torpedo_launched = True
                torpedo_z = 0.5
                torpedo_x = 0.0

            # update/draw torpedo
            if torpedo_launched:
                torpedo_z += SPEED * 1.5
                tx, ty = project(torpedo_x, 0.3, torpedo_z)
                graphics.set_pen(graphics.create_pen(0, 180, 255))
                graphics.pixel(tx, ty)
                for i in range(1, 4):
                    trail_z = torpedo_z + (i * 0.2)
                    trail_x, trail_y = project(torpedo_x, 0.3, trail_z)
                    brightness = 180 - i * 40
                    graphics.set_pen(graphics.create_pen(0, brightness, 255))
                    graphics.pixel(trail_x, trail_y)
                for tower in towers:
                    if abs(tower["z"] - torpedo_z) < 0.3 and abs(tower["x"] - torpedo_x) < 0.2:
                        tower["hit"] = True
                if torpedo_z >= 0.5 + SEGMENTS * grid_spacing:
                    explosion_active = True
                    explosion_start = current_time

            # draw the countdown display
            color = graphics.create_pen(255, 0, 0)
            draw_countdown(graphics, countdown, color, y=1)

        else:
            # bullseye the womp-rat
            explosion_time = utime.ticks_diff(current_time, explosion_start) / 1000.0
            if explosion_time < 0.2:
                graphics.set_pen(graphics.create_pen(255, 255, 255))
                graphics.clear()
            else:
                center_x = WIDTH // 2
                center_y = HEIGHT // 2
                for i in range(3):
                    radius = int((explosion_time - i * 0.3) * min(WIDTH, HEIGHT) * 0.4)
                    if radius <= 0:
                        continue
                    prev_x, prev_y = None, None
                    for angle in range(0, 370, 15):
                        rad = math.radians(angle)
                        x = center_x + int(math.cos(rad) * radius)
                        y = center_y + int(math.sin(rad) * radius)
                        if prev_x is not None:
                            if i == 0:
                                graphics.set_pen(graphics.create_pen(255, 255, 255))
                            elif i == 1:
                                graphics.set_pen(graphics.create_pen(255, 150, 0))
                            else:
                                graphics.set_pen(graphics.create_pen(255, 50, 0))
                            graphics.line(prev_x, prev_y, x, y)
                        prev_x, prev_y = x, y
                num_lines = 16
                for i in range(num_lines):
                    angle = (i / num_lines) * 2 * math.pi
                    length = int(explosion_time * min(WIDTH, HEIGHT) * 0.5)
                    end_x = center_x + int(math.cos(angle) * length)
                    end_y = center_y + int(math.sin(angle) * length)
                    graphics.set_pen(graphics.create_pen(255, 220, 0))
                    graphics.line(center_x, center_y, end_x, end_y)
                if explosion_time > 2.0:
                    break

        gu.update(graphics)
        if elapsed > MAX_RUNTIME + 3:
            break
        await uasyncio.sleep(0.02)

