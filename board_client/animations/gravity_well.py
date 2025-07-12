import uasyncio
import random
import math
from collections import deque

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT


async def run(graphics, gu, state, interrupt_event):
    """
    A more advanced gravity well effect with particle trails and a glowing planet.
    """
    NUM_PARTICLES = 10 + WIDTH // 4
    CENTER_X = WIDTH / 2
    CENTER_Y = HEIGHT / 2
    PLANET_RADIUS = 3.5
    TRAIL_LENGTH = 5
    MIN_MASS = 0.1  # Increased range for mass
    MAX_MASS = 3.0  # Increased range for mass

    # Destruction flash parameters
    DESTRUCTION_FLASH_DURATION = 5  # Number of frames the white flash lasts

    # Particle dynamics parameters
    EVAPORATION_RATE = 0.0005  # Rate at which particles lose mass per frame

    class Particle:
        def __init__(self):
            self.history = deque((), TRAIL_LENGTH)
            self.reset()

        def reset(self):
            """
            Reset a particle to a new random position and velocity.
            """
            self.mass = random.uniform(MIN_MASS, MAX_MASS)
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(PLANET_RADIUS + 2, max(WIDTH, HEIGHT) / 2)
            self.x = CENTER_X + fast_cos(angle) * radius
            self.y = CENTER_Y + fast_sin(angle) * radius

            # Give particles an initial tangential velocity
            tangent_angle = angle + math.pi / 2
            speed = 1 / math.sqrt(radius) * 2
            self.vx = fast_cos(tangent_angle) * speed
            self.vy = fast_sin(tangent_angle) * speed

            self.history = deque((), TRAIL_LENGTH)
            for _ in range(TRAIL_LENGTH):
                self.history.append((self.x, self.y))

        def update(self, gravity_strength):
            """
            Update particle position based on gravity and handle mass evaporation.
            Returns (True, x, y) if a collision with the planet occurred, (False, None, None) otherwise.
            """
            # Mass evaporation
            self.mass -= EVAPORATION_RATE
            if self.mass < MIN_MASS:
                self.reset()
                return False, None, None  # Particle reset, no collision with planet

            dx = CENTER_X - self.x
            dy = CENTER_Y - self.y
            dist_sq = dx * dx + dy * dy

            if dist_sq < PLANET_RADIUS * PLANET_RADIUS:
                collision_x, collision_y = self.x, self.y # Capture position before reset
                self.reset()
                return True, collision_x, collision_y  # Indicate collision and position

            # Apply dynamic gravity strength
            force = self.mass * gravity_strength / max(dist_sq, 1.0)
            self.vx += dx * force
            self.vy += dy * force

            speed_sq = self.vx * self.vx + self.vy * self.vy
            if speed_sq > 2 * 2:
                scale = 2 / math.sqrt(speed_sq)
                self.vx *= scale
                self.vy *= scale

            self.x += self.vx
            self.y += self.vy
            self.history.appendleft((self.x, self.y))
            return False, None, None  # No collision

        def draw(self, t):
            """
            Draw the particle and its trail.
            """
            # Draw the trail
            for i, (x, y) in enumerate(self.history):
                brightness = 1.0 - (i / TRAIL_LENGTH)
                hue = 0.6 - (self.mass - MIN_MASS) / (MAX_MASS - MIN_MASS) * 0.6
                r, g, b = hsv_to_rgb(hue, 0.9, 0.8 * brightness * brightness)
                pen = graphics.create_pen(r, g, b)
                graphics.set_pen(pen)
                px, py = int(x), int(y)
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.pixel(px, py)

    def draw_planet(t, gravity_strength):
        """
        Draw a glowing planet in the center, with color varying by gravity strength.
        """
        for x in range(int(CENTER_X - PLANET_RADIUS), int(CENTER_X + PLANET_RADIUS) + 1):
            for y in range(int(CENTER_Y - PLANET_RADIUS), int(CENTER_Y + PLANET_RADIUS) + 1):
                if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                    dx = x - CENTER_X
                    dy = y - CENTER_Y
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist <= PLANET_RADIUS:
                        hue = (0.3 + (gravity_strength - 0.5) / 1.0 * 0.5) % 1.0
                        val = 1.0 - (dist / PLANET_RADIUS)
                        r, g, b = hsv_to_rgb(hue, 0.8, val * 0.9)
                        pen = graphics.create_pen(r, g, b)
                        graphics.set_pen(pen)
                        graphics.pixel(x, y)

    particles = [Particle() for _ in range(NUM_PARTICLES)]
    t = 0.0
    destruction_flashes = [] # List to store (x, y, timer) for flashes

    while not interrupt_event.is_set():
        gravity_strength = 1.0 + 0.5 * fast_sin(t * 0.5)

        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        draw_planet(t, gravity_strength)

        for p in particles:
            collided, col_x, col_y = p.update(gravity_strength)
            if collided:
                destruction_flashes.append((col_x, col_y, DESTRUCTION_FLASH_DURATION))
            p.draw(t)

        # Draw destruction flashes
        new_destruction_flashes = []
        for flash_x, flash_y, flash_timer in destruction_flashes:
            if flash_timer > 0:
                brightness = flash_timer / DESTRUCTION_FLASH_DURATION
                r, g, b = hsv_to_rgb(0.0, 0.0, brightness) # White flash
                flash_pen = graphics.create_pen(r, g, b)
                graphics.set_pen(flash_pen)
                px, py = int(flash_x), int(flash_y)
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.pixel(px, py)
                new_destruction_flashes.append((flash_x, flash_y, flash_timer - 1))
        destruction_flashes = new_destruction_flashes

        gu.update(graphics)
        t += 0.03
        await uasyncio.sleep(0.01)