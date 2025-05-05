import uasyncio
import utime
import math
import random

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT, MODEL

NUM_POLYGONS = 3

GALACTIC_SECTION_W = 17  #(57/NUM_POLYGONS)-2 
GALACTIC_SECTION_H = HEIGHT

class PolygonAnim:
    def __init__(self, center_x, center_y, min_radius, max_radius, phase_offset=0.0):
        self.center_x = center_x
        self.center_y = center_y
        self.min_radius = min_radius
        self.max_radius = max_radius
        self.phase_offset = phase_offset
        self.angle = random.uniform(0, math.pi * 2)
        self.rotation_speed = random.uniform(-0.04, 0.04)
        self.target_rotation_speed = self.rotation_speed
        self.radius = (min_radius + max_radius) / 2
        self.radius_phase = random.uniform(0, math.pi * 2)
        self.radius_speed = random.uniform(0.015, 0.025)
        self.sides = 3
        self.target_sides = 3
        self.hue_base = random.random()
        self.hue_speed = random.uniform(0.01, 0.03)
        self.time_since_last_change = 0.0

    def update(self, t, dt):
        self.time_since_last_change += dt
        if self.time_since_last_change > 3.5 + random.random() * 2.5:
            self.target_sides = random.randint(3, 8)
            self.target_rotation_speed = random.uniform(-0.09, 0.09)
            self.radius_speed = random.uniform(0.012, 0.025)
            self.time_since_last_change = 0.0
        self.sides += (self.target_sides - self.sides) * 0.04
        self.rotation_speed += (self.target_rotation_speed - self.rotation_speed) * 0.03
        self.angle += self.rotation_speed
        self.radius_phase += self.radius_speed
        grow = 0.5 + 0.5 * fast_sin(self.radius_phase + self.phase_offset)
        self.radius = self.min_radius + (self.max_radius - self.min_radius) * grow
        self.hue_base = (self.hue_base + self.hue_speed * dt) % 1.0

    def draw(self, graphics, t):
        n_sides = int(round(self.sides))
        angle_offset = self.angle
        hue = (self.hue_base + 0.13 * self.phase_offset) % 1.0
        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
        pen = graphics.create_pen(r, g, b)
        graphics.set_pen(pen)
        vertices = []
        for i in range(n_sides):
            angle = angle_offset + 2 * math.pi * i / n_sides
            x = int(round(self.center_x + math.cos(angle) * self.radius))
            y = int(round(self.center_y + math.sin(angle) * self.radius))
            vertices.append((x, y))
        for i in range(n_sides):
            x1, y1 = vertices[i]
            x2, y2 = vertices[(i + 1) % n_sides]
            if (0 <= x1 < WIDTH and 0 <= y1 < HEIGHT and
                0 <= x2 < WIDTH and 0 <= y2 < HEIGHT):
                graphics.line(x1, y1, x2, y2)

async def run(graphics, gu, state, interrupt_event):
    # mighty morphin' polygon-ger effect
    t = 0.0
    last_time = None

    if MODEL == "galactic":
        section_w = 17
        section_h = HEIGHT
        gap = 1
        centers = [
            (section_w // 2, HEIGHT // 2),
            (WIDTH // 2, HEIGHT // 2),
            (WIDTH - section_w // 2 - 1, HEIGHT // 2)
        ]
        min_radius = 3
        max_radius = min(section_w, section_h) * 0.45
        polygons = [
            PolygonAnim(cx, cy, min_radius, max_radius, phase_offset=i * 2.1)
            for i, (cx, cy) in enumerate(centers)
        ]
    else:
        center_x = (WIDTH - 1) / 2
        center_y = (HEIGHT - 1) / 2
        min_radius = min(WIDTH, HEIGHT) * 0.18
        max_radius = min(WIDTH, HEIGHT) * 0.45
        polygons = [
            PolygonAnim(center_x, center_y, min_radius, max_radius, phase_offset=i * 2.1)
            for i in range(NUM_POLYGONS)
        ]

    last_time = utime.ticks_ms()
    while not interrupt_event.is_set():
        now = utime.ticks_ms()
        dt = utime.ticks_diff(now, last_time) / 1000.0
        last_time = now
        t += dt

        # dynamic dark bg
        bg_hue = (t * 0.04) % 1.0
        r, g, b = hsv_to_rgb(bg_hue, 0.7, 0.13)
        graphics.set_pen(graphics.create_pen(r, g, b))
        graphics.clear()

        for poly in polygons:
            poly.update(t, dt)
            poly.draw(graphics, t)

        gu.update(graphics)
        await uasyncio.sleep(0.01)

