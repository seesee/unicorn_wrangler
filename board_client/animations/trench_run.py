import uasyncio
import utime
import random
import micropython

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT, MODEL
from uw.logger import log

# Pre-calculated 3x3 digit patterns (same as original)
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

@micropython.native
def draw_small_digit(graphics, digit, x, y, color_pen):
    if 0 <= digit <= 9:
        pattern = DIGITS_3x3[digit]
        graphics.set_pen(color_pen)
        for row in range(3):
            line = pattern[row]
            py = y + row
            if 0 <= py < HEIGHT:
                for col in range(3):
                    if line[col] == "#":
                        px = x + col
                        if 0 <= px < WIDTH:
                            graphics.pixel(px, py)

@micropython.native
def draw_countdown(graphics, value, color_pen, y=1):
    num_str = f"{value:03d}"
    total_w = 11
    start_x = (WIDTH - total_w) >> 1
    for i in range(3):
        digit = int(num_str[i])
        x_pos = start_x + (i << 2)
        draw_small_digit(graphics, digit, x_pos, y, color_pen)

async def run(graphics, gu, state, interrupt_event):
    log("Trench run animation started", "INFO")
    MAX_RUNTIME = getattr(state, "max_runtime_s", 60)
    LAUNCH_SECONDS_BEFORE_END = 10

    SEGMENTS = 14 if MODEL == "cosmic" else 18
    SPEED = 0.25

    vanishing_x = WIDTH >> 1
    vanishing_y = 5 + ((HEIGHT - 5) >> 1)

    if (MODEL == "galactic") or (WIDTH > HEIGHT * 2):
        trench_width = 3.0
    else:
        trench_width = 1.5
    trench_height = 1.5
    grid_spacing = 1.2

    black_pen = graphics.create_pen(0, 0, 0)
    red_pen = graphics.create_pen(255, 0, 0)
    blue_pen = graphics.create_pen(0, 180, 255)
    white_pen = graphics.create_pen(255, 255, 255)
    explosion_orange_pen = graphics.create_pen(255, 150, 0)
    explosion_yellow_pen = graphics.create_pen(255, 220, 0)
    explosion_yellow_pen = graphics.create_pen(255, 220, 0)

    brightness_pens = []
    edge_pens = []
    outline_pens = []
    for i in range(SEGMENTS):
        distance_factor = i / SEGMENTS
        brightness_factor = max(0.05, (1.0 - distance_factor) ** 2.5)
        brightness = max(15, min(255, int(255 * brightness_factor)))
        brightness_pens.append(graphics.create_pen(brightness, brightness, brightness))

        edge_brightness_factor = max(0.1, (1.0 - distance_factor) ** 2.0)
        edge_brightness = max(20, min(255, int(200 * edge_brightness_factor)))
        edge_pens.append(graphics.create_pen(edge_brightness, edge_brightness, edge_brightness))

        outline_brightness = max(30, min(255, int(255 * edge_brightness_factor)))
        outline_pens.append(graphics.create_pen(int(outline_brightness * 0.7),
                                               int(outline_brightness * 0.7),
                                               int(outline_brightness * 0.7)))

    towers = []
    explosion_active = False
    explosion_start = 0
    missiles = []
    lasers = []
    missile_hang = False
    missile_hang_time = 0.0
    missile_hang_duration = 0.5
    explosion_total_duration = 4.0

    start_time = utime.ticks_ms()
    total_countdown_time = MAX_RUNTIME - LAUNCH_SECONDS_BEFORE_END
    countdown_start = min(200, max(100, int(total_countdown_time / 0.2)))
    countdown = countdown_start
    countdown_interval = total_countdown_time / countdown_start if countdown_start > 0 else 1
    last_countdown_update = utime.ticks_ms()

    @micropython.native
    def project_flight(x, y, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=False):
        if wall_mode:
            x_rot = x * cos_roll - y * sin_roll
            y_rot = y
        else:
            x_rot = x * cos_roll - y * sin_roll
            y_rot = x * sin_roll + y * cos_roll
        y_with_altitude = y_rot - altitude
        y_pitched = y_with_altitude * cos_pitch
        z_pitched = z + y_with_altitude * sin_pitch
        z_final = max(0.1, z_pitched)
        scale = (HEIGHT * 1.1) / (z_final * trench_height)
        screen_x = vanishing_x + int((x_rot + shake_x) * scale)
        screen_y = vanishing_y - int((y_pitched + shake_y) * scale)
        return screen_x, screen_y

    current_offset = 0.0
    elapsed = 0.0

    while not interrupt_event.is_set():
        current_time = utime.ticks_ms()
        elapsed = (utime.ticks_diff(current_time, start_time)) * 0.001

        base_roll = fast_sin(elapsed * 1.2) * 0.08 + fast_sin(elapsed * 0.5) * 0.04
        urgency_factor = max(0.3, 1.0 - (countdown / countdown_start)) if countdown_start > 0 else 0.3
        banking = fast_sin(elapsed * 0.7) * 0.15 * urgency_factor
        roll_angle = base_roll + banking
        pitch_base = fast_sin(elapsed * 0.9) * 0.12 * urgency_factor
        pitch_dodge = fast_sin(elapsed * 2.1) * 0.06 * urgency_factor
        pitch_angle = pitch_base + pitch_dodge
        altitude_base = 0.4 + fast_sin(elapsed * 0.6) * 0.3
        altitude_evasive = fast_sin(elapsed * 1.8) * 0.4 * urgency_factor
        altitude = max(0.1, altitude_base + abs(altitude_evasive))
        cos_roll = fast_cos(roll_angle)
        sin_roll = fast_sin(roll_angle)
        cos_pitch = fast_cos(pitch_angle)
        sin_pitch = fast_sin(pitch_angle)
        shake_intensity = 1.0 + urgency_factor * 1.5
        shake_x = fast_sin(elapsed * 2.7) * 0.04 * shake_intensity
        shake_y = fast_sin(elapsed * 1.9) * 0.03 * shake_intensity

        graphics.set_pen(black_pen)
        graphics.clear()

        if not explosion_active:
            current_offset = (current_offset + SPEED) % grid_spacing

            # Draw floor grid lines
            for i in range(SEGMENTS):
                z = 0.5 + i * grid_spacing - (current_offset % grid_spacing)
                pen_idx = min(i, len(brightness_pens) - 1)
                px_left, py_left = project_flight(-trench_width, 0.0, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y)
                px_right, py_right = project_flight(trench_width, 0.0, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y)
                graphics.set_pen(brightness_pens[pen_idx])
                graphics.line(px_left, py_left, px_right, py_right)
                for side in [-trench_width, trench_width]:
                    if MODEL == "cosmic" and i % 2 == 1:
                        continue
                    px0, py0 = project_flight(side, 0.0, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    px1, py1 = project_flight(side, trench_height, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    graphics.set_pen(brightness_pens[pen_idx])
                    graphics.line(px0, py0, px1, py1)

            # Draw top edges of the trench
            for side in [-trench_width, trench_width]:
                prev_px, prev_py = None, None
                for i in range(SEGMENTS):
                    z = 0.5 + i * grid_spacing - (current_offset % grid_spacing)
                    px, py = project_flight(side, trench_height, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    if prev_px is not None:
                        pen_idx = min(i, len(edge_pens) - 1)
                        graphics.set_pen(edge_pens[pen_idx])
                        graphics.line(prev_px, prev_py, px, py)
                    prev_px, prev_py = px, py

            # Draw outer landscape
            outer_landscape_width = trench_width * 1.8
            for i in range(SEGMENTS):
                z = 0.5 + i * grid_spacing - (current_offset % grid_spacing)
                pen_idx = min(i, len(outline_pens) - 1)
                for side in [-1, 1]:
                    inner_x = side * trench_width
                    inner_px, inner_py = project_flight(inner_x, trench_height, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    outer_x = side * outer_landscape_width
                    outer_px, outer_py = project_flight(outer_x, trench_height, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    graphics.set_pen(outline_pens[pen_idx])
                    graphics.line(inner_px, inner_py, outer_px, outer_py)

            # Tower spawning
            spawn_rate = 0.04 + urgency_factor * 0.02
            if random.random() < spawn_rate and len(towers) < 4:
                side = -trench_width if random.random() < 0.5 else trench_width
                tower = {
                    "z": 0.5 + SEGMENTS * grid_spacing,
                    "side": side,
                    "height": random.uniform(0.5, 1.0) * trench_height,
                    "hue": random.random(),
                }
                towers.append(tower)
                log(f"Tower spawned: {tower}", "DEBUG")

            # Draw towers
            for tower in towers:
                tower["z"] -= SPEED
                if tower["z"] > 0:
                    px0, py0 = project_flight(tower["side"], 0.0, tower["z"], cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    px1, py1 = project_flight(tower["side"], tower["height"], tower["z"], cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    distance_factor = tower["z"] / (SEGMENTS * grid_spacing)
                    brightness_factor = max(0.1, (1.0 - distance_factor) ** 2.0)
                    value = max(0.12, min(1.0, brightness_factor))
                    r, g, b = hsv_to_rgb(tower["hue"], 0.85, value)
                    tower_dynamic_pen = graphics.create_pen(int(r), int(g), int(b))
                    graphics.set_pen(tower_dynamic_pen)
                    graphics.line(px0, py0, px1, py1)
            towers = [t for t in towers if t["z"] > 0]

            # Missile logic
            if not missile_hang and random.random() < 0.02 and len(missiles) < 1 and countdown < 10:
                missile = {"z": 0.5, "speed": SPEED * 0.5, "dipping": False, "dip_progress": 0.0}
                missiles.append(missile)
                log(f"Missile spawned: {missile}", "DEBUG")

            for missile in missiles:
                if not missile["dipping"]:
                    missile["z"] += missile["speed"]
                    log(f"Missile z updated: {missile['z']}", "DEBUG")
                    if missile["z"] >= SEGMENTS * grid_spacing - 1.0:
                        missile["dipping"] = True
                        missile["dip_progress"] = 0.0
                        missile_hang = True
                        missile_hang_time = elapsed
                        log("Missile reached end, starting hang/dip", "DEBUG")
                else:
                    missile["dip_progress"] += 0.04
                    log(f"Missile dipping, progress: {missile['dip_progress']}", "DEBUG")

                missile_height = 0.5 - (missile["dip_progress"] * 0.3 if missile["dipping"] else 0.0)
                px, py = project_flight(0.0, missile_height,
                                        min(missile["z"], SEGMENTS * grid_spacing - 1.0),
                                        cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, 0, 0)
                graphics.set_pen(blue_pen)
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.pixel(px, py)

            if missile_hang and elapsed - missile_hang_time > missile_hang_duration:
                missiles.clear()
                missile_hang = False
                explosion_active = True
                explosion_start = utime.ticks_ms()
                log("Explosion triggered!", "INFO")

            # Laser effects
            laser_spawn_rate = 0.04 + urgency_factor * 0.02
            if random.random() < laser_spawn_rate and len(lasers) < 2 and towers:
                tower = random.choice(towers)
                target_side = -tower["side"]
                laser = {
                    "source_tower": tower,
                    "target_side": target_side,
                    "z": tower["z"],
                    "progress": 0.0,
                }
                lasers.append(laser)
                log(f"Laser spawned from tower: {tower}", "DEBUG")

            for laser in lasers:
                laser["progress"] += 0.12
                prog = min(1.0, laser["progress"])
                tower = laser["source_tower"]
                start_x, start_y = project_flight(
                    tower["side"], tower["height"], tower["z"],
                    cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True
                )
                end_x, end_y = project_flight(
                    laser["target_side"], tower["height"], tower["z"],
                    cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True
                )
                curr_x = int(start_x + (end_x - start_x) * prog)
                curr_y = int(start_y + (end_y - start_y) * prog)
                tower_hue = tower["hue"]
                r, g, b = hsv_to_rgb(tower_hue, 1.0, 1.0)
                laser_pen = graphics.create_pen(int(r), int(g), int(b))
                graphics.set_pen(laser_pen)
                graphics.line(start_x, start_y, curr_x, curr_y)
            lasers = [l for l in lasers if l["progress"] < 1.0]

            # Countdown update
            if countdown > 0 and not missile_hang:
                now = utime.ticks_ms()
                if utime.ticks_diff(now, last_countdown_update) >= int(countdown_interval * 1000):
                    countdown -= 1
                    last_countdown_update = now

            draw_countdown(graphics, countdown, red_pen, y=1)

        else:
            log("Explosion animation running", "DEBUG")
            explosion_time = (utime.ticks_ms() - explosion_start) * 0.001
            if explosion_time < 0.2:
                if int(explosion_time * 20) % 2 == 0:
                    graphics.set_pen(white_pen)
                else:
                    graphics.set_pen(explosion_yellow_pen)
                graphics.clear()
            else:
                graphics.set_pen(black_pen)
                graphics.clear()
                center_x = WIDTH >> 1
                center_y = HEIGHT >> 1
                tumble_x = int(fast_sin(explosion_time * 4.0) * 3)
                tumble_y = int(fast_cos(explosion_time * 3.0) * 3)
                center_x += tumble_x
                center_y += tumble_y
                for i in range(3):
                    radius = int((explosion_time - i * 0.3) * min(WIDTH, HEIGHT) * 0.4)
                    if radius > 0:
                        if i == 0:
                            ring_pen = white_pen
                        elif i == 1:
                            ring_pen = explosion_yellow_pen
                        else:
                            ring_pen = explosion_orange_pen
                        graphics.set_pen(ring_pen)
                        for angle in range(0, 360, 15):
                            rad = angle * 0.0174533
                            x = center_x + int(fast_cos(rad) * radius)
                            y = center_y + int(fast_sin(rad) * radius)
                            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                                graphics.pixel(x, y)
                num_lines = 16
                length = int(explosion_time * min(WIDTH, HEIGHT) * 0.5)
                graphics.set_pen(explosion_yellow_pen)
                for i in range(num_lines):
                    angle = (i / num_lines) * 6.28318
                    end_x = center_x + int(fast_cos(angle) * length)
                    end_y = center_y + int(fast_sin(angle) * length)
                    graphics.line(center_x, center_y, end_x, end_y)
                if explosion_time > explosion_total_duration:
                    log("Explosion animation complete, exiting animation", "INFO")
                    return

        gu.update(graphics)
        log(f"Elapsed: {elapsed:.2f}, missile_hang: {missile_hang}, explosion_active: {explosion_active}, missiles: {len(missiles)}", "DEBUG")
        await uasyncio.sleep(0.02)

    log("Trench run animation interrupted", "INFO")
