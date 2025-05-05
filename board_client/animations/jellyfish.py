import uasyncio
import math
import random
from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

# seaweed
NUM_SEAWEED = max(3, WIDTH // 8)
SEAWEED_COLOR_BASE = 0.33  # green hue
SEAWEED_COLOR_VARIATION = 0.08
SEAWEED_SAT = 0.8
SEAWEED_VAL = 0.35
SEAWEED_HEIGHT_MIN = int(HEIGHT * 0.5)
SEAWEED_HEIGHT_MAX = HEIGHT - 2

# bubbles
NUM_BUBBLES = max(3, WIDTH // 7)
BUBBLE_MIN_RADIUS = 1
BUBBLE_MAX_RADIUS = 2

# fish
FISH_SHOAL_MIN_LEN = 4
FISH_SHOAL_MAX_LEN = 8
FISH_SHOAL_MIN_Y = 2
FISH_SHOAL_MAX_Y = HEIGHT // 2
FISH_SHOAL_SPEED = 0.13  # pixels per frame
FISH_SHOAL_SPAWN_CHANCE = 0.012  # chance per frame to spawn a new shoal

FISH_COLORS = [
    (0.0, 0.0, 0.22),   # silver
    (0.08, 0.55, 0.18), # bronze
    (0.13, 0.7, 0.22),  # gold
]

class SeaweedStalk:
    def __init__(self, base_x):
        self.base_x = base_x
        self.height = random.randint(SEAWEED_HEIGHT_MIN, SEAWEED_HEIGHT_MAX)
        self.phase = random.uniform(0, math.pi * 2)
        self.amp = random.uniform(0.7, 1.7)
        self.freq = random.uniform(0.18, 0.32)
        self.hue = (SEAWEED_COLOR_BASE +
                    random.uniform(-SEAWEED_COLOR_VARIATION, SEAWEED_COLOR_VARIATION)) % 1.0

    def draw(self, graphics, t):
        for y in range(HEIGHT-1, HEIGHT-1-self.height, -1):
            sway = fast_sin(self.phase + t * self.freq + y * 0.18) * self.amp * (1 - (HEIGHT-1-y)/self.height)
            x = int(round(self.base_x + sway))
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                r, g, b = hsv_to_rgb(self.hue, SEAWEED_SAT, SEAWEED_VAL)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(x, y)

class Bubble:
    def __init__(self):
        self.reset()

    def reset(self):
        self.distance = random.uniform(0.0, 1.0)
        self.x = random.uniform(1, WIDTH-2)
        self.y = HEIGHT - 1
        self.radius = BUBBLE_MIN_RADIUS if self.distance < 0.5 else BUBBLE_MAX_RADIUS
        self.speed = 0.07 + 0.08 * self.distance
        self.drift_phase = random.uniform(0, math.pi * 2)
        self.drift_amp = random.uniform(0.15, 0.5) * (0.5 + self.distance)
        self.hue = 0.58 + 0.04 * (1.0 - self.distance)
        self.sat = 0.65 + 0.25 * self.distance
        self.val = 0.18 + 0.22 * self.distance

    def update(self, t):
        drift = fast_sin(t * 0.7 + self.drift_phase + self.y * 0.12) * self.drift_amp
        self.x += drift * 0.08
        self.y -= self.speed
        if self.y < -self.radius:
            self.reset()

    def draw(self, graphics):
        r, g, b = hsv_to_rgb(self.hue, self.sat, self.val)
        pen = graphics.create_pen(r, g, b)
        for dx in range(-self.radius, self.radius+1):
            for dy in range(-self.radius, self.radius+1):
                if dx*dx + dy*dy <= self.radius*self.radius:
                    px = int(round(self.x + dx))
                    py = int(round(self.y + dy))
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        graphics.set_pen(pen)
                        graphics.pixel(px, py)

def pick_jellyfish_hue():
    ranges = [
        (0.55, 0.65),  # blue
        (0.7, 0.8),    # purple
        (0.9, 1.0),    # pink
        (0.0, 0.08),   # red
    ]
    r = random.random()
    if r < 0.4:
        return random.uniform(*ranges[0])
    elif r < 0.7:
        return random.uniform(*ranges[1])
    elif r < 0.85:
        return random.uniform(*ranges[2])
    else:
        return random.uniform(*ranges[3])

class FishShoal:
    def __init__(self):
        self.reset()

    def reset(self):
        self.length = random.randint(FISH_SHOAL_MIN_LEN, FISH_SHOAL_MAX_LEN)
        self.y = random.randint(FISH_SHOAL_MIN_Y, FISH_SHOAL_MAX_Y)
        self.color = random.choice(FISH_COLORS)
        self.direction = random.choice([-1, 1])  # -1: rtl, 1: ltr
        if self.direction == 1:
            self.x = -self.length * 2
        else:
            self.x = WIDTH + self.length * 2
        self.speed = FISH_SHOAL_SPEED * (0.8 + 0.4 * random.random())

    def update(self):
        self.x += self.speed * self.direction

    def is_offscreen(self):
        if self.direction == 1:
            return self.x - self.length * 2 > WIDTH
        else:
            return self.x + self.length * 2 < 0

    def draw(self, graphics):
        h, s, v = self.color
        r, g, b = hsv_to_rgb(h, s, v)
        pen = graphics.create_pen(r, g, b)
        for i in range(self.length):
            fx = int(round(self.x + i * 2 * self.direction))
            fy = self.y
            # fish = 2x1 block
            for dx in range(2):
                px = fx + dx * self.direction
                py = fy
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.set_pen(pen)
                    graphics.pixel(px, py)

async def run(graphics, gu, state, interrupt_event):
    WIDTH, HEIGHT = graphics.get_bounds()

    # jellyfish params
    bell_radius = min(WIDTH, HEIGHT) * 0.22 + 2
    bell_segments = 18 + WIDTH // 3
    tentacle_count = 7 + WIDTH // 7
    tentacle_length = int(HEIGHT * 0.55)
    tentacle_wave_speed = 0.09
    tentacle_wave_amp = 1.2 + HEIGHT * 0.04
    tentacle_color_shift = 0.13
    bell_pulse_speed = 0.035
    bell_pulse_amp = 0.18
    bell_hue_base = pick_jellyfish_hue()
    bell_hue_speed = 0.018
    bell_glow_layers = 4

    tentacles = []
    tentacle_max_offset = 0
    for i in range(tentacle_count):
        offset = (i - (tentacle_count - 1) / 2) * (bell_radius * 1.2 / tentacle_count)
        tentacle_max_offset = max(tentacle_max_offset, abs(offset))
        phase = random.uniform(0, math.pi * 2)
        amp = tentacle_wave_amp * (0.7 + 0.6 * random.random())
        tentacles.append({
            "offset": offset,
            "phase": phase,
            "amp": amp,
            "speed": tentacle_wave_speed * (0.8 + 0.5 * random.random()),
            "color_shift": tentacle_color_shift * (0.7 + 0.6 * random.random()),
        })

    min_cx = bell_radius
    max_cx = WIDTH - 1 - bell_radius
    min_cy = bell_radius
    max_cy = HEIGHT - 1 - bell_radius

    center_x = (min_cx + max_cx) / 2
    center_y = (min_cy + max_cy) / 2

    drift_x_range = (max_cx - min_cx) / 2
    drift_y_range = (max_cy - min_cy) / 2

    # aquarium setup
    seaweed_stalks = []
    for i in range(NUM_SEAWEED):
        base_x = int((i + 0.5) * WIDTH / NUM_SEAWEED + random.uniform(-1, 1))
        seaweed_stalks.append(SeaweedStalk(base_x))

    bubbles = [Bubble() for _ in range(NUM_BUBBLES)]

    fish_shoal = None
    t = 0.0
    drift_phase = random.uniform(0, math.pi * 2)
    drift_speed = 0.012 + random.random() * 0.01

    while not interrupt_event.is_set():
        # set bg colour (dark blue)
        bg_hue = 0.58
        bg_sat = 0.7
        bg_val = 0.10
        graphics.set_pen(graphics.create_pen(*hsv_to_rgb(bg_hue, bg_sat, bg_val)))
        graphics.clear()

        # fish shoal (farthest back)
        if fish_shoal is None and random.random() < FISH_SHOAL_SPAWN_CHANCE:
            fish_shoal = FishShoal()
        if fish_shoal is not None:
            fish_shoal.update()
            fish_shoal.draw(graphics)
            if fish_shoal.is_offscreen():
                fish_shoal = None

        # seaweed
        for stalk in seaweed_stalks:
            stalk.draw(graphics, t)

        # bubbles
        for bubble in bubbles:
            bubble.update(t)
            bubble.draw(graphics)

        # finally, the jellyfish
        # drift constraints
        drift_x = fast_sin(t * drift_speed + drift_phase) * drift_x_range * 0.95
        drift_y = fast_cos(t * drift_speed * 0.7 + drift_phase) * drift_y_range * 0.95
        jelly_x = int(center_x + drift_x)
        jelly_y = int(center_y + drift_y)

        # jellyfish bell pulse and colour
        pulse = 1.0 + fast_sin(t * bell_pulse_speed) * bell_pulse_amp
        bell_r = bell_radius * (0.95 + 0.12 * fast_sin(t * 0.7))
        bell_h = int(bell_r * (0.7 + 0.25 * pulse))
        bell_hue = (bell_hue_base + t * bell_hue_speed) % 1.0

        # jellyfish bell glow
        for layer in range(bell_glow_layers, 0, -1):
            layer_frac = layer / bell_glow_layers
            r = int(bell_r * (1.0 + 0.18 * layer_frac))
            h = int(bell_h * (1.0 + 0.22 * layer_frac))
            alpha = 0.18 + 0.22 * layer_frac
            hue = (bell_hue + 0.03 * layer) % 1.0
            if 0.25 < hue < 0.42:
                hue = 0.42
            sat = 0.7 - 0.2 * layer_frac
            val = 0.7 * alpha
            rr, gg, bb = hsv_to_rgb(hue, sat, val)
            pen = graphics.create_pen(rr, gg, bb)
            graphics.set_pen(pen)
            for seg in range(bell_segments):
                angle = math.pi * (seg / (bell_segments - 1))
                x = int(jelly_x + math.cos(angle) * r)
                y = int(jelly_y + h - math.sin(angle) * h)
                if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                    graphics.pixel(x, y)

        # bell edge
        for seg in range(bell_segments):
            angle = math.pi * (seg / (bell_segments - 1))
            x = int(jelly_x + math.cos(angle) * bell_r)
            y = int(jelly_y + bell_h - math.sin(angle) * bell_h)
            hue = (bell_hue + 0.04 * fast_sin(t + seg)) % 1.0
            if 0.25 < hue < 0.42:
                hue = 0.42
            rr, gg, bb = hsv_to_rgb(hue, 0.7, 1.0)
            pen = graphics.create_pen(rr, gg, bb)
            graphics.set_pen(pen)
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                graphics.pixel(x, y)

        # tentacles
        for i, tentacle in enumerate(tentacles):
            base_x = int(jelly_x + tentacle["offset"])
            base_y = int(jelly_y + bell_h)
            phase = tentacle["phase"] + t * tentacle["speed"]
            amp = tentacle["amp"] * (0.8 + 0.2 * fast_sin(t * 0.5 + i))
            color_shift = tentacle["color_shift"]
            for seg in range(tentacle_length):
                frac = seg / tentacle_length
                wave = fast_sin(phase + frac * math.pi * 2.2 + i * 0.5)
                x = int(base_x + wave * amp * (1.0 - frac * 0.5))
                y = int(base_y + seg)
                hue = (bell_hue + color_shift * frac) % 1.0
                if 0.25 < hue < 0.42:
                    hue = 0.42
                sat = 0.7 + 0.3 * (1.0 - frac)
                val = 0.7 * (1.0 - frac * 0.7)
                rr, gg, bb = hsv_to_rgb(hue, sat, val)
                pen = graphics.create_pen(rr, gg, bb)
                graphics.set_pen(pen)
                if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                    graphics.pixel(x, y)

        # bell highlights
        highlight_r = int(bell_r * 0.45)
        highlight_h = int(bell_h * 0.45)
        for seg in range(bell_segments // 2):
            angle = math.pi * (seg / (bell_segments // 2 - 1))
            x = int(jelly_x + math.cos(angle) * highlight_r)
            y = int(jelly_y + highlight_h - math.sin(angle) * highlight_h)
            hue = (bell_hue + 0.08) % 1.0
            if 0.25 < hue < 0.42:
                hue = 0.42
            rr, gg, bb = hsv_to_rgb(hue, 0.2, 1.0)
            pen = graphics.create_pen(rr, gg, bb)
            graphics.set_pen(pen)
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                graphics.pixel(x, y)

        gu.update(graphics)
        t += 0.045
        await uasyncio.sleep(0.012)

