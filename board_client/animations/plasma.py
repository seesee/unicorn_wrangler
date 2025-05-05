import uasyncio
import math

from animations.utils import hsv_to_rgb

async def run(graphics, gu, state, interrupt_event):
    # plasma effect using hsv
    WIDTH, HEIGHT = graphics.get_bounds()
    t = 0.0
    hue_offset = 0.0

    # params todo: tweak more?
    time_increment = 0.08
    hue_cycle_speed = 0.015
    brightness = 1.0
    saturation = 1.0
    freq_x1, freq_y1 = 4.5, 3.5
    freq_x2, freq_y2 = 2.8, 5.2
    freq_diag1 = 6.0
    freq_rad1 = 5.0
    time_mod1, time_mod2 = 1.1, 0.8
    drift_speed_x, drift_speed_y = 0.15, 0.1

    while not interrupt_event.is_set():
        t += time_increment
        hue_offset += hue_cycle_speed

        drift_x = math.sin(t * drift_speed_x) * 1.5
        drift_y = math.cos(t * drift_speed_y) * 1.5

        for y in range(HEIGHT):
            for x in range(WIDTH):
                eff_x = x + drift_x
                eff_y = y + drift_y

                v1 = 0.5 + 0.5 * math.sin(eff_x / freq_x1 + t)
                v2 = 0.5 + 0.5 * math.sin(eff_y / freq_y1 + t * time_mod1)
                v3 = 0.5 + 0.5 * math.sin((eff_x + eff_y) / freq_diag1 + t * time_mod2)
                v4 = 0.5 + 0.5 * math.sin(math.sqrt(eff_x**2 + eff_y**2) / freq_rad1 + t)
                v = (v1 + v2 + v3 + v4) / 4.0

                hue = (v + hue_offset) % 1.0
                r, g, b = hsv_to_rgb(hue, saturation, brightness)

                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(x, y)

        gu.update(graphics)
        await uasyncio.sleep(0.001)
