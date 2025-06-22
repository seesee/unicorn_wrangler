import uasyncio
import math
import random

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT, MODEL

async def run(graphics, gu, state, interrupt_event):
    centre_x = WIDTH // 2
    centre_y = HEIGHT // 2
    num_tendrils = 6 + WIDTH // 8
    min_radius = 1.0  # Smallest possible centre

    # For galactic, let tendrils reach the furthest edge
    if MODEL == "galactic":
        # Distance from centre to furthest corner
        max_radius = math.sqrt((max(centre_x, WIDTH - centre_x - 1))**2 +
                               (max(centre_y, HEIGHT - centre_y - 1))**2)
    else:
        max_radius = min(WIDTH, HEIGHT) * 0.48

    hue_base = random.random()

    tendril_phase = [random.uniform(0, 2*math.pi) for _ in range(num_tendrils)]
    tendril_target = [random.uniform(0, 2*math.pi) for _ in range(num_tendrils)]
    tendril_branch = [random.random() for _ in range(num_tendrils)]

    t = 0.0
    while not interrupt_event.is_set():
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # Minimal glowing centre: just a single pixel (or a tiny cross)
        hue = (hue_base + t * 0.12) % 1.0
        rr, gg, bb = hsv_to_rgb(hue, 0.7, 1.0)
        graphics.set_pen(graphics.create_pen(rr, gg, bb))
        graphics.pixel(centre_x, centre_y)
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            if 0 <= centre_x+dx < WIDTH and 0 <= centre_y+dy < HEIGHT:
                graphics.set_pen(graphics.create_pen(int(rr*0.5), int(gg*0.5), int(bb*0.5)))
                graphics.pixel(centre_x+dx, centre_y+dy)

        # Animate tendrils
        for i in range(num_tendrils):
            phase = t * (0.7 + 0.2 * i) + tendril_phase[i]
            tendril_target[i] += (random.random() - 0.5) * 0.03
            base_angle = tendril_target[i] + fast_sin(phase) * 0.25

            # The tendril "grows" and "retracts" with a pulse
            pulse = 0.7 + 0.3 * fast_sin(phase * 0.7 + i)
            length = min_radius + (max_radius - min_radius) * pulse

            branch = tendril_branch[i] > 0.7
            branch_angle = base_angle + (0.18 if branch else 0)

            for seg in range(int(min_radius), int(length)):
                frac = (seg - min_radius) / (max_radius - min_radius)
                wiggle = fast_sin(phase + frac * 7 + i) * (0.18 + 0.18 * frac)
                angle = base_angle + wiggle

                px = int(centre_x + math.cos(angle) * seg)
                py = int(centre_y + math.sin(angle) * seg)

                if random.random() < 0.07 * frac:
                    continue

                fade = 1.0 - frac * 0.85
                fade = max(0.0, min(1.0, fade))
                hue = (hue_base + i / num_tendrils + t * 0.07 + frac * 0.2) % 1.0
                r, g, b = hsv_to_rgb(hue, 1.0, fade)
                graphics.set_pen(graphics.create_pen(int(r), int(g), int(b)))
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.pixel(px, py)

                # Draw a branch if enabled
                if branch and frac > 0.5:
                    branch_px = int(centre_x + math.cos(branch_angle + wiggle * 0.7) * seg)
                    branch_py = int(centre_y + math.sin(branch_angle + wiggle * 0.7) * seg)
                    if 0 <= branch_px < WIDTH and 0 <= branch_py < HEIGHT:
                        graphics.set_pen(graphics.create_pen(int(r*0.7), int(g*0.7), int(b*0.7)))
                        graphics.pixel(branch_px, branch_py)

            # Optionally, a bright "spark" at the tip
            tip_angle = base_angle + fast_sin(phase + i) * 0.2
            tip_len = length + fast_sin(phase * 1.2 + i) * 1.2
            tip_x = int(centre_x + math.cos(tip_angle) * tip_len)
            tip_y = int(centre_y + math.sin(tip_angle) * tip_len)
            if 0 <= tip_x < WIDTH and 0 <= tip_y < HEIGHT:
                r, g, b = hsv_to_rgb((hue_base + i / num_tendrils + t * 0.1) % 1.0, 1.0, 1.0)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(tip_x, tip_y)

        gu.update(graphics)
        t += 0.045
        await uasyncio.sleep(0.01)
