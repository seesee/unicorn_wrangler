import uasyncio
import math
import random

from animations.utils import hsv_to_rgb, fast_cos, fast_sin
from uw.hardware import WIDTH, HEIGHT

SKY_TOP = (0.62, 0.8, 0.18)   # hsv: deep blue
SKY_BOTTOM = (0.62, 0.8, 0.02) # hsv: almost black

def lerp(a, b, t):
    return a + (b - a) * t

def lerp_hsv(hsv1, hsv2, t):
    h1, s1, v1 = hsv1
    h2, s2, v2 = hsv2
    return (lerp(h1, h2, t), lerp(s1, s2, t), lerp(v1, v2, t))

NUM_STARS = 30
STAR_PIXELS = [
    (random.randint(0, WIDTH-1), random.randint(0, HEIGHT-1), random.uniform(0.05, 0.18), random.uniform(0, math.pi*2))
    for _ in range(NUM_STARS)
]

# firework, particle types
MAX_PARTICLES = 90
MAX_FIREWORKS = 2
GRAVITY = 0.05
LAUNCH_CHANCE = 0.04

FIREWORK_TYPES = [
    {"particles": 15, "speed": 0.8, "life": 20, "shape": "normal"},
    {"particles": 25, "speed": 1.0, "life": 25, "shape": "normal"},
    {"particles": 35, "speed": 0.9, "life": 30, "shape": "normal"},
    {"particles": 24, "speed": 1.0, "life": 28, "shape": "ring"},  # ring type
]

COLOURS = [
    (255, 50, 50),    # red
    (255, 150, 50),   # orange
    (255, 255, 50),   # yellow
    (50, 255, 50),    # green
    (50, 150, 255),   # blue
    (200, 50, 255),   # purple
    (255, 50, 200)    # pink
]

COLOURFUL_HUES = [
    (0.0, 1.0, 1.0),    # red
    (0.08, 1.0, 1.0),   # orange
    (0.15, 1.0, 1.0),   # yellow
    (0.33, 1.0, 1.0),   # green
    (0.58, 1.0, 1.0),   # blue
    (0.78, 1.0, 1.0),   # purple
    (0.9, 1.0, 1.0),    # pink
]

