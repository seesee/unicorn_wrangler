import uasyncio
import math
import random

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT, MODEL


async def run(graphics, gu, state, interrupt_event):
    centre_x = WIDTH // 2
    centre_y = HEIGHT // 2
    num_tendrils = 6 + WIDTH // 8
    min_radius = 1.0

    if MODEL == "galactic":
        sphere_radius = HEIGHT // 2
    else:
        sphere_radius = min(WIDTH, HEIGHT) // 2

    max_tendril_radius = sphere_radius * 0.95

    tendril_phase = [random.uniform(0, 2 * math.pi) for _ in range(num_tendrils)]
    tendril_target = [random.uniform(0, 2 * math.pi) for _ in range(num_tendrils)]
    tendril_branch = [random.random() for _ in range(num_tendrils)]

    t = 0.0
    while not interrupt_event.is_set():
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # Fill the sphere with a dark grey-blue
        fill_r, fill_g, fill_b = 10, 15, 20
        graphics.set_pen(graphics.create_pen(fill_r, fill_g, fill_b))
        for y in range(HEIGHT):
            for x in range(WIDTH):
                dist = math.sqrt((x - centre_x) ** 2 + (y - centre_y) ** 2)
                if dist <= sphere_radius:
                    graphics.pixel(x, y)

        # Draw the glass boundary
        glass_r, glass_g, glass_b = 30, 40, 50  # Dim blue-grey
        graphics.set_pen(graphics.create_pen(glass_r, glass_g, glass_b))
        for angle_deg in range(0, 360, 2):
            angle_rad = math.radians(angle_deg)
            x = int(centre_x + math.cos(angle_rad) * (sphere_radius -1))
            y = int(centre_y + math.sin(angle_rad) * (sphere_radius-1))
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                graphics.pixel(x, y)

        def draw_pixel_in_sphere(x, y, r, g, b):
            dist = math.sqrt((x - centre_x) ** 2 + (y - centre_y) ** 2)
            if dist <= sphere_radius:
                fade_factor = 1.0 - (dist / sphere_radius)
                fade_factor = max(0.0, min(1.0, fade_factor ** 1.5))
                # Combine with background
                final_r = int(fill_r + (r - fill_r) * fade_factor)
                final_g = int(fill_g + (g - fill_g) * fade_factor)
                final_b = int(fill_b + (b - fill_b) * fade_factor)
                graphics.set_pen(graphics.create_pen(final_r, final_g, final_b))
                graphics.pixel(x, y)

        hue = 0.9 + (fast_sin(t * 0.5) * 0.05)
        rr, gg, bb = hsv_to_rgb(hue, 0.7, 1.0)
        draw_pixel_in_sphere(centre_x, centre_y, rr, gg, bb)

        for i in range(num_tendrils):
            phase = t * (0.7 + 0.2 * i) + tendril_phase[i]
            tendril_target[i] += (random.random() - 0.5) * 0.03
            base_angle = tendril_target[i] + fast_sin(phase) * 0.25

            pulse = 0.7 + 0.3 * fast_sin(phase * 0.7 + i)
            length = min_radius + (max_tendril_radius - min_radius) * pulse

            for seg in range(int(min_radius), int(length)):
                frac = (seg - min_radius) / (max_tendril_radius - min_radius)
                wiggle = fast_sin(phase + frac * 7 + i) * (0.18 + 0.18 * frac)
                angle = base_angle + wiggle

                px = int(centre_x + math.cos(angle) * seg)
                py = int(centre_y + math.sin(angle) * seg)

                if random.random() < 0.07 * frac:
                    continue

                fade = 1.0 - frac * 0.85
                fade = max(0.0, min(1.0, fade))
                hue = 0.9 + (fast_sin(t + i) * 0.05)
                saturation = max(0.0, min(1.0, frac * 1.2))
                r, g, b = hsv_to_rgb(hue, saturation, fade)

                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    draw_pixel_in_sphere(px, py, r, g, b)

            tip_angle = base_angle + fast_sin(phase + i) * 0.2
            tip_len = length + fast_sin(phase * 1.2 + i) * 1.2
            tip_x = int(centre_x + math.cos(tip_angle) * tip_len)
            tip_y = int(centre_y + math.sin(tip_angle) * tip_len)

            dist_to_tip = math.sqrt((tip_x - centre_x) ** 2 + (tip_y - centre_y) ** 2)
            if dist_to_tip >= sphere_radius - 1:
                impact_angle = math.atan2(tip_y - centre_y, tip_x - centre_x)
                spark_hue = 0.8  # Purple

                for d_angle in range(-4, 5):
                    angle = impact_angle + math.radians(d_angle * 2)
                    brightness = max(0.5, 1.0 - (abs(d_angle) / 5.0))
                    r, g, b = hsv_to_rgb(spark_hue, 1.0, brightness)

                    px = int(centre_x + math.cos(angle) * (sphere_radius - 1))
                    py = int(centre_y + math.sin(angle) * (sphere_radius - 1))

                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        graphics.set_pen(graphics.create_pen(r, g, b))
                        graphics.pixel(px, py)

        gu.update(graphics)
        t += 0.045
        await uasyncio.sleep(0.01)
