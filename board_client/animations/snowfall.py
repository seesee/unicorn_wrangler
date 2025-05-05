import uasyncio
import math
import random
import utime

from animations.utils import hsv_to_rgb, fast_sin

async def run(graphics, gu, state, interrupt_event):
    # snowfall with overkill

    WIDTH, HEIGHT = graphics.get_bounds()
    NUM_FLAKES = 30
    MAX_SNOW_DEPTH_VISUAL = 4
    GROUND_Y_LIMIT = HEIGHT

    MIN_Z = 1.0
    MAX_Z = 8.0
    MIN_SPEED = 0.25
    MAX_SPEED = 0.7
    Z_TO_SPEED_FACTOR = 0.3

    MIN_BRIGHTNESS = 0.2
    MAX_BRIGHTNESS = 1.0
    BRIGHTNESS_POWER = 1.5

    WIND_STRENGTH_MAX = 0.3
    WIND_CHANGE_SPEED = 0.08
    DRIFT_FACTOR = 0.8

    SNOW_BRIGHTNESS_STEPS = 10
    DISAPPEAR_TRIGGER_LEVEL = 5

    SKY_TOP_HUE = 0.6
    SKY_TOP_SAT = 0.7
    SKY_TOP_VAL = 0.1
    SKY_BOTTOM_HUE = 0.55
    SKY_BOTTOM_SAT = 0.5
    SKY_BOTTOM_VAL = 0.2

    HILL_BASE_Y = HEIGHT * 0.4
    HILL_UNDULATION_AMP = HEIGHT * 0.2
    HILL_UNDULATION_FREQ = 0.15
    HILL_HUE = 0.33
    HILL_SAT = 0.5
    HILL_VAL_TOP = 0.18
    HILL_VAL_BOTTOM = 0.08

    WATER_HUE = 0.58
    WATER_SAT = 0.5
    WATER_VAL_MAX = 0.95
    WATER_VAL_MIN = 0.25

    SNOW_HUE = 0.6
    SNOW_SAT = 0.05

    def map_range(value, in_min, in_max, out_min, out_max, clamp=True):
        if in_max == in_min: return out_min if clamp else out_min
        t = (value - in_min) / (in_max - in_min)
        if clamp: t = max(0.0, min(1.0, t))
        return out_min + t * (out_max - out_min)

    def calculate_z_brightness(z):
        t = 1.0 - map_range(z, MIN_Z, MAX_Z, 0.0, 1.0)
        t_powered = t ** BRIGHTNESS_POWER
        brightness = MIN_BRIGHTNESS + t_powered * (MAX_BRIGHTNESS - MIN_BRIGHTNESS)
        return brightness

    def calculate_settled_snow_brightness(step_value):
        if step_value <= 0: return 0.0
        return map_range(step_value, 1, SNOW_BRIGHTNESS_STEPS, MIN_BRIGHTNESS, MAX_BRIGHTNESS)

    snow_flakes = []
    settled_snow = [[0 for _ in range(HEIGHT)] for _ in range(WIDTH)]
    global_time = 0.0
    current_wind = 0.0

    def reset_flake(index, flakes_list):
        z = random.uniform(MIN_Z, MAX_Z)
        speed_t = map_range(z, MIN_Z, MAX_Z, 1.0, 0.0)
        speed_variation = (MAX_SPEED - MIN_SPEED) * (1.0 - Z_TO_SPEED_FACTOR * speed_t)
        speed = MIN_SPEED + random.random() * speed_variation
        flake = [
            random.uniform(-1.0, WIDTH),
            random.uniform(-2.0, 0.0),
            z,
            speed,
            random.uniform(0, math.pi * 2)
        ]
        if index < len(flakes_list): flakes_list[index] = flake
        else: flakes_list.append(flake)

    for i in range(NUM_FLAKES):
        reset_flake(i, snow_flakes)

    last_time = utime.ticks_ms()

    while not interrupt_event.is_set():
        current_time = utime.ticks_ms()
        dt = utime.ticks_diff(current_time, last_time) / 1000.0
        last_time = current_time
        dt = min(dt, 0.1)
        frame_step = dt * 50
        global_time += dt

        current_wind = fast_sin(global_time * WIND_CHANGE_SPEED) * WIND_STRENGTH_MAX

        made_space = False
        for x in range(WIDTH):
            for y in range(HEIGHT - 1, 0, -1):
                if settled_snow[x][y] == SNOW_BRIGHTNESS_STEPS:
                    if settled_snow[x][y-1] == SNOW_BRIGHTNESS_STEPS:
                        settled_snow[x][y] = -1
        for x in range(WIDTH):
            for y in range(HEIGHT - 1, 1, -1):
                if settled_snow[x][y] == -1:
                    if settled_snow[x][y-2] >= DISAPPEAR_TRIGGER_LEVEL:
                        settled_snow[x][y] = 0
                        made_space = True
        if made_space:
            for x in range(WIDTH):
                lowest_empty = -1
                for y in range(HEIGHT - 1, -1, -1):
                    if settled_snow[x][y] == 0:
                        if lowest_empty == -1: lowest_empty = y
                    elif lowest_empty != -1:
                        settled_snow[x][lowest_empty] = settled_snow[x][y]
                        settled_snow[x][y] = 0
                        lowest_empty -= 1

        for i in range(len(snow_flakes)):
            flake = snow_flakes[i]
            flake[1] += flake[3] * frame_step
            drift = fast_sin(flake[4] + global_time * 0.5) * 0.1
            flake[0] += (current_wind * DRIFT_FACTOR + drift) * frame_step
            if flake[0] < -1.0: flake[0] += WIDTH + 1.0
            elif flake[0] >= WIDTH + 1.0: flake[0] -= WIDTH + 1.0
            ix = int(flake[0])
            iy = int(flake[1])
            if 0 <= ix < WIDTH:
                target_y = -1
                for check_y in range(HEIGHT - 1, -1, -1):
                    if 0 <= settled_snow[ix][check_y] < SNOW_BRIGHTNESS_STEPS:
                        target_y = check_y
                        break
                if target_y == -1: target_y = HEIGHT
                potential_land_y = target_y
                if iy >= potential_land_y and potential_land_y < GROUND_Y_LIMIT:
                    land_y = max(0, potential_land_y)
                    current_depth = 0
                    for check_y_depth in range(HEIGHT - 1, land_y - 1, -1):
                        if settled_snow[ix][check_y_depth] != 0:
                            current_depth += 1
                    if current_depth < MAX_SNOW_DEPTH_VISUAL:
                        current_val = settled_snow[ix][land_y]
                        if current_val == 0: settled_snow[ix][land_y] = 1
                        else: settled_snow[ix][land_y] += 1
                        reset_flake(i, snow_flakes)
                        continue
                    else:
                        reset_flake(i, snow_flakes)
                        continue
            if flake[1] >= HEIGHT:
                reset_flake(i, snow_flakes)
                continue

        for x in range(WIDTH):
            hill_sine_angle = x * HILL_UNDULATION_FREQ
            hill_offset = fast_sin(hill_sine_angle) * HILL_UNDULATION_AMP
            hill_start_y = int(HILL_BASE_Y + hill_offset)
            hill_start_y = max(0, min(HEIGHT - 1, hill_start_y))
            for y in range(HEIGHT):
                if y < hill_start_y:
                    t = y / max(1, hill_start_y)
                    hue = map_range(t, 0, 1, SKY_TOP_HUE, SKY_BOTTOM_HUE)
                    sat = map_range(t, 0, 1, SKY_TOP_SAT, SKY_BOTTOM_SAT)
                    val = map_range(t, 0, 1, SKY_TOP_VAL, SKY_BOTTOM_VAL)
                else:
                    hill_height_here = max(1, HEIGHT - hill_start_y)
                    t = (y - hill_start_y) / hill_height_here
                    hue = HILL_HUE
                    sat = HILL_SAT
                    val = map_range(t, 0, 1, HILL_VAL_TOP, HILL_VAL_BOTTOM)
                r, g, b = hsv_to_rgb(hue, sat, val)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(x, y)

        for x in range(WIDTH):
            for y in range(HEIGHT):
                snow_val = settled_snow[x][y]
                pen_set = False
                if snow_val == -1:
                    fill_level_above_2 = 0
                    if y >= 2:
                        val_above_2 = settled_snow[x][y-2]
                        fill_level_above_2 = max(0, val_above_2)
                    water_val = map_range(fill_level_above_2, 0, SNOW_BRIGHTNESS_STEPS, WATER_VAL_MAX, WATER_VAL_MIN)
                    r, g, b = hsv_to_rgb(WATER_HUE, WATER_SAT, water_val)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    pen_set = True
                elif snow_val > 0:
                    brightness = calculate_settled_snow_brightness(snow_val)
                    r, g, b = hsv_to_rgb(SNOW_HUE, SNOW_SAT, brightness)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    pen_set = True
                if pen_set:
                    graphics.pixel(x, y)

        for flake in snow_flakes:
            ix = int(flake[0])
            iy = int(flake[1])
            if 0 <= ix < WIDTH and 0 <= iy < HEIGHT:
                brightness = calculate_z_brightness(flake[2])
                val_int = int(brightness * 255)
                val_int = max(0, min(255, val_int))
                graphics.set_pen(graphics.create_pen(val_int, val_int, val_int))
                graphics.pixel(ix, iy)

        gu.update(graphics)
        await uasyncio.sleep(0.04)
