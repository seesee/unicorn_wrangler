import uasyncio
import math
import random

from animations.utils import hsv_to_rgb, fast_sin, fast_cos

async def run(graphics, gu, state, interrupt_event):
    # particle swarm/boid effect. todo: shorten tails

    WIDTH, HEIGHT = graphics.get_bounds()

    TRAIL_FADE_MIN = 20  # min fade (longest trail)
    TRAIL_FADE_MAX = 32  # max fade (shortest trail)
    TRAIL_FADE_PULSE_SPEED = 0.7  # lower = slower
    
    SPEED_MULTIPLIER = 0.7
    NUM_BOIDS = 30

    trail_buffer = [
        [(0, 0, 0) for _ in range(HEIGHT)] for _ in range(WIDTH)
    ]

    class Boid:
        def __init__(self):
            self.x = random.random() * WIDTH
            self.y = random.random() * HEIGHT
            self.vx = random.random() * 2 - 1
            self.vy = random.random() * 2 - 1
            speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
            if speed > 0:
                self.vx /= speed
                self.vy /= speed
            else:
                self.vx = 1.0
                self.vy = 0.0
            self.hue = random.random()
            self.r, self.g, self.b = 0, 0, 0

        def update(self, boids, t):
            perception_radius = 10
            separation_weight = 1.5
            alignment_weight = 1.0
            cohesion_weight = 1.0

            sep_x, sep_y = 0, 0
            ali_x, ali_y = 0, 0
            coh_x, coh_y = 0, 0
            count = 0

            for other in boids:
                if other is self:
                    continue
                dx = other.x - self.x
                dy = other.y - self.y
                dist_sq = dx * dx + dy * dy
                if dist_sq < perception_radius * perception_radius:
                    dist = math.sqrt(dist_sq)
                    if dist > 0:
                        inv_dist = 1.0 / dist
                        sep_x -= dx * inv_dist
                        sep_y -= dy * inv_dist
                    ali_x += other.vx
                    ali_y += other.vy
                    coh_x += other.x
                    coh_y += other.y
                    count += 1

            if count > 0:
                ali_x /= count
                ali_y /= count
                coh_x /= count
                coh_y /= count
                coh_x -= self.x
                coh_y -= self.y
                sep_x *= separation_weight
                sep_y *= separation_weight
                ali_x *= alignment_weight
                ali_y *= alignment_weight
                coh_x *= cohesion_weight
                coh_y *= cohesion_weight
                self.vx += sep_x + ali_x + coh_x
                self.vy += sep_y + ali_y + coh_y
                speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
                if speed > 0:
                    inv_speed = 1.0 / speed
                    self.vx *= inv_speed
                    self.vy *= inv_speed

            flow_x = fast_sin(self.y / HEIGHT * 5 + t * 0.2) * 0.3
            flow_y = fast_cos(self.x / WIDTH * 5 + t * 0.2) * 0.3
            self.vx += flow_x
            self.vy += flow_y

            speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
            if speed > 0:
                inv_speed = 1.0 / speed
                self.vx *= inv_speed
                self.vy *= inv_speed
            elif self.vx == 0 and self.vy == 0:
                self.vx = random.random() * 2 - 1
                self.vy = random.random() * 2 - 1
                speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
                if speed > 0:
                    self.vx /= speed
                    self.vy /= speed
                else:
                    self.vx = 1.0

            self.x += self.vx * SPEED_MULTIPLIER
            self.y += self.vy * SPEED_MULTIPLIER
            self.x %= WIDTH
            self.y %= HEIGHT
            if self.x < 0: self.x += WIDTH
            if self.y < 0: self.y += HEIGHT

            h = (self.hue + t * 0.05) % 1.0
            self.r, self.g, self.b = hsv_to_rgb(h, 1.0, 1.0)

        def add_to_trail(self):
            ix, iy = int(self.x), int(self.y)
            if 0 <= ix < WIDTH and 0 <= iy < HEIGHT:
                current_r, current_g, current_b = trail_buffer[ix][iy]
                new_r = min(255, current_r + self.r)
                new_g = min(255, current_g + self.g)
                new_b = min(255, current_b + self.b)
                trail_buffer[ix][iy] = (new_r, new_g, new_b)

        def draw_boid(self):
            graphics.set_pen(graphics.create_pen(self.r, self.g, self.b))
            graphics.pixel(int(self.x), int(self.y))

    boids = [Boid() for _ in range(NUM_BOIDS)]
    t = 0

    while not interrupt_event.is_set():
        pulse = 0.5 + 0.5 * math.sin(t * TRAIL_FADE_PULSE_SPEED)
        FADE_AMOUNT = int(TRAIL_FADE_MIN + (TRAIL_FADE_MAX - TRAIL_FADE_MIN) * pulse)
        for x in range(WIDTH):
            for y in range(HEIGHT):
                r, g, b = trail_buffer[x][y]
                r = max(0, r - FADE_AMOUNT)
                g = max(0, g - FADE_AMOUNT)
                b = max(0, b - FADE_AMOUNT)
                trail_buffer[x][y] = (r, g, b)

        for x in range(WIDTH):
            for y in range(HEIGHT):
                r, g, b = trail_buffer[x][y]
                if r > 0 or g > 0 or b > 0:
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(x, y)

        for boid in boids:
            boid.update(boids, t)
            boid.add_to_trail()
            boid.draw_boid()

        t += 0.03
        gu.update(graphics)
        await uasyncio.sleep(0.001)
