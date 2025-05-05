import uasyncio
import math
import random

from animations.utils import hsv_to_rgb, fast_sin

async def run(graphics, gu, state, interrupt_event):
    # oscilloscope effect.
    WIDTH, HEIGHT = graphics.get_bounds()
    NUM_WAVES = 3
    MIN_SCROLL_SPEED = -0.3
    MAX_SCROLL_SPEED = 0.3
    MIN_FREQUENCY = 1.0
    MAX_FREQUENCY = 4.0
    MIN_AMPLITUDE = 0.5
    MAX_AMPLITUDE = HEIGHT / 2.0
    MIN_CHANGE_TIME = 2.0
    MAX_CHANGE_TIME = 5.0
    LERP_FACTOR = 0.05
    HUE_SPEED = 0.01

    ENABLE_AMP_MODULATION = True
    MIN_AMP_MOD_FREQ = 0.2
    MAX_AMP_MOD_FREQ = 1.5
    MIN_AMP_MOD_DEPTH = 0.3
    MAX_AMP_MOD_DEPTH = 0.8
    AMP_MOD_SPEED = 0.15

    MAX_WAVE_BRIGHTNESS = 200
    MAX_AMPLITUDE = max(MAX_AMPLITUDE, MIN_AMPLITUDE + 0.5)

    class Wave:
        def __init__(self, initial_hue):
            self.hue = initial_hue
            self.phase_shift = random.uniform(0, math.pi * 2)
            self.scroll_speed = random.uniform(MIN_SCROLL_SPEED, MAX_SCROLL_SPEED)
            self.frequency = random.uniform(MIN_FREQUENCY, MAX_FREQUENCY)
            self.amplitude = random.uniform(MIN_AMPLITUDE, MAX_AMPLITUDE)
            self.amp_mod_phase = random.uniform(0, math.pi * 2)
            self.amp_mod_frequency = random.uniform(MIN_AMP_MOD_FREQ, MAX_AMP_MOD_FREQ)
            self.amp_mod_depth = random.uniform(MIN_AMP_MOD_DEPTH, MAX_AMP_MOD_DEPTH)
            self.target_scroll_speed = self.scroll_speed
            self.target_frequency = self.frequency
            self.target_amplitude = self.amplitude
            self.target_amp_mod_frequency = self.amp_mod_frequency
            self.target_amp_mod_depth = self.amp_mod_depth
            self.time_to_next_change = random.uniform(MIN_CHANGE_TIME, MAX_CHANGE_TIME)

        def _randomize_targets(self):
            self.target_scroll_speed = random.uniform(MIN_SCROLL_SPEED, MAX_SCROLL_SPEED)
            self.target_frequency = random.uniform(MIN_FREQUENCY, MAX_FREQUENCY)
            self.target_amplitude = random.uniform(MIN_AMPLITUDE, MAX_AMPLITUDE)
            self.target_amp_mod_frequency = random.uniform(MIN_AMP_MOD_FREQ, MAX_AMP_MOD_FREQ)
            self.target_amp_mod_depth = random.uniform(MIN_AMP_MOD_DEPTH, MAX_AMP_MOD_DEPTH)
            self.time_to_next_change = random.uniform(MIN_CHANGE_TIME, MAX_CHANGE_TIME)

        def update(self, dt):
            self.time_to_next_change -= dt
            if self.time_to_next_change <= 0:
                self._randomize_targets()
            self.scroll_speed += (self.target_scroll_speed - self.scroll_speed) * LERP_FACTOR
            self.frequency += (self.target_frequency - self.frequency) * LERP_FACTOR
            self.amplitude += (self.target_amplitude - self.amplitude) * LERP_FACTOR
            self.amp_mod_frequency += (self.target_amp_mod_frequency - self.amp_mod_frequency) * LERP_FACTOR
            self.amp_mod_depth += (self.target_amp_mod_depth - self.amp_mod_depth) * LERP_FACTOR
            self.phase_shift += self.scroll_speed * dt * 10
            self.amp_mod_phase += AMP_MOD_SPEED * dt * 10
            self.hue = (self.hue + HUE_SPEED * dt) % 1.0

        def calculate_y(self, x, width, center_y):
            horizontal_stretch = math.pi * 2
            angle = (x / width) * horizontal_stretch + self.phase_shift
            wave_shape = fast_sin(angle * self.frequency)
            effective_amplitude = self.amplitude
            if ENABLE_AMP_MODULATION:
                mod_angle = (x / width) * math.pi * 2 * self.amp_mod_frequency + self.amp_mod_phase
                mod_sine_mapped = (fast_sin(mod_angle) + 1.0) / 2.0
                modulation_factor = 1.0 - self.amp_mod_depth * mod_sine_mapped
                effective_amplitude *= modulation_factor
            y_pos = wave_shape * effective_amplitude + center_y
            return y_pos

    center_y = HEIGHT / 2.0
    waves = [Wave(initial_hue=i / NUM_WAVES) for i in range(NUM_WAVES)]
    pixel_buffer = [[(0, 0, 0) for _ in range(HEIGHT)] for _ in range(WIDTH)]

    import utime
    last_time = utime.ticks_ms()

    while not interrupt_event.is_set():
        current_time = utime.ticks_ms()
        dt = utime.ticks_diff(current_time, last_time) / 1000.0
        last_time = current_time
        dt = min(dt, 0.1)

        for x in range(WIDTH):
            for y in range(HEIGHT):
                pixel_buffer[x][y] = (0, 0, 0)

        for wave in waves:
            wave.update(dt)
            r_base, g_base, b_base = hsv_to_rgb(wave.hue, 1.0, 1.0)
            r_wave = int(r_base * (MAX_WAVE_BRIGHTNESS / 255.0))
            g_wave = int(g_base * (MAX_WAVE_BRIGHTNESS / 255.0))
            b_wave = int(b_base * (MAX_WAVE_BRIGHTNESS / 255.0))
            last_y_pixel = None
            for x in range(WIDTH):
                y_pos = wave.calculate_y(x, WIDTH, center_y)
                y_pixel = int(y_pos + 0.5)
                y_pixel = max(0, min(HEIGHT - 1, y_pixel))
                if last_y_pixel is None:
                    current_r, current_g, current_b = pixel_buffer[x][y_pixel]
                    new_r = min(255, current_r + r_wave)
                    new_g = min(255, current_g + g_wave)
                    new_b = min(255, current_b + b_wave)
                    pixel_buffer[x][y_pixel] = (new_r, new_g, new_b)
                else:
                    x0, y0 = x - 1, last_y_pixel
                    x1, y1 = x, y_pixel
                    dx = abs(x1 - x0)
                    dy = abs(y1 - y0)
                    sx = 1
                    sy = 1 if y0 < y1 else -1
                    err = dx - dy
                    plot_x, plot_y = x0, y0
                    while True:
                        if 0 <= plot_x < WIDTH and 0 <= plot_y < HEIGHT:
                            current_r, current_g, current_b = pixel_buffer[plot_x][plot_y]
                            new_r = min(255, current_r + r_wave)
                            new_g = min(255, current_g + g_wave)
                            new_b = min(255, current_b + b_wave)
                            pixel_buffer[plot_x][plot_y] = (new_r, new_g, new_b)
                        if plot_x == x1 and plot_y == y1:
                            break
                        e2 = 2 * err
                        if e2 >= -dy:
                            err -= dy
                            plot_x += sx
                        if e2 <= dx:
                            err += dx
                            plot_y += sy
                last_y_pixel = y_pixel

        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        for x in range(WIDTH):
            for y in range(HEIGHT):
                r_final, g_final, b_final = pixel_buffer[x][y]
                if r_final > 0 or g_final > 0 or b_final > 0:
                    pen = graphics.create_pen(r_final, g_final, b_final)
                    graphics.set_pen(pen)
                    graphics.pixel(x, y)

        gu.update(graphics)
        await uasyncio.sleep(0.03)
