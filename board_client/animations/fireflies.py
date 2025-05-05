import uasyncio
import random
import math

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

# firefly palette (red, orange, yellow, green)
FIREFLY_HUES = [0.00, 0.08, 0.15, 0.33]

# dusk gradient
DUSK_TOP = (0.60, 0.8, 0.04)   # deep blue
DUSK_BOTTOM = (0.00, 0.9, 0.07) # deep red

def lerp(a, b, t):
    return a + (b - a) * t

def lerp_hsv(hsv1, hsv2, t):
    # interpolate hsv; handle hue wrap
    h1, s1, v1 = hsv1
    h2, s2, v2 = hsv2
    dh = h2 - h1
    if dh > 0.5:
        dh -= 1.0
    elif dh < -0.5:
        dh += 1.0
    h = (h1 + dh * t) % 1.0
    s = lerp(s1, s2, t)
    v = lerp(v1, v2, t)
    return (h, s, v)

async def run(graphics, gu, state, interrupt_event):
    NUM_FIREFLIES = 10 + WIDTH // 4
    TRAIL_LENGTH = 8

    class Firefly:
        def __init__(self):
            self.x = random.uniform(0, WIDTH - 1)
            self.y = random.uniform(0, HEIGHT - 1)
            self.angle = random.uniform(0, 2 * math.pi)
            self.speed = 0.12 + random.random() * 0.18
            self.hue = random.choice(FIREFLY_HUES)
            self.trail = []
            self.sat = 0.85 + random.uniform(-0.1, 0.1)
            self.val = 1.0

        def update(self, t):
            # randomly change direction
            if random.random() < 0.08:
                self.angle += random.uniform(-0.5, 0.5)
            # move
            self.x += math.cos(self.angle) * self.speed
            self.y += math.sin(self.angle) * self.speed
            # bounce off edges
            if self.x < 0:
                self.x = 0
                self.angle = math.pi - self.angle
            elif self.x > WIDTH - 1:
                self.x = WIDTH - 1
                self.angle = math.pi - self.angle
            if self.y < 0:
                self.y = 0
                self.angle = -self.angle
            elif self.y > HEIGHT - 1:
                self.y = HEIGHT - 1
                self.angle = -self.angle
            # add trail
            self.trail.insert(0, (self.x, self.y))
            if len(self.trail) > TRAIL_LENGTH:
                self.trail.pop()
            # flicker
            self.val = 0.8 + 0.2 * fast_sin(t * 2 + self.hue * 7)

        def draw(self, t):
            # draw fading trail
            for i, (tx, ty) in enumerate(self.trail):
                fade = max(0.0, 1.0 - i / TRAIL_LENGTH)
                # shift hue for trail, keep palette
                r, g, b = hsv_to_rgb(self.hue, self.sat, fade * 0.7)
                graphics.set_pen(graphics.create_pen(r, g, b))
                px, py = int(tx), int(ty)
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.pixel(px, py)
            # draw firefly
            pulse = 0.7 + 0.3 * fast_sin(t * 2 + self.hue * 6)
            r, g, b = hsv_to_rgb(self.hue, self.sat, pulse * self.val)
            graphics.set_pen(graphics.create_pen(r, g, b))
            px, py = int(self.x), int(self.y)
            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                graphics.pixel(px, py)

    fireflies = [Firefly() for _ in range(NUM_FIREFLIES)]
    t = 0.0

    while not interrupt_event.is_set():
        # draw dusk gradient
        for y in range(HEIGHT):
            t_y = y / (HEIGHT - 1) if HEIGHT > 1 else 0
            hsv = lerp_hsv(DUSK_TOP, DUSK_BOTTOM, t_y)
            r, g, b = hsv_to_rgb(*hsv)
            graphics.set_pen(graphics.create_pen(r, g, b))
            for x in range(WIDTH):
                graphics.pixel(x, y)

        for f in fireflies:
            f.update(t)
            f.draw(t)
        gu.update(graphics)
        t += 0.03
        await uasyncio.sleep(0.01)
