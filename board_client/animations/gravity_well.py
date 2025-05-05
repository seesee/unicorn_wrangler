import uasyncio
import random
import math

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

async def run(graphics, gu, state, interrupt_event):
    # a gravity well effect
    NUM_PARTICLES = 18 + WIDTH // 2
    CENTER_X = WIDTH / 2
    CENTER_Y = HEIGHT / 2
    WELL_STRENGTH = 0.13 + 0.04 * (WIDTH / 32)
    PARTICLE_MIN_RADIUS = min(WIDTH, HEIGHT) * 0.18
    PARTICLE_MAX_RADIUS = min(WIDTH, HEIGHT) * 0.48
    PARTICLE_MIN_SPEED = 0.04
    PARTICLE_MAX_SPEED = 0.13

    class Particle:
        def __init__(self):
            self.reset()

        def reset(self):
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(PARTICLE_MIN_RADIUS, PARTICLE_MAX_RADIUS)
            self.x = CENTER_X + math.cos(angle) * radius
            self.y = CENTER_Y + math.sin(angle) * radius
            self.radius = radius
            self.angle = angle
            self.speed = random.uniform(PARTICLE_MIN_SPEED, PARTICLE_MAX_SPEED)
            self.colour_phase = random.random()
            self.orbit_dir = random.choice([-1, 1])
            self.age = 0

        def update(self):
            # Spiral inward
            self.radius -= WELL_STRENGTH * (0.7 + 0.3 * fast_sin(self.angle + self.colour_phase * 2))
            if self.radius < 2.0:
                self.reset()
                return
            self.angle += self.speed * self.orbit_dir
            self.x = CENTER_X + math.cos(self.angle) * self.radius
            self.y = CENTER_Y + math.sin(self.angle) * self.radius
            self.age += 1

        def draw(self, t):
            # colour: based on radius and phase
            dist_norm = (self.radius - PARTICLE_MIN_RADIUS) / (PARTICLE_MAX_RADIUS - PARTICLE_MIN_RADIUS)
            hue = (0.58 + 0.25 * dist_norm + t * 0.07 + self.colour_phase) % 1.0
            sat = 0.7 + 0.3 * fast_cos(t + self.colour_phase * 2)
            val = 0.7 + 0.3 * fast_sin(t + self.age * 0.1)
            r, g, b = hsv_to_rgb(hue, sat, val)
            pen = graphics.create_pen(r, g, b)
            graphics.set_pen(pen)
            px = int(self.x)
            py = int(self.y)
            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                graphics.pixel(px, py)

    particles = [Particle() for _ in range(NUM_PARTICLES)]
    t = 0.0

    while not interrupt_event.is_set():
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        for p in particles:
            p.draw(t)
            p.update()
        # Draw a glowing center
        for r0 in range(2, int(PARTICLE_MIN_RADIUS)):
            fade = 1.0 - (r0 - 2) / (PARTICLE_MIN_RADIUS - 2)
            fade = max(0.0, min(1.0, fade))
            hue = (0.58 + t * 0.12) % 1.0
            rr, gg, bb = hsv_to_rgb(hue, 0.5, fade)
            for a in range(0, 360, 12):
                rad = math.radians(a)
                px = int(CENTER_X + math.cos(rad) * r0)
                py = int(CENTER_Y + math.sin(rad) * r0)
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.set_pen(graphics.create_pen(rr, gg, bb))
                    graphics.pixel(px, py)
        gu.update(graphics)
        t += 0.03
        await uasyncio.sleep(0.01)