class Particle:
    __slots__ = ['x', 'y', 'vx', 'vy', 'colour', 'life', 'age', 'sparkle', 'hue_shift']
    def __init__(self, x, y, vx, vy, colour, life, sparkle=False, hue_shift=0.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.colour = colour  # can be rgb or hsv tuple
        self.life = life
        self.age = 0
        self.sparkle = sparkle
        self.hue_shift = hue_shift

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += GRAVITY
        self.age += 1
        return self.age < self.life

    def get_colour(self):
        # if colour is hsv, shift hue as it ages
        if isinstance(self.colour, tuple) and len(self.colour) == 3 and self.hue_shift != 0.0:
            h, s, v = self.colour
            h = (h + self.hue_shift * self.age) % 1.0
            return hsv_to_rgb(h, s, v)
        elif isinstance(self.colour, tuple) and len(self.colour) == 3 and max(self.colour) <= 1.0:
            # hsv, no shift
            return hsv_to_rgb(*self.colour)
        return self.colour

class Firework:
    __slots__ = ['x', 'y', 'target_y', 'vy', 'exploded', 'colour', 'type']
    def __init__(self):
        self.x = random.randint(WIDTH//4, WIDTH*3//4)
        self.y = HEIGHT
        self.target_y = random.randint(2, HEIGHT*2//3)
        self.vy = -random.random() * 0.5 - 0.5
        self.exploded = False
        # 1 in 3 chance of colour-changing firework
        if random.random() < 0.33:
            self.colour = random.choice(COLOURFUL_HUES)
        else:
            self.colour = random.choice(COLOURS)
        self.type = random.choice(FIREWORK_TYPES)

    def update(self, particles, graphics):
        if not self.exploded:
            self.y += self.vy
            ix, iy = int(self.x), int(self.y)
            if 0 <= ix < WIDTH and 0 <= iy < HEIGHT:
                # launch trail
                graphics.set_pen(graphics.create_pen(255, 255, 200))
                graphics.pixel(ix, iy)
                for i in range(1, 3):
                    trail_y = iy + i
                    if trail_y < HEIGHT:
                        fade = 1.0 - (i / 3)
                        graphics.set_pen(graphics.create_pen(
                            int(255 * fade),
                            int(200 * fade),
                            int(50 * fade)
                        ))
                        graphics.pixel(ix, trail_y)
            if self.y <= self.target_y:
                self.exploded = True
                # ring shape
                if self.type.get("shape", "normal") == "ring":
                    for k in range(self.type["particles"]):
                        angle = (k / self.type["particles"]) * math.pi * 2
                        speed = self.type["speed"]
                        # colour-changing: use hsv and hue_shift
                        if isinstance(self.colour, tuple) and max(self.colour) <= 1.0:
                            hue_shift = 0.012 + random.uniform(-0.004, 0.004)
                            colour = self.colour
                        else:
                            hue_shift = 0.0
                            colour = self.colour
                        particles.append(Particle(
                            self.x, self.y,
                            fast_cos(angle) * speed,
                            fast_sin(angle) * speed,
                            colour,
                            random.randint(self.type["life"] - 5, self.type["life"] + 5),
                            random.random() < 0.3,
                            hue_shift
                        ))
                else:
                    for _ in range(self.type["particles"]):
                        angle = random.random() * math.pi * 2
                        speed = random.random() * self.type["speed"] + 0.3
                        # colour-changing: use HSV and hue_shift
                        if isinstance(self.colour, tuple) and max(self.colour) <= 1.0:
                            hue_shift = 0.012 + random.uniform(-0.004, 0.004)
                            colour = self.colour
                        else:
                            hue_shift = 0.0
                            colour = self.colour
                        r, g, b = colour if isinstance(colour, tuple) and max(colour) > 1.0 else (0, 0, 0)
                        if isinstance(colour, tuple) and max(colour) > 1.0:
                            # Slight colour variation for RGB
                            r = min(255, r + random.randint(-20, 20))
                            g = min(255, g + random.randint(-20, 20))
                            b = min(255, b + random.randint(-20, 20))
                            colour = (r, g, b)
                        particles.append(Particle(
                            self.x, self.y,
                            fast_cos(angle) * speed,
                            fast_sin(angle) * speed,
                            colour,
                            random.randint(self.type["life"] - 5, self.type["life"] + 5),
                            random.random() < 0.3,
                            hue_shift
                        ))
            return True
        return False

async def run(graphics, gu, state, interrupt_event):
    # a typical municipal fireworks display
    fireworks = []
    particles = []
    t = 0.0

    while not interrupt_event.is_set():
        # apply night sky gradient
        for y in range(HEIGHT):
            t_y = y / (HEIGHT-1) if HEIGHT > 1 else 0
            hsv = lerp_hsv(SKY_TOP, SKY_BOTTOM, t_y)
            r, g, b = hsv_to_rgb(*hsv)
            graphics.set_pen(graphics.create_pen(r, g, b))
            for x in range(WIDTH):
                graphics.pixel(x, y)
        # twinkle twinkle little star(s)
        for sx, sy, val, phase in STAR_PIXELS:
            twinkle = 0.7 + 0.3 * math.sin(t * 2 + phase)
            r, g, b = hsv_to_rgb(0.62, 0.0, val * twinkle)
            graphics.set_pen(graphics.create_pen(r, g, b))
            graphics.pixel(sx, sy)

        # baby you're a firework
        if len(fireworks) < MAX_FIREWORKS and random.random() < LAUNCH_CHANCE:
            fireworks.append(Firework())

        i = 0
        while i < len(fireworks):
            if fireworks[i].update(particles, graphics):
                i += 1
            else:
                fireworks[i] = fireworks[-1]
                fireworks.pop() # .pop().pop()

        i = 0
        while i < len(particles):
            p = particles[i]
            if p.update():
                fade = 1.0 - (p.age / p.life)
                if p.sparkle and random.random() < 0.4:
                    fade = min(1.0, fade * 1.5)
                ix, iy = int(p.x), int(p.y)
                if 0 <= ix < WIDTH and 0 <= iy < HEIGHT:
                    r, g, b = p.get_colour()
                    r = int(r * fade)
                    g = int(g * fade)
                    b = int(b * fade)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(ix, iy)
                    prev_x = ix - int(p.vx)
                    prev_y = iy - int(p.vy)
                    if 0 <= prev_x < WIDTH and 0 <= prev_y < HEIGHT:
                        trail_fade = fade * 0.6
                        graphics.set_pen(graphics.create_pen(
                            int(r * trail_fade),
                            int(g * trail_fade),
                            int(b * trail_fade)
                        ))
                        graphics.pixel(prev_x, prev_y)
                i += 1
            else:
                particles[i] = particles[-1]
                particles.pop()

        gu.update(graphics)
        t += 0.035
        await uasyncio.sleep(0.035)