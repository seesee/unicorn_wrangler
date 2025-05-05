import uasyncio
import math
import random
import gc

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

def hypot(a, b):
    return math.sqrt(a * a + b * b)

async def run(graphics, gu, state, interrupt_event):
    # storm effect

    class LightningBolt:
        def __init__(self, start_x, start_y, end_x, end_y, max_segments=40, intensity=1.0, speed=1.0):
            self.segments = []
            self.branches = []
            self.lifetime = random.randint(8, 20)
            self.progression = 0
            self.max_segments = max_segments
            self.intensity = intensity
            self.completed = False
            self.age = 0
            self.speed = speed
            self.hue_shift = random.uniform(-0.05, 0.05)
            self.current_x = start_x
            self.current_y = start_y
            self.end_x = end_x
            self.end_y = end_y
            self.angle = math.atan2(end_y - start_y, end_x - start_x)
            self.path_points = self._plan_path()

        def _plan_path(self):
            # plan lightning path
            points = []
            x, y = self.current_x, self.current_y
            steps = max(10, abs(self.end_y - self.current_y))
            for i in range(1, steps + 1):
                t = i / steps
                # interpolation
                nx = self.current_x + (self.end_x - self.current_x) * t
                ny = self.current_y + (self.end_y - self.current_y) * t
                # add horizontal jitter
                jitter = random.uniform(-WIDTH * 0.08, WIDTH * 0.08)
                nx += jitter * (1 - t)  # less jitter near the ground
                points.append((nx, ny))
            return points

        def grow(self):
            if self.completed:
                return
            steps_to_grow = max(1, int(self.speed * 2))
            for _ in range(steps_to_grow):
                if not self.path_points:
                    self.completed = True
                    break
                target_x, target_y = self.path_points.pop(0)
                segment_length = hypot(target_x - self.current_x, target_y - self.current_y)
                width = (1.0 + random.uniform(-0.2, 0.2)) * self.intensity
                width = max(1, min(3, width))
                brightness = 1.0 * self.intensity
                self.segments.append([
                    self.current_x, self.current_y,
                    target_x, target_y,
                    width, brightness
                ])
                self.current_x, self.current_y = target_x, target_y
                # allow forking (but not near ground)
                if (self.current_y < HEIGHT - 4 and random.random() < 0.08):
                    branch_angle = self.angle + random.uniform(-1.2, 1.2)
                    branch_intensity = self.intensity * random.uniform(0.4, 0.7)
                    branch_size = int(self.max_segments * random.uniform(0.2, 0.5))
                    branch_speed = self.speed * random.uniform(0.7, 1.0)
                    branch = LightningBolt(
                        self.current_x, self.current_y,
                        self.current_x + math.cos(branch_angle) * (HEIGHT - self.current_y),
                        HEIGHT - 1,
                        branch_size,
                        branch_intensity,
                        branch_speed
                    )
                    self.branches.append(branch)
                if self.current_y >= HEIGHT - 1:
                    self.completed = True
                    break

        def update(self):
            self.age += 1
            if not self.completed:
                self.grow()
            for branch in self.branches:
                branch.update()
            self.branches = [b for b in self.branches if b.age < b.lifetime]

        def render(self, graphics, storm_brightness):
            if self.age >= self.lifetime:
                return
            alpha = 1.0
            fade_start_time = self.lifetime * 0.5
            if self.age > fade_start_time:
                fade_duration = self.lifetime - fade_start_time
                if fade_duration > 0:
                    fade_progress = (self.age - fade_start_time) / fade_duration
                    alpha = 1.0 - fade_progress
                else:
                    alpha = 0.0
            alpha = max(0.0, alpha)
            num_segments = len(self.segments)
            if num_segments == 0: return
            segments_to_draw = int(self.progression * num_segments)
            for i in range(segments_to_draw):
                segment = self.segments[i]
                x1, y1, x2, y2, width, brightness = segment
                segment_progress = i / num_segments
                hue = 0.58 + self.hue_shift * (1 - segment_progress)
                saturation = 0.1 + 0.2 * segment_progress
                flicker = 0.9 + 0.1 * fast_sin(self.age * 0.8 + i * 0.5)
                base_value = min(1.0, brightness * alpha * storm_brightness * flicker)
                core_value = base_value
                r, g, b = hsv_to_rgb(hue, saturation, core_value)
                r_int, g_int, b_int = max(0, int(r)), max(0, int(g)), max(0, int(b))
                graphics.set_pen(graphics.create_pen(r_int, g_int, b_int))
                graphics.line(int(x1), int(y1), int(x2), int(y2))
                if base_value > 0.7 and width > 1:
                    glow_width = int(width * 0.5)
                    glow_value = base_value * 0.5
                    r_glow, g_glow, b_glow = hsv_to_rgb(hue, saturation * 0.7, glow_value)
                    rg_int, gg_int, bg_int = max(0, int(r_glow)), max(0, int(g_glow)), max(0, int(b_glow))
                    graphics.set_pen(graphics.create_pen(rg_int, gg_int, bg_int))
                    dx = x2 - x1
                    dy = y2 - y1
                    length_sq = dx*dx + dy*dy
                    if length_sq < 0.01: continue
                    length = math.sqrt(length_sq)
                    nx = -dy / length
                    ny = dx / length
                    for offset in range(1, glow_width + 1):
                        graphics.line(
                            int(x1 + nx * offset), int(y1 + ny * offset),
                            int(x2 + nx * offset), int(y2 + ny * offset)
                        )
                        graphics.line(
                            int(x1 - nx * offset), int(y1 - ny * offset),
                            int(x2 - nx * offset), int(y2 - ny * offset)
                        )
            for branch in self.branches:
                branch.render(graphics, storm_brightness)

    class CloudSystem:
        def __init__(self):
            self.clouds = []
            self.initialize_clouds()
            self.wind_speed = 0
            self.wind_target = 0
            self.next_wind_change = random.randint(200, 500)

        def initialize_clouds(self):
            self.clouds = []
            num_clouds = random.randint(8, 16)
            for _ in range(num_clouds):
                x = random.uniform(0, WIDTH - 1)
                y = random.randint(0, HEIGHT // 3)
                width = random.randint(5, 15)
                height = random.randint(3, 7)
                density = random.uniform(0.4, 0.9)
                speed = random.uniform(0.05, 0.2)
                darkness = random.uniform(0.5, 0.9)
                self.clouds.append([x, y, width, height, density, speed, darkness])

        def update(self):
            self.next_wind_change -= 1
            if self.next_wind_change <= 0:
                self.wind_target = random.uniform(-0.3, 0.3)
                self.next_wind_change = random.randint(200, 500)
            self.wind_speed += (self.wind_target - self.wind_speed) * 0.01
            for i in range(len(self.clouds)):
                cloud = self.clouds[i]
                x, y, width, height, density, speed, darkness = cloud
                x += (speed * random.choice([-1, 1]) + self.wind_speed * 0.5)
                if x > WIDTH + width:
                    x = -width
                elif x < -width:
                    x = WIDTH + width
                self.clouds[i][0] = x

        def render(self, graphics, storm_intensity):
            for cloud in self.clouds:
                x, y, width, height, density, speed, darkness = cloud
                intensity_boost = storm_intensity * 0.5
                cloud_darkness = darkness + intensity_boost * 0.3
                cloud_darkness = min(0.95, cloud_darkness)
                saturation = 0.2 + intensity_boost * 0.2
                value = 0.1 * (1 - cloud_darkness)
                value = max(0.0, value)
                r, g, b = hsv_to_rgb(0.65, saturation, value)
                r_int, g_int, b_int = max(0, int(r)), max(0, int(g)), max(0, int(b))
                graphics.set_pen(graphics.create_pen(r_int, g_int, b_int))
                center_x, center_y = int(x), int(y)
                half_width = width / 2.0
                half_height = height / 2.0
                min_draw_x = max(0, int(center_x - width))
                max_draw_x = min(WIDTH, int(center_x + width))
                min_draw_y = max(0, int(center_y - height))
                max_draw_y = min(HEIGHT, int(center_y + height))
                for cy in range(min_draw_y, max_draw_y):
                    for cx in range(min_draw_x, max_draw_x):
                        dx = (cx - center_x) / half_width if half_width > 0 else 0
                        dy = (cy - center_y) / half_height if half_height > 0 else 0
                        dist_sq = dx*dx + dy*dy
                        density_threshold_sq = density * density
                        if dist_sq < density_threshold_sq:
                            graphics.pixel(cx, cy)

    class StormController:
        def __init__(self):
            self.lightning_bolts = []
            self.cloud_system = CloudSystem()
            self.intensity = 0.5
            self.target_intensity = 0.5
            self.flash_countdown = random.randint(30, 100)
            self.recent_flash_intensity = 0
            self.bg_brightness = 0.02
            self.min_bg_brightness = 0.01
            self.cloud_shadow = 0.3

        def update(self):
            self.intensity += (self.target_intensity - self.intensity) * 0.01
            if random.random() < 0.003:
                self.target_intensity = random.uniform(0.2, 1.0)
            self.recent_flash_intensity *= 0.9
            self.flash_countdown -= 1
            if self.flash_countdown <= 0:
                self._create_lightning()
                base_delay = 180 - self.intensity * 150
                variation = base_delay * 0.5
                self.flash_countdown = max(10, int(base_delay + random.uniform(-variation, variation)))
            active_bolts = []
            for bolt in self.lightning_bolts:
                bolt.update()
                if not bolt.completed:
                    progression_step = 0.05 * bolt.speed * (0.5 + self.intensity * 0.5)
                    bolt.progression = min(1.0, bolt.progression + progression_step)
                if bolt.age < bolt.lifetime:
                    active_bolts.append(bolt)
            self.lightning_bolts = active_bolts
            self.cloud_system.update()
            target_shadow = 0.3 + self.intensity * 0.4
            self.cloud_shadow += (target_shadow - self.cloud_shadow) * 0.02

        def _create_lightning(self):
            strike_intensity = random.uniform(0.7, 1.0) * (0.5 + self.intensity * 0.5)
            if random.random() < 0.3:
                self.recent_flash_intensity = max(self.recent_flash_intensity, random.uniform(0.4, 0.7) * strike_intensity)
                return
            start_x = random.randint(WIDTH // 4, WIDTH * 3 // 4)
            start_y = 0
            end_x = random.randint(0, WIDTH - 1)
            end_y = HEIGHT - 1
            angle = math.atan2(end_y - start_y, end_x - start_x)
            max_segments = random.randint(20, 50)
            bolt_speed = random.uniform(0.8, 1.5) * (0.7 + self.intensity * 0.3)
            bolt = LightningBolt(
                start_x, start_y, end_x, end_y, max_segments,
                strike_intensity, bolt_speed
            )
            self.lightning_bolts.append(bolt)
            self.recent_flash_intensity = max(self.recent_flash_intensity, strike_intensity * random.uniform(0.8, 1.0))

        def render(self, graphics):
            ambient_flash = self.recent_flash_intensity * 0.5
            base_bg_brightness = self.min_bg_brightness + ambient_flash * 0.2
            for y in range(HEIGHT):
                gradient_t = y / max(1, HEIGHT - 1)
                gradient_brightness = base_bg_brightness + (0.04 * gradient_t) - (self.cloud_shadow * (1.0 - gradient_t))
                gradient_brightness = max(0.01, gradient_brightness)
                brightness = gradient_brightness + ambient_flash * gradient_t * 0.8
                brightness = min(1.0, brightness)
                saturation = 0.2 - gradient_t * 0.1
                saturation = max(0.0, saturation)
                r, g, b = hsv_to_rgb(0.65, saturation, brightness)
                r_int, g_int, b_int = max(0, int(r)), max(0, int(g)), max(0, int(b))
                graphics.set_pen(graphics.create_pen(r_int, g_int, b_int))
                graphics.line(0, y, WIDTH-1, y)
            self.cloud_system.render(graphics, self.intensity)
            storm_brightness = 0.9 + ambient_flash * 0.1
            for bolt in self.lightning_bolts:
                bolt.render(graphics, storm_brightness)

    storm = StormController()
    frame_count = 0

    while not interrupt_event.is_set():
        # clear display
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        storm.update()
        storm.render(graphics)
        gu.update(graphics)
        frame_count += 1
        if frame_count % 100 == 0:
            gc.collect()
        if storm.recent_flash_intensity > 0.1 or len(storm.lightning_bolts) > 0:
            await uasyncio.sleep(0.02)
        else:
            await uasyncio.sleep(0.04)
