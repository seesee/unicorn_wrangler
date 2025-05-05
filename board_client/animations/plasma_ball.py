import uasyncio
import math
import random

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

async def run(graphics, gu, state, interrupt_event):
    # plasma ball effect
    center_x = WIDTH // 2
    center_y = HEIGHT // 2
    num_tendrils = 7 + WIDTH // 6
    base_radius = min(WIDTH, HEIGHT) * 0.32
    max_radius = min(WIDTH, HEIGHT) * 0.48
    hue_base = random.random()

    # precompute base angles for tendrils
    base_angles = [2 * math.pi * i / num_tendrils for i in range(num_tendrils)]

    t = 0.0
    rotation = 0.0
    rotation_speed = 0.045  # radians per frame

    while not interrupt_event.is_set():
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # animate tendrils with rotation
        for i, base_angle in enumerate(base_angles):
            # add rotation to the base angle
            angle = base_angle + rotation
            # each tendril wiggles & pulses
            phase = t * (0.7 + 0.2 * i) + i
            wiggle = fast_sin(phase + angle * 2) * 0.5 + fast_cos(phase * 0.7 + angle) * 0.3
            length = base_radius + (max_radius - base_radius) * (0.7 + 0.3 * fast_sin(phase + i))
            length += wiggle * 2.5

            # cycle hue per tendril
            hue = (hue_base + i / num_tendrils + t * 0.07) % 1.0
            r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
            pen = graphics.create_pen(r, g, b)
            graphics.set_pen(pen)

            # draw the tendril as a line from centre outward
            for seg in range(int(length)):
                frac = seg / length
                px = int(center_x + math.cos(angle) * seg)
                py = int(center_y + math.sin(angle) * seg)
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    # fade out toward the end
                    fade = 1.0 - frac * 0.8
                    fade = max(0.0, min(1.0, fade))
                    if fade < 0.05:
                        continue
                    # slightly dim the colour at the tip
                    graphics.set_pen(graphics.create_pen(
                        int(r * fade), int(g * fade), int(b * fade)
                    ))
                    graphics.pixel(px, py)

        # glowing center
        for r0 in range(int(base_radius * 0.7), int(base_radius * 0.95)):
            fade = 1.0 - (r0 - base_radius * 0.7) / (base_radius * 0.25)
            fade = max(0.0, min(1.0, fade))
            hue = (hue_base + t * 0.12) % 1.0
            rr, gg, bb = hsv_to_rgb(hue, 0.7, fade)
            for a in range(0, 360, 8):
                rad = math.radians(a)
                px = int(center_x + math.cos(rad) * r0)
                py = int(center_y + math.sin(rad) * r0)
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.set_pen(graphics.create_pen(rr, gg, bb))
                    graphics.pixel(px, py)

        gu.update(graphics)
        t += 0.04
        rotation += rotation_speed
        await uasyncio.sleep(0.01)
