import uasyncio
import math

from animations.utils import hsv_to_rgb, fast_sin, fast_cos

async def run(graphics, gu, state, interrupt_event):
    # orbiting radial rainbow effect
    WIDTH, HEIGHT = graphics.get_bounds()
    time = 0

    offset1 = 0.0
    offset2 = 0.5
    radius1 = 0.0
    radius2 = math.sqrt((WIDTH/2)**2 + (HEIGHT/2)**2) / 2

    speed1 = 0.5
    speed2 = 0.4
    dir1 = 1
    dir2 = -1

    orbit_rad = min(WIDTH, HEIGHT) / 4
    orbit_speed1 = 0.02
    orbit_speed2 = 0.015

    max_dist = math.sqrt((WIDTH/2)**2 + (HEIGHT/2)**2)

    while not interrupt_event.is_set():
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        center1_x = WIDTH/2 + orbit_rad * fast_cos(time * orbit_speed1)
        center1_y = HEIGHT/2 + orbit_rad * fast_sin(time * orbit_speed1)
        center2_x = WIDTH/2 + orbit_rad * fast_cos(time * orbit_speed2 + math.pi)
        center2_y = HEIGHT/2 + orbit_rad * fast_sin(time * orbit_speed2 + math.pi)

        dist_x = center1_x - center2_x
        dist_y = center1_y - center2_y
        center_dist = math.sqrt(dist_x*dist_x + dist_y*dist_y)
        interaction = max(0, 1 - (center_dist / (max_dist/2)))

        for y in range(HEIGHT):
            for x in range(WIDTH):
                dx1 = x - center1_x
                dy1 = y - center1_y
                dist1 = math.sqrt(dx1*dx1 + dy1*dy1)
                dx2 = x - center2_x
                dy2 = y - center2_y
                dist2 = math.sqrt(dx2*dx2 + dy2*dy2)
                scale = max_dist / 4.0
                hue1 = (offset1 + (dist1 - radius1) / scale) % 1.0
                hue2 = (offset2 + (dist2 - radius2) / scale) % 1.0
                w1 = 1.0 / (1.0 + dist1 * 0.1)
                w2 = 1.0 / (1.0 + dist2 * 0.1)
                w_total = w1 + w2
                w1 = w1 / w_total
                w2 = w2 / w_total
                r1, g1, b1 = hsv_to_rgb(hue1, 1.0, 1.0)
                r2, g2, b2 = hsv_to_rgb(hue2, 1.0, 1.0)
                r = int(r1 * w1 + r2 * w2)
                g = int(g1 * w1 + g2 * w2)
                b = int(b1 * w1 + b2 * w2)
                if interaction > 0.2:
                    boost = 1 + interaction * 0.5
                    r = min(255, int(r * boost))
                    g = min(255, int(g * boost))
                    b = min(255, int(b * boost))
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(x, y)

        time += 1
        offset1 += 0.003
        offset2 += 0.004
        radius1 += speed1 * dir1
        radius2 += speed2 * dir2
        if radius1 >= max_dist and dir1 == 1:
            dir1 = -1
        elif radius1 <= 0 and dir1 == -1:
            dir1 = 1
        if radius2 >= max_dist and dir2 == 1:
            dir2 = -1
        elif radius2 <= 0 and dir2 == -1:
            dir2 = 1

        gu.update(graphics)
        await uasyncio.sleep(0.02)
