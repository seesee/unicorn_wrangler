import uasyncio
import math
import random

from animations.utils import hsv_to_rgb, fast_sin

async def run(graphics, gu, state, interrupt_event):
    # starfield effect
    WIDTH, HEIGHT = graphics.get_bounds()
    NUM_FG_STARS = 60
    NUM_BG_STARS = 40
    CENTER_X = WIDTH / 2.0
    CENTER_Y = HEIGHT / 2.0
    PERSPECTIVE_FACTOR_Z = 5.0

    FG_MIN_STAR_SPEED = 0.15
    FG_MAX_STAR_SPEED = 0.55
    FG_MIN_Z = 0.1
    FG_MAX_Z_INITIAL = 20.0
    FG_RESET_Z_MIN = 15.0
    FG_RESET_Z_MAX = 20.0
    FG_MIN_BASE_BRIGHTNESS = 0.6
    FG_MAX_BASE_BRIGHTNESS = 1.0
    FG_MIN_DEPTH_BRIGHTNESS_MULT = 0.05
    FG_DEPTH_BRIGHTNESS_POWER = 2.0

    BG_MIN_BRIGHTNESS = 0.03
    BG_MAX_BRIGHTNESS = 0.15
    BG_HUE = 0.65
    BG_SATURATION = 0.9

    ENABLE_TWINKLE = True
    TWINKLE_SPEED = 1.5
    TWINKLE_DEPTH = 0.4

    PROB_WHITE = 0.80
    PROB_BLUE = 0.12
    PROB_RED = 0.08
    BLUE_HUE_MIN = 0.55
    BLUE_HUE_MAX = 0.70
    RED_HUE_MIN = 0.0
    RED_HUE_MAX = 0.08
    WHITE_SAT_MIN = 0.0
    WHITE_SAT_MAX = 0.15
    COLOR_SAT_MIN = 0.7
    COLOR_SAT_MAX = 1.0

    ENABLE_SWIRL = True
    BASE_SWIRL_STRENGTH = 0.003
    SWIRL_VARIATION_AMP = 0.005
    SWIRL_VARIATION_SPEED = 0.1

    BACKGROUND_HUE = 0.65
    BACKGROUND_SAT = 0.8
    BACKGROUND_VAL = 0.05

    def create_fg_star():
        x = random.uniform(-CENTER_X * 1.5, CENTER_X * 1.5)
        y = random.uniform(-CENTER_Y * 1.5, CENTER_Y * 1.5)
        z = random.uniform(FG_MIN_Z + 1.0, FG_MAX_Z_INITIAL)
        base_brightness = random.uniform(FG_MIN_BASE_BRIGHTNESS, FG_MAX_BASE_BRIGHTNESS)
        speed = random.uniform(FG_MIN_STAR_SPEED, FG_MAX_STAR_SPEED)
        twinkle_phase = random.uniform(0, math.pi * 2)
        use_twinkle = ENABLE_TWINKLE

        color_roll = random.random()
        if color_roll < PROB_WHITE:
            hue = random.random()
            saturation = random.uniform(WHITE_SAT_MIN, WHITE_SAT_MAX)
        elif color_roll < PROB_WHITE + PROB_BLUE:
            hue = random.uniform(BLUE_HUE_MIN, BLUE_HUE_MAX)
            saturation = random.uniform(COLOR_SAT_MIN, COLOR_SAT_MAX)
        else:
            if random.random() < 0.5:
                hue = random.uniform(0.0, RED_HUE_MAX)
            else:
                hue = random.uniform(1.0 - RED_HUE_MAX, 1.0)
            saturation = random.uniform(COLOR_SAT_MIN, COLOR_SAT_MAX)

        return [x, y, z, base_brightness, hue, saturation, speed, twinkle_phase, use_twinkle]

    def create_bg_star_pixels(num):
        pixels = []
        for _ in range(num):
            sx = random.randint(0, WIDTH - 1)
            sy = random.randint(0, HEIGHT - 1)
            val = random.uniform(BG_MIN_BRIGHTNESS, BG_MAX_BRIGHTNESS)
            r, g, b = hsv_to_rgb(BG_HUE, BG_SATURATION, val)
            pixels.append((sx, sy, r, g, b))
        return pixels

    fg_stars = [create_fg_star() for _ in range(NUM_FG_STARS)]
    bg_star_pixels = create_bg_star_pixels(NUM_BG_STARS)
    global_time = 0.0

    z_range = FG_RESET_Z_MAX - FG_MIN_Z
    if z_range <= 0:
        z_range = 1.0

    bg_r, bg_g, bg_b = hsv_to_rgb(BACKGROUND_HUE, BACKGROUND_SAT, BACKGROUND_VAL)
    BACKGROUND_PEN = graphics.create_pen(bg_r, bg_g, bg_b)

    while not interrupt_event.is_set():
        dt = 0.03
        global_time += dt

        graphics.set_pen(BACKGROUND_PEN)
        graphics.clear()

        for sx, sy, r, g, b in bg_star_pixels:
            pen = graphics.create_pen(r, g, b)
            graphics.set_pen(pen)
            graphics.pixel(sx, sy)

        current_swirl = 0.0
        if ENABLE_SWIRL:
            swirl_variation = fast_sin(global_time * SWIRL_VARIATION_SPEED) * SWIRL_VARIATION_AMP
            current_swirl = BASE_SWIRL_STRENGTH + swirl_variation

        for i in range(len(fg_stars)):
            star = fg_stars[i]
            star[2] -= star[6] * dt * 50

            if ENABLE_SWIRL and current_swirl != 0:
                x0, y0 = star[0], star[1]
                swirl_amount = current_swirl * dt * 100
                star[0] += -y0 * swirl_amount
                star[1] += x0 * swirl_amount

            reset_star = False
            current_z = star[2]
            if current_z <= FG_MIN_Z:
                reset_star = True
            else:
                max_proj_dist_sq = (WIDTH * 2)**2 + (HEIGHT * 2)**2
                proj_factor_est = PERSPECTIVE_FACTOR_Z / current_z
                proj_x_est = CENTER_X + star[0] * proj_factor_est
                proj_y_est = CENTER_Y + star[1] * proj_factor_est
                dist_from_center_sq = (proj_x_est - CENTER_X)**2 + (proj_y_est - CENTER_Y)**2
                if dist_from_center_sq > max_proj_dist_sq:
                    reset_star = True

            if reset_star:
                fg_stars[i] = create_fg_star()
                fg_stars[i][2] = random.uniform(FG_RESET_Z_MIN, FG_RESET_Z_MAX)
                continue

            if current_z <= 0.01:
                continue
            perspective_factor = PERSPECTIVE_FACTOR_Z / current_z
            sx = int(CENTER_X + star[0] * perspective_factor)
            sy = int(CENTER_Y + star[1] * perspective_factor)

            if 0 <= sx < WIDTH and 0 <= sy < HEIGHT:
                current_pos_in_range = FG_RESET_Z_MAX - current_z
                brightness_t = max(0.0, min(1.0, current_pos_in_range / z_range))
                powered_t = brightness_t ** FG_DEPTH_BRIGHTNESS_POWER
                depth_brightness_multiplier = FG_MIN_DEPTH_BRIGHTNESS_MULT + (1.0 - FG_MIN_DEPTH_BRIGHTNESS_MULT) * powered_t
                base_val = star[3] * depth_brightness_multiplier

                twinkle_factor = 1.0
                if star[8]:
                    twinkle_val = fast_sin(star[7] + global_time * TWINKLE_SPEED)
                    twinkle_factor = 1.0 + twinkle_val * TWINKLE_DEPTH

                final_value = max(0.0, min(1.0, base_val * twinkle_factor))
                r, g, b = hsv_to_rgb(star[4], star[5], final_value)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(sx, sy)

        gu.update(graphics)
        await uasyncio.sleep(dt)
