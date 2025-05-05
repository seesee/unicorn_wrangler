import uasyncio
import random
import math

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT

async def run(graphics, gu, state, interrupt_event):
    # growing vines effect

    NUM_VINES = 8
    MAX_ACTIVE_VINES = 12
    MAX_LENGTH = 40 + WIDTH // 2
    BRANCH_PROB = 0.06
    ANGLE_VARIATION = math.pi / 5
    FLOWER_CHANCE = 0.04
    FLOWER_COLOURS = [
        (0.95, 0.7, 1.0),  # Pink
        (0.12, 0.8, 1.0),  # Yellow
        (0.0, 0.8, 1.0),   # Red
        (0.6, 0.7, 1.0),   # Blue
        (0.33, 0.5, 1.0),  # Light green
    ]
    
    VINE_SHADES = [
        (0.33, 1.0, 1.0),  # Bright green
        (0.18, 0.7, 0.7),  # Olive
        (0.08, 0.8, 0.5),  # Brown
    ]

    class Vine:
        __slots__ = ("x", "y", "angle", "shade", "length", "max_length", "alive")
        def __init__(self, x, y, angle, shade):
            self.x = x
            self.y = y
            self.angle = angle
            self.shade = shade
            self.length = 0
            self.max_length = random.randint(MAX_LENGTH // 2, MAX_LENGTH)
            self.alive = True

        def grow(self):
            if not self.alive:
                return
            # Move
            step = 1.0
            nx = self.x + math.cos(self.angle) * step
            ny = self.y + math.sin(self.angle) * step
            # Bounce off edges
            bounced = False
            if nx < 0:
                nx = 0
                self.angle = math.pi - self.angle + random.uniform(-ANGLE_VARIATION, ANGLE_VARIATION)
                bounced = True
            elif nx > WIDTH - 1:
                nx = WIDTH - 1
                self.angle = math.pi - self.angle + random.uniform(-ANGLE_VARIATION, ANGLE_VARIATION)
                bounced = True
            if ny < 0:
                ny = 0
                self.angle = -self.angle + random.uniform(-ANGLE_VARIATION, ANGLE_VARIATION)
                bounced = True
            elif ny > HEIGHT - 1:
                ny = HEIGHT - 1
                self.angle = -self.angle + random.uniform(-ANGLE_VARIATION, ANGLE_VARIATION)
                bounced = True
            if not bounced and random.random() < BRANCH_PROB:
                self.angle += random.uniform(-ANGLE_VARIATION, ANGLE_VARIATION)
            self.x, self.y = nx, ny
            self.length += 1
            if self.length >= self.max_length:
                self.alive = False

    t = 0.0

    while not interrupt_event.is_set():
        # Clear display
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # Start new vines
        vines = []
        for _ in range(NUM_VINES):
            if random.random() < 0.4:
                x = random.uniform(2, WIDTH - 3)
                y = HEIGHT - 1
                angle = -math.pi / 2 + random.uniform(-0.4, 0.4)
            elif random.random() < 0.5:
                side = random.choice([0, WIDTH - 1])
                x = side
                y = random.uniform(HEIGHT * 0.3, HEIGHT * 0.9)
                angle = math.pi if side == WIDTH - 1 else 0
                angle += random.uniform(-0.5, 0.5)
            else:
                x = WIDTH / 2 + random.uniform(-2, 2)
                y = HEIGHT / 2 + random.uniform(-2, 2)
                angle = random.uniform(-math.pi, math.pi)
            shade = random.choice(VINE_SHADES)
            vines.append(Vine(x, y, angle, shade))

        active_vines = list(vines)

        while active_vines and not interrupt_event.is_set():
            # Grow and draw all active vines
            new_vines = []
            for vine in active_vines:
                vine.grow()
                h, s, v = vine.shade
                px, py = int(round(vine.x)), int(round(vine.y))
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    # Draw vine
                    r, g, b = hsv_to_rgb(h, s, v)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(px, py)
                    # Maybe draw a flower
                    if random.random() < FLOWER_CHANCE:
                        fr, fg, fb = hsv_to_rgb(*random.choice(FLOWER_COLOURS))
                        graphics.set_pen(graphics.create_pen(fr, fg, fb))
                        graphics.pixel(px, py)
                # Occasionally branch
                if (vine.alive and random.random() < 0.03 and
                    len(active_vines) + len(new_vines) < MAX_ACTIVE_VINES):
                    branch_angle = vine.angle + random.uniform(-ANGLE_VARIATION, ANGLE_VARIATION)
                    branch_shade = random.choice(VINE_SHADES)
                    new_vines.append(Vine(vine.x, vine.y, branch_angle, branch_shade))
            # Prune dead vines
            active_vines = [v for v in active_vines if v.alive]
            # Add new branches
            active_vines.extend(new_vines)
            gu.update(graphics)
            t += 0.04
            await uasyncio.sleep(0.02)
