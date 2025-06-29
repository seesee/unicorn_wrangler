import uasyncio
import math
import random
import gc

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT

def hypot(a, b):
    return math.sqrt(a * a + b * b)

async def run(graphics, gu, state, interrupt_event):

    class LightningBolt:
        def __init__(self, start_x, start_y, end_x, end_y, max_segments=40, intensity=1.0, speed=1.0, is_branch=False):
            self.start_x = start_x
            self.start_y = start_y
            self.end_x = end_x
            self.end_y = end_y
            self.max_segments = int(max_segments)
            self.intensity = intensity
            self.speed = speed
            self.is_branch = is_branch

            self.segments = []
            self.branches = []
            self.lifetime = random.randint(10, 25)
            self.completed = False
            self.age = 0
            self.hue_shift = random.uniform(-0.1, 0.1)  # More purple/blue shift

            self.current_x = float(start_x)
            self.current_y = float(start_y)
            self.path_points = self._plan_path()

        def _plan_path(self):
            points = []
            steps = int(max(10, abs(self.end_y - self.current_y)))
            if steps == 0: return []

            for i in range(1, steps + 1):
                t = i / steps
                nx = self.current_x + (self.end_x - self.current_x) * t
                ny = self.current_y + (self.end_y - self.current_y) * t
                jitter = random.uniform(-WIDTH * 0.1, WIDTH * 0.1)
                nx += jitter * (1 - t)  # Jitter decreases closer to the ground
                points.append((nx, ny))
            return points

        def grow(self):
            if self.completed: return

            steps_to_grow = int(max(1, self.speed * 2))
            for _ in range(steps_to_grow):
                if not self.path_points:
                    self.completed = True
                    break

                target_x, target_y = self.path_points.pop(0)
                self.segments.append([
                    self.current_x, self.current_y,
                    target_x, target_y,
                    self.intensity
                ])

                self.current_x, self.current_y = target_x, target_y

                # Forking logic
                if not self.is_branch and self.current_y < HEIGHT - 5 and random.random() < 0.15:
                    self._create_fork()

                if self.current_y >= HEIGHT - 1:
                    self.completed = True
                    break

        def _create_fork(self):
            angle_to_ground = math.atan2(self.end_y - self.current_y, self.end_x - self.current_x)
            num_forks = random.randint(1, 3)
            for _ in range(num_forks):
                branch_angle = angle_to_ground + random.uniform(-1.5, 1.5)
                branch_intensity = self.intensity * random.uniform(0.3, 0.6)
                branch_length_factor = random.uniform(0.3, 0.6)
                remaining_y = HEIGHT - self.current_y
                branch_end_x = self.current_x + math.cos(branch_angle) * remaining_y * branch_length_factor
                branch_end_y = self.current_y + math.sin(branch_angle) * remaining_y * branch_length_factor

                branch = LightningBolt(
                    self.current_x, self.current_y,
                    branch_end_x, branch_end_y,
                    max_segments=int(self.max_segments * 0.5),
                    intensity=branch_intensity,
                    speed=self.speed * random.uniform(0.8, 1.1),
                    is_branch=True
                )
                self.branches.append(branch)

        def update(self):
            self.age += 1
            if not self.completed:
                self.grow()
            for branch in self.branches:
                branch.update()
            self.branches = [b for b in self.branches if b.age < b.lifetime]

        def render(self, graphics, storm_brightness):
            if self.age >= self.lifetime: return

            fade_progress = max(0.0, (self.age - self.lifetime * 0.4) / (self.lifetime * 0.6))
            alpha = 1.0 - fade_progress

            for segment in self.segments:
                x1, y1, x2, y2, intensity = segment
                hue = 0.6 + self.hue_shift  # Shift towards blue/purple
                saturation = random.uniform(0.1, 0.3)
                flicker = random.uniform(0.8, 1.0)
                value = min(1.0, intensity * alpha * storm_brightness * flicker)

                r_int, g_int, b_int = hsv_to_rgb(hue, saturation, value)
                graphics.set_pen(graphics.create_pen(r_int, g_int, b_int))
                # Ensure coordinates are integers
                graphics.line(int(x1), int(y1), int(x2), int(y2))

            for branch in self.branches:
                branch.render(graphics, storm_brightness)

    class CloudSystem:
        def __init__(self):
            self.clouds = []
            self.initialize_clouds()

        def initialize_clouds(self):
            self.clouds = []
            num_clouds = random.randint(10, 20)
            for _ in range(num_clouds):
                self.clouds.append({
                    'x': random.uniform(0, WIDTH - 1),
                    'y': random.randint(0, HEIGHT // 3),
                    'width': random.randint(8, 20),
                    'height': random.randint(4, 8),
                    'speed': random.uniform(0.05, 0.2),
                    'darkness': random.uniform(0.6, 0.95)
                })

        def update(self):
            for cloud in self.clouds:
                cloud['x'] += cloud['speed'] * random.choice([-1, 1])
                if cloud['x'] > WIDTH + cloud['width']:
                    cloud['x'] = -cloud['width']
                elif cloud['x'] < -cloud['width']:
                    cloud['x'] = WIDTH + cloud['width']

        def render(self, graphics, storm_intensity):
            for cloud in self.clouds:
                darkness = min(0.98, cloud['darkness'] + storm_intensity * 0.2)
                value = 0.1 * (1 - darkness)
                r_int, g_int, b_int = hsv_to_rgb(0.65, 0.3, value)
                pen = graphics.create_pen(r_int, g_int, b_int)
                graphics.set_pen(pen)

                # Ensure coordinates are integers
                cx, cy = int(cloud['x']), int(cloud['y'])
                w, h = int(cloud['width']), int(cloud['height'])
                for y_offset in range(-h // 2, h // 2):
                    for x_offset in range(-w // 2, w // 2):
                        if (x_offset / (w/2))**2 + (y_offset / (h/2))**2 < 1:
                            graphics.pixel(cx + x_offset, cy + y_offset)

    class StormController:
        def __init__(self):
            self.lightning_bolts = []
            self.cloud_system = CloudSystem()
            self.intensity = 0.5
            self.target_intensity = 0.5
            self.flash_countdown = random.randint(50, 150)
            self.recent_flash_intensity = 0.0

        def update(self):
            self.intensity += (self.target_intensity - self.intensity) * 0.01
            if random.random() < 0.005:
                self.target_intensity = random.uniform(0.3, 1.0)

            self.recent_flash_intensity *= 0.85 # Faster decay for more flickering
            self.flash_countdown -= 1

            if self.flash_countdown <= 0:
                self._create_lightning()
                base_delay = 200 - self.intensity * 180
                self.flash_countdown = int(max(20, base_delay + random.uniform(-base_delay * 0.4, base_delay * 0.4)))

            self.lightning_bolts = [bolt for bolt in self.lightning_bolts if bolt.age < bolt.lifetime]
            for bolt in self.lightning_bolts:
                bolt.update()

            self.cloud_system.update()

        def _create_lightning(self):
            if random.random() < 0.4: # Chance for a flash without a bolt
                self.recent_flash_intensity = max(self.recent_flash_intensity, random.uniform(0.5, 1.0) * self.intensity)
                return

            start_x = random.randint(WIDTH // 4, WIDTH * 3 // 4)
            end_x = random.randint(0, WIDTH - 1)
            intensity = random.uniform(0.8, 1.2) * self.intensity
            speed = random.uniform(0.9, 1.6)

            bolt = LightningBolt(start_x, 0, end_x, HEIGHT - 1, intensity=intensity, speed=speed)
            self.lightning_bolts.append(bolt)
            self.recent_flash_intensity = max(self.recent_flash_intensity, intensity)

        def render(self, graphics):
            # Background gradient and flash
            flash = self.recent_flash_intensity
            for y in range(HEIGHT):
                t = y / (HEIGHT - 1)
                bg_val = 0.01 + t * 0.05 + flash * (0.3 + t * 0.7)
                bg_sat = 0.4 - t * 0.3
                r_int, g_int, b_int = hsv_to_rgb(0.6, bg_sat, bg_val)
                pen = graphics.create_pen(r_int, g_int, b_int)
                graphics.set_pen(pen)
                graphics.line(0, y, WIDTH - 1, y)

            self.cloud_system.render(graphics, self.intensity)

            storm_brightness = 0.8 + flash * 0.2
            for bolt in self.lightning_bolts:
                bolt.render(graphics, storm_brightness)

    storm = StormController()

    while not interrupt_event.is_set():
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        storm.update()
        storm.render(graphics)

        gu.update(graphics)
        gc.collect()

        await uasyncio.sleep(1 / 30) # 30 FPS
