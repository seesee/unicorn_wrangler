import uasyncio
import math
import random

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT, MODEL

async def run(graphics, gu, state, interrupt_event):
    centre_x = WIDTH // 2
    centre_y = HEIGHT // 2
    num_tendrils = 12 + WIDTH // 4
    min_radius = 1.0

    if MODEL == "galactic":
        sphere_radius = (WIDTH // 2) - 1
    else:
        sphere_radius = min(WIDTH, HEIGHT) // 2

    max_tendril_radius = sphere_radius * 0.95

    tendril_phase = [random.uniform(0, 2 * math.pi) for _ in range(num_tendrils)]
    tendril_target = [random.uniform(0, 2 * math.pi) for _ in range(num_tendrils)]

    t = 0.0
    while not interrupt_event.is_set():
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        fill_r, fill_g, fill_b = 10, 15, 20
        glass_r, glass_g, glass_b = 30, 40, 50

        if MODEL == "galactic":
            graphics.set_pen(graphics.create_pen(fill_r, fill_g, fill_b))
            graphics.clear()
            graphics.set_pen(graphics.create_pen(glass_r, glass_g, glass_b))
            edge_x = WIDTH - 1
            for y in range(3):
                graphics.pixel(1, y)
                graphics.pixel(edge_x - 1, y)
            for y in range(3, HEIGHT - 3):
                graphics.pixel(0, y)
                graphics.pixel(edge_x, y)
            for y in range(HEIGHT - 3, HEIGHT):
                graphics.pixel(1, y)
                graphics.pixel(edge_x - 1, y)
        else:
            # Draw filled circle for non-galactic models
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    dist = math.sqrt((x - centre_x)**2 + (y - centre_y)**2)
                    if dist <= sphere_radius:
                        if sphere_radius - dist < 1:
                            graphics.set_pen(graphics.create_pen(glass_r, glass_g, glass_b))
                        else:
                            graphics.set_pen(graphics.create_pen(fill_r, fill_g, fill_b))
                        graphics.pixel(x, y)

        def draw_pixel_in_viewport(x, y, r, g, b):
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                dist_from_centre = math.sqrt((x - centre_x) ** 2 + (y - centre_y) ** 2)
                if dist_from_centre < sphere_radius:
                    fade_factor = 1.0 - (dist_from_centre / sphere_radius)
                    fade_factor = max(0.0, min(1.0, fade_factor ** 1.5))
                    final_r = int(fill_r + (r - fill_r) * fade_factor)
                    final_g = int(fill_g + (g - fill_g) * fade_factor)
                    final_b = int(fill_b + (b - fill_b) * fade_factor)
                    graphics.set_pen(graphics.create_pen(final_r, final_g, final_b))
                    graphics.pixel(x, y)

        hue = 0.95 + (fast_sin(t * 0.5) * 0.05)
        rr, gg, bb = hsv_to_rgb(hue, 0.8, 1.0)
        draw_pixel_in_viewport(centre_x, centre_y, rr, gg, bb)

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

                if not (0 <= py < HEIGHT):
                    continue

                if random.random() < 0.07 * frac:
                    continue

                fade = 1.0 - frac * 0.8
                fade = max(0.0, min(1.0, fade))
                hue = 0.95 + (fast_sin(t + i) * 0.05)
                saturation = max(0.0, min(1.0, frac * 1.5))
                r, g, b = hsv_to_rgb(hue, saturation, fade)
                draw_pixel_in_viewport(px, py, r, g, b)

            tip_angle = base_angle + fast_sin(phase + i) * 0.2
            tip_len = length + fast_sin(phase * 1.2 + i) * 1.2
            tip_x = int(centre_x + math.cos(tip_angle) * tip_len)
            tip_y = int(centre_y + math.sin(tip_angle) * tip_len)

            dist_to_tip = math.sqrt((tip_x - centre_x) ** 2 + (tip_y - centre_y) ** 2)

            if dist_to_tip >= sphere_radius - 1:
                spark_hue = 0.8  # Purple
                for dy in range(-2, 3):
                    brightness = max(0.5, 1.0 - (abs(dy) / 3.0))
                    r, g, b = hsv_to_rgb(spark_hue, 1.0, brightness)
                    py = tip_y + dy

                    dist_y = py - centre_y
                    if abs(dist_y) < sphere_radius:
                        dist_x_sq = sphere_radius**2 - dist_y**2
                        if dist_x_sq > 0:
                            dist_x = math.sqrt(dist_x_sq)
                            if tip_x > centre_x:
                                px = int(centre_x + dist_x - 1)
                            else:
                                px = int(centre_x - dist_x)

                            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                                graphics.set_pen(graphics.create_pen(r, g, b))
                                graphics.pixel(px, py)

        gu.update(graphics)
        t += 0.045
        await uasyncio.sleep(0.01)
