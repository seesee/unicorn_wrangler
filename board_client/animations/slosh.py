import uasyncio
import utime
import math
import random

from animations.utils import hsv_to_rgb, fast_sin, fast_cos

async def run(graphics, gu, state, interrupt_event):
    # sloshing water with foam, droplets, and dynamic lighting
    WIDTH, HEIGHT = graphics.get_bounds()
    aspect = WIDTH / HEIGHT

    # adaptive target height and amplitude
    if aspect < 1.5:  # square-ish
        TARGET_HEIGHT = HEIGHT * 0.55
        amplitude_scale = 1.5
    else:
        TARGET_HEIGHT = HEIGHT * 0.68
        amplitude_scale = 1.0

    DAMPING = 0.015
    SPREAD = 0.072
    GRAVITY = 0.018
    BREAKING_THRESHOLD = 0.65
    CHOPPINESS = 0.35

    WAVE_BASE_FREQUENCY = 0.15
    WAVE_PERIOD_MIN = 3.0
    WAVE_PERIOD_MAX = 6.0
    WAVE_STRENGTH_MIN = 0.5 * amplitude_scale
    WAVE_STRENGTH_MAX = 1.2 * amplitude_scale
    SWELL_AMPLITUDE = 0.12 * amplitude_scale
    SWELL_FREQUENCY = 0.2

    MAX_FOAM_PARTICLES = 45
    FOAM_LIFETIME = 1.2
    FOAM_SPAWN_VELOCITY = 0.25
    SPLASH_DROPLET_CHANCE = 0.6

    WIND_STRENGTH = 0.04
    WIND_VARIABILITY = 0.015
    WIND_CHANGE_PERIOD = 4.0

    WATER_DEEP_HUE = 0.60
    WATER_SHALLOW_HUE = 0.48
    WATER_SAT_SURFACE = 0.80
    WATER_SAT_DEEP = 0.95
    WATER_SURFACE_VAL = 0.75
    WATER_DEEP_VAL = 0.13

    HIGHLIGHT_STRENGTH = 0.25
    SURFACE_TENSION = 0.65
    MOONLIGHT_REFLECTION = 0.10
    MOONLIGHT_SIZE = 0.15

    SKY_HUE = 0.63
    SKY_SAT = 0.70
    SKY_VAL = 0.08
    HILL_HUE = 0.32
    HILL_SAT = 0.60
    HILL_VAL = 0.04
    STAR_CHANCE = 0.002
    STAR_BRIGHTNESS = 0.25

    SKY_PEN = graphics.create_pen(*hsv_to_rgb(SKY_HUE, SKY_SAT, SKY_VAL))
    HILL_PEN = graphics.create_pen(*hsv_to_rgb(HILL_HUE, HILL_SAT, HILL_VAL))
    STAR_PEN = graphics.create_pen(*hsv_to_rgb(0, 0, STAR_BRIGHTNESS))

    def map_range(value, in_min, in_max, out_min, out_max, clamp=True):
        if in_max == in_min:
            return out_min
        t = (value - in_min) / (in_max - in_min)
        if clamp:
            t = max(0.0, min(1.0, t))
        return out_min + t * (out_max - out_min)

    class WaterParticle:
        def __init__(self, x, y, vx, vy, lifetime=None):
            self.x = float(x)
            self.y = float(y)
            self.vx = float(vx)
            self.vy = float(vy)
            self.lifetime = lifetime or FOAM_LIFETIME
            self.max_lifetime = self.lifetime
            self.active = True
            self.type = "foam"

    class FoamParticle(WaterParticle):
        def __init__(self, x, y, vx, vy, lifetime=None):
            super().__init__(x, y, vx, vy, lifetime)
            self.type = "foam"
            self.lifetime = self.max_lifetime * random.uniform(0.7, 1.0)
        def update(self, dt, heights, wind_force):
            self.vx += wind_force * 0.4 * dt
            self.vy += GRAVITY * 0.4 * dt
            self.x += self.vx * dt * 12
            self.y += self.vy * dt * 12
            self.vx *= (1.0 - 0.3 * dt)
            self.vy *= (1.0 - 0.3 * dt)
            ix = int(self.x)
            if 0 <= ix < WIDTH:
                water_y = heights[ix]
                if self.y > water_y:
                    self.y = water_y
                    self.vy *= -0.1
                    self.vx *= 0.95
            self.lifetime -= dt
            self.active = self.lifetime > 0 and 0 <= self.x < WIDTH

    class DropletParticle(WaterParticle):
        def __init__(self, x, y, vx, vy, lifetime=None):
            super().__init__(x, y, vx, vy, lifetime or (FOAM_LIFETIME * 0.7))
            self.type = "droplet"
        def update(self, dt, heights, wind_force):
            self.vx += wind_force * 0.6 * dt
            self.vy += GRAVITY * dt * 1.5
            self.x += self.vx * dt * 15
            self.y += self.vy * dt * 15
            self.vx *= (1.0 - 0.1 * dt)
            self.vy *= (1.0 - 0.1 * dt)
            ix = int(self.x)
            if 0 <= ix < WIDTH:
                water_y = heights[ix]
                if self.y > water_y:
                    self.active = False
            self.lifetime -= dt
            self.active = self.lifetime > 0 and 0 <= self.x < WIDTH and self.y < HEIGHT

    heights = [float(TARGET_HEIGHT)] * WIDTH
    velocities = [0.0] * WIDTH
    tensions = [0.0] * WIDTH
    particles = []
    stars = []
    for _ in range(int(WIDTH * (HEIGHT * 0.6) * STAR_CHANCE)):
        stars.append((
            random.randint(0, WIDTH-1),
            random.randint(0, int(HEIGHT * 0.5)),
            random.uniform(0.5, 1.0)
        ))
    global_time = 0.0
    last_time = utime.ticks_ms()
    last_major_wave = 0.0
    next_wave_time = random.uniform(WAVE_PERIOD_MIN, WAVE_PERIOD_MAX)
    current_wind = random.uniform(-WIND_STRENGTH, WIND_STRENGTH)
    target_wind = current_wind
    last_wind_change = 0.0
    moonlight_pos = random.uniform(WIDTH * 0.25, WIDTH * 0.75)

    while not interrupt_event.is_set():
        current_time = utime.ticks_ms()
        dt = utime.ticks_diff(current_time, last_time) / 1000.0
        last_time = current_time
        dt = min(dt, 0.1)
        global_time += dt

        if global_time - last_wind_change > WIND_CHANGE_PERIOD:
            target_wind = random.uniform(-WIND_STRENGTH, WIND_STRENGTH)
            last_wind_change = global_time
        wind_diff = target_wind - current_wind
        current_wind += wind_diff * min(1.0, dt * 0.8)
        current_wind += random.uniform(-WIND_VARIABILITY, WIND_VARIABILITY) * dt
        current_wind = max(-WIND_STRENGTH*1.5, min(WIND_STRENGTH*1.5, current_wind))

        swell = fast_sin(global_time * SWELL_FREQUENCY) * SWELL_AMPLITUDE
        if global_time - last_major_wave > next_wave_time:
            wave_side = 0 if current_wind > 0 else WIDTH-1
            strength = random.uniform(WAVE_STRENGTH_MIN, WAVE_STRENGTH_MAX)
            for i in range(3):
                idx = wave_side + (i if wave_side == 0 else -i)
                if 0 <= idx < WIDTH:
                    velocities[idx] -= strength * (0.9 ** i)
            last_major_wave = global_time
            next_wave_time = random.uniform(WAVE_PERIOD_MIN, WAVE_PERIOD_MAX)

        spreads = [0.0] * WIDTH
        for i in range(WIDTH):
            left_idx = max(0, i-1)
            right_idx = min(WIDTH-1, i+1)
            left_diff = heights[i] - heights[left_idx]
            right_diff = heights[i] - heights[right_idx]
            tensions[i] = (left_diff + right_diff) * SURFACE_TENSION
            spreads[i] = SPREAD * (left_diff + right_diff)

        for i in range(WIDTH):
            forces = 0.0
            forces += GRAVITY * (TARGET_HEIGHT - heights[i])
            forces += spreads[i]
            height_above_baseline = max(0, TARGET_HEIGHT - heights[i])
            wind_exposure = min(1.0, height_above_baseline * 0.5)
            forces += current_wind * wind_exposure
            forces += swell * GRAVITY * 2
            if random.random() < CHOPPINESS * dt:
                forces += random.uniform(-0.01, 0.01)
            velocities[i] += forces * dt * 20
            velocities[i] *= (1.0 - DAMPING * dt * 15)
            velocities[i] -= tensions[i] * dt * 10
            heights[i] += velocities[i] * dt * 15

        for i in range(1, WIDTH-1):
            left_slope = heights[i-1] - heights[i]
            right_slope = heights[i+1] - heights[i]
            slope_diff = abs(left_slope - right_slope)
            is_breaking = False
            if (current_wind > 0 and right_slope > BREAKING_THRESHOLD) or \
               (current_wind < 0 and left_slope > BREAKING_THRESHOLD):
                is_breaking = True
            if slope_diff > BREAKING_THRESHOLD * 1.2:
                is_breaking = True
            if is_breaking and len(particles) < MAX_FOAM_PARTICLES and random.random() < 0.6:
                if heights[i] < TARGET_HEIGHT - 0.5:
                    spawn_count = random.randint(1, 3)
                    wind_dir = 1 if current_wind > 0 else -1
                    for _ in range(spawn_count):
                        foam_vx = FOAM_SPAWN_VELOCITY * wind_dir * random.uniform(0.7, 1.3)
                        foam_vy = -FOAM_SPAWN_VELOCITY * random.uniform(0.1, 0.3)
                        particles.append(FoamParticle(
                            i + random.uniform(-0.3, 0.3),
                            heights[i] - random.uniform(0, 0.3),
                            foam_vx, foam_vy
                        ))
                    if random.random() < SPLASH_DROPLET_CHANCE:
                        droplet_count = random.randint(1, 2)
                        for _ in range(droplet_count):
                            droplet_vx = FOAM_SPAWN_VELOCITY * wind_dir * random.uniform(0.5, 1.0)
                            droplet_vy = -FOAM_SPAWN_VELOCITY * random.uniform(1.0, 2.0)
                            particles.append(DropletParticle(
                                i + random.uniform(-0.2, 0.2),
                                heights[i] - random.uniform(0.3, 0.6),
                                droplet_vx, droplet_vy
                            ))

        active_particles = []
        for particle in particles:
            particle.update(dt, heights, current_wind)
            if particle.active:
                active_particles.append(particle)
        particles = active_particles

        moonlight_pos += current_wind * dt * 0.5
        if moonlight_pos < 0:
            moonlight_pos += WIDTH
        if moonlight_pos >= WIDTH:
            moonlight_pos %= WIDTH

        for y in range(int(HEIGHT * 0.7)):
            for x in range(WIDTH):
                graphics.set_pen(SKY_PEN)
                graphics.pixel(x, y)
        hill_start_y = int(HEIGHT * 0.7)
        for y in range(hill_start_y, HEIGHT):
            for x in range(WIDTH):
                graphics.set_pen(HILL_PEN)
                graphics.pixel(x, y)
        for x, y, brightness in stars:
            if random.random() < 0.9:
                graphics.set_pen(STAR_PEN)
                graphics.pixel(x, y)
        for x in range(WIDTH):
            h = heights[x]
            # clamp and fix bad values
            if not isinstance(h, float) or math.isnan(h) or math.isinf(h):
                h = TARGET_HEIGHT
                heights[x] = h
            water_y = int(h)
            water_y = max(0, min(HEIGHT-1, water_y))
            if 0 < x < WIDTH-1:
                normal_x = (heights[x+1] - heights[x-1]) * 0.5
            else:
                normal_x = 0
            wave_height_factor = max(0, (TARGET_HEIGHT - h) / 3.0)
            wave_height_factor = min(1.0, wave_height_factor)
            dist_from_moon = abs(x - moonlight_pos)
            moonlight_factor = max(0, 1.0 - (dist_from_moon / (WIDTH * MOONLIGHT_SIZE)))
            moonlight_factor = moonlight_factor ** 2
            for y in range(max(water_y, 0), HEIGHT):
                depth = (y - water_y) / max(1, (HEIGHT - water_y))
                hue = map_range(depth, 0, 1, WATER_SHALLOW_HUE, WATER_DEEP_HUE)
                sat = map_range(depth, 0, 1, WATER_SAT_SURFACE, WATER_SAT_DEEP)
                val = map_range(depth, 0, 1, WATER_SURFACE_VAL, WATER_DEEP_VAL)
                if y == water_y:
                    highlight = HIGHLIGHT_STRENGTH * wave_height_factor
                    highlight += abs(normal_x) * HIGHLIGHT_STRENGTH * 0.5
                    highlight += moonlight_factor * MOONLIGHT_REFLECTION
                    val = min(1.0, val + highlight)
                r, g, b = hsv_to_rgb(hue, sat, val)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(x, y)
        for particle in particles:
            ix, iy = int(particle.x), int(particle.y)
            if 0 <= ix < WIDTH and 0 <= iy < HEIGHT:
                life_factor = particle.lifetime / particle.max_lifetime
                if particle.type == "foam":
                    brightness = 0.7 + (life_factor * 0.3)
                    r, g, b = hsv_to_rgb(0.55, 0.1, brightness)
                else:
                    brightness = 0.5 + (life_factor * 0.5)
                    r, g, b = hsv_to_rgb(0.52, 0.3, brightness)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(ix, iy)
        gu.update(graphics)
        await uasyncio.sleep(0.016)
