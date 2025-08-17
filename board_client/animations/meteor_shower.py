import uasyncio
import random
import math

from animations.utils import hsv_to_rgb, fast_sin
from uw.hardware import WIDTH, HEIGHT

# aurora gradient stops (hsv)
AURORA_STOPS = [
    (0.68, 0.8, 0.08),   # deep blue/purple (top)
    (0.45, 0.9, 0.13),   # green
    (0.18, 0.7, 0.10),   # yellow-green
    (0.00, 0.8, 0.07),   # dull red/orange (bottom)
]

def lerp(a, b, t):
    return a + (b - a) * t

def lerp_hsv(hsv1, hsv2, t):
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

def get_aurora_colour(y):
    t = y / (HEIGHT - 1) if HEIGHT > 1 else 0
    num_stops = len(AURORA_STOPS)
    seg = t * (num_stops - 1)
    i = int(seg)
    frac = seg - i
    if i >= num_stops - 1:
        return AURORA_STOPS[-1]
    return lerp_hsv(AURORA_STOPS[i], AURORA_STOPS[i+1], frac)

# meteor colour palette: (hsv)
METEOR_COLOURS = [
    (0.10, 0.2, 1.0),   # white
    (0.08, 0.9, 1.0),   # orange
    (0.15, 0.8, 1.0),   # yellow
    (0.58, 0.7, 1.0),   # blue (rare)
    (0.00, 0.9, 1.0),   # red (rare)
]
METEOR_COLOUR_WEIGHTS = [0.35, 0.30, 0.30, 0.025, 0.025]  # Blue/red are rare

def pick_meteor_colour():
    r = random.random()
    total = 0
    for colour, weight in zip(METEOR_COLOURS, METEOR_COLOUR_WEIGHTS):
        total += weight
        if r < total:
            return colour
    return METEOR_COLOURS[0]

class Glow:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 2
        self.base_brightness = 0.7
        self.lifetime = 0.5  # linger
        self.age = 0.0
        self.flicker_phase = random.uniform(0, math.pi * 2)

    def update(self, dt):
        self.age += dt

    def is_alive(self):
        return self.age < self.lifetime

    def draw(self, graphics, t):
        fade = max(0.0, 1.0 - self.age / self.lifetime)
        # flicker: sine + random
        flicker = 0.85 + 0.15 * fast_sin(t * 12 + self.flicker_phase + self.age * 8)
        flicker += random.uniform(-0.08, 0.08)
        brightness = self.base_brightness * fade * flicker
        for dx in range(-self.radius, self.radius + 1):
            for dy in range(-self.radius, self.radius + 1):
                dist = math.sqrt(dx*dx + dy*dy)
                if dist <= self.radius:
                    px = self.x + dx
                    py = self.y + dy
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        local_fade = max(0.0, 1.0 - dist / (self.radius + 0.5))
                        r, g, b = hsv_to_rgb(0.07, 0.8, max(0.0, min(1.0, brightness * local_fade)))
                        graphics.set_pen(graphics.create_pen(r, g, b))
                        graphics.pixel(px, py)

async def run(graphics, gu, state, interrupt_event):
    NUM_METEORS = 6 + WIDTH // 6
    METEOR_LENGTH = 7 + WIDTH // 8
    METEOR_SPEED_MIN = 0.25
    METEOR_SPEED_MAX = 0.7

    class Meteor:
        def __init__(self):
            self.reset()

        def reset(self):
            MIN_ANGLE_DEG = 15
            MAX_ANGLE_DEG = 75
            min_angle = math.radians(MIN_ANGLE_DEG)
            max_angle = math.radians(MAX_ANGLE_DEG)
            if random.random() < 0.5:
                self.x = random.uniform(0, WIDTH - 1)
                self.y = 0
                angle = random.uniform(min_angle, max_angle)
            else:
                self.x = 0
                self.y = random.uniform(0, HEIGHT - 1)
                angle = random.uniform(min_angle, max_angle)
            if self.x == 0:
                self.dx = math.sin(angle)
                self.dy = math.cos(angle)
            else:
                self.dx = math.cos(angle)
                self.dy = math.sin(angle)
            self.speed = random.uniform(METEOR_SPEED_MIN, METEOR_SPEED_MAX)
            self.length = METEOR_LENGTH
            self.colour = pick_meteor_colour()
            self.brightness = 1.0

        def update(self):
            self.x += self.dx * self.speed
            self.y += self.dy * self.speed
            if (self.x < -self.length or self.x > WIDTH + self.length or
                self.y < -self.length or self.y > HEIGHT + self.length):
                self.reset()
                return None
            if int(self.y) >= HEIGHT - 1:
                impact_x = int(self.x)
                impact_y = HEIGHT - 1
                self.reset()
                return (impact_x, impact_y)
            return None

        def draw(self, t):
            h, s, v = self.colour
            for i in range(self.length):
                px = int(self.x - self.dx * i)
                py = int(self.y - self.dy * i)
                fade = max(0.0, 1.0 - i / self.length)
                # Slight hue shift for trail
                hue = (h + 0.01 * i) % 1.0
                r, g, b = hsv_to_rgb(hue, s, max(0.0, min(1.0, fade * self.brightness * v)))
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(px, py)

    meteors = [Meteor() for _ in range(NUM_METEORS)]
    glows = []
    t = 0.0

    import utime
    last_time = utime.ticks_ms()

    while not interrupt_event.is_set():
        # aurora static background
        for y in range(HEIGHT):
            hsv = get_aurora_colour(y)
            r, g, b = hsv_to_rgb(*hsv)
            graphics.set_pen(graphics.create_pen(r, g, b))
            for x in range(WIDTH):
                graphics.pixel(x, y)

        # update meteors, spawn glows
        current_time = utime.ticks_ms()
        dt = utime.ticks_diff(current_time, last_time) / 1000.0
        last_time = current_time

        for m in meteors:
            impact = m.update()
            if impact:
                glows.append(Glow(*impact))
            m.draw(t)

        # update, draw glows
        next_glows = []
        for glow in glows:
            glow.update(dt)
            if glow.is_alive():
                glow.draw(graphics, t)
                next_glows.append(glow)
        glows = next_glows

        gu.update(graphics)
        t += 0.02
        await uasyncio.sleep(0.01)
