import uasyncio
import math
import random

from animations.utils import hsv_to_rgb

async def run(graphics, gu, state, interrupt_event):
    # twisting wireframe tunnel effect that is somewhat broken but I like it.
    WIDTH, HEIGHT = graphics.get_bounds()
    num_segments = 15
    points_per_segment = 8
    segment_depth = 2.0
    tunnel_radius = 8.0
    zoom_speed = 0.15
    focal_length = WIDTH / 1.5

    path_freq_x = 0.15
    path_freq_y = 0.2
    path_amplitude_x = WIDTH / 4
    path_amplitude_y = HEIGHT / 4
    path_time_speed_x = 0.8
    path_time_speed_y = 0.6

    hue_start = random.random()
    hue_speed = 0.02

    screen_center_x = WIDTH / 2
    screen_center_y = HEIGHT / 2
    max_z = num_segments * segment_depth

    segments_z = [(i + 1) * segment_depth for i in range(num_segments)]
    time_offset = 0.0

    while not interrupt_event.is_set():
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        time_offset += zoom_speed
        segments_z.sort(reverse=True)
        new_segments_z = []
        current_hue = (hue_start + time_offset * hue_speed) % 1.0
        projected_points_prev = None

        for i, z in enumerate(segments_z):
            z -= zoom_speed
            new_segments_z.append(z)
            if z <= 0.1:
                continue

            path_x = path_amplitude_x * math.sin(z * path_freq_x + time_offset * path_time_speed_x)
            path_y = path_amplitude_y * math.cos(z * path_freq_y + time_offset * path_time_speed_y)
            projected_points_current = []

            for p in range(points_per_segment):
                angle = (p / points_per_segment) * 2 * math.pi
                x3d = path_x + tunnel_radius * math.cos(angle)
                y3d = path_y + tunnel_radius * math.sin(angle)
                scale = focal_length / z
                sx = int(screen_center_x + x3d * scale)
                sy = int(screen_center_y + y3d * scale)
                projected_points_current.append((sx, sy))

            brightness = max(0.0, min(1.0, 1.0 - (z / max_z)))
            r, g, b = hsv_to_rgb(current_hue, 1.0, brightness)
            pen = graphics.create_pen(r, g, b)
            graphics.set_pen(pen)

            for p in range(points_per_segment):
                x1, y1 = projected_points_current[p]
                x2, y2 = projected_points_current[(p + 1) % points_per_segment]
                if 0 <= x1 < WIDTH and 0 <= y1 < HEIGHT and 0 <= x2 < WIDTH and 0 <= y2 < HEIGHT:
                    graphics.line(x1, y1, x2, y2)

            if projected_points_prev is not None and len(projected_points_prev) == points_per_segment:
                for p in range(points_per_segment):
                    x1, y1 = projected_points_current[p]
                    x2, y2 = projected_points_prev[p]
                    if 0 <= x1 < WIDTH and 0 <= y1 < HEIGHT and 0 <= x2 < WIDTH and 0 <= y2 < HEIGHT:
                        graphics.line(x1, y1, x2, y2)

            projected_points_prev = projected_points_current

        segments_z = [z for z in new_segments_z if z > 0.1]
        while len(segments_z) < num_segments:
            current_max_z = max(segments_z) if segments_z else 0.0
            new_z = current_max_z + segment_depth
            segments_z.append(new_z)
            max_z = max(segments_z)

        gu.update(graphics)
        await uasyncio.sleep(0.01)
