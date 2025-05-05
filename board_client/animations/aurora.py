import uasyncio
import math
import random
import utime
import gc
import array

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

#import micropython # broke faster functions into utils.py, nothing else helped short of simplification and worse looks

async def run(graphics, gu, state, interrupt_event):
    # wavy line sim; best on galactic unicorn
    NUM_CURTAINS = 4

    aspect = WIDTH / HEIGHT
    # On square displays, try to make curtains fatter and more overlapping (TODO: find better settings for sqares)
    amplitude_scale = 1.0
    frequency_scale = 1.0
    if aspect > 1.0:  # galactic
        amplitude_scale = 1.5
        frequency_scale = 0.6
    if aspect <= 1.0:  # cosmic/stellar
        amplitude_scale = 2.0
        frequency_scale = 0.45

    MIN_Y_CENTRE = 1.0
    MAX_Y_CENTRE = HEIGHT - 2.0
    MIN_AMPLITUDE = 1.5 * amplitude_scale
    MAX_AMPLITUDE = 5.0 * amplitude_scale
    MIN_FREQUENCY = 0.15 * frequency_scale
    MAX_FREQUENCY = 0.7 * frequency_scale
    MIN_SPEED = -0.35
    MAX_SPEED = 0.35
    MIN_BRIGHTNESS = 0.02
    MAX_BRIGHTNESS = 0.95

    AURORA_COLOURS = [
        {"hue": 0.95, "weight": 18}, {"hue": 0.00, "weight": 20},
        {"hue": 0.05, "weight": 12}, {"hue": 0.30, "weight": 15},
        {"hue": 0.33, "weight": 10}, {"hue": 0.40, "weight": 8},
        {"hue": 0.65, "weight": 8}, {"hue": 0.75, "weight": 18},
        {"hue": 0.82, "weight": 25},
    ]
    TOTAL_COLOUR_WEIGHT = sum(colour["weight"] for colour in AURORA_COLOURS)

    MIN_CHANGE_TIME = 1.8
    MAX_CHANGE_TIME = 4.5
    LERP_FACTOR = 0.06
    QUICK_LERP_FACTOR = 0.25
    VERTICAL_FALLOFF = 1.4
    PULSATION_FREQUENCY = 0.15
    PULSATION_DEPTH = 0.35
    FLARE_CHANCE = 0.015
    FLOW_SPEED = 0.18
    DANCING_INTENSITY = 0.45

    TWO_PI = math.pi * 2.0
    INV_FALLOFF_FACTOR = 1.0 / (2.0 * VERTICAL_FALLOFF * VERTICAL_FALLOFF)
    INTENSITY_THRESHOLD = 0.005
    PULSATION_FREQ_TWO_PI = PULSATION_FREQUENCY * TWO_PI
    PULSATION_FREQ_1_63_TWO_PI = PULSATION_FREQUENCY * 1.63 * TWO_PI
    _FLARE_RAMP_UP_FACTOR = 0.3
    _FLARE_FADE_FACTOR = 0.7

    class Curtain:
        def __init__(self):
            self.hue = self._weighted_random_hue()
            self.y_centre = random.uniform(MIN_Y_CENTRE, MAX_Y_CENTRE)
            self.amplitude = random.uniform(MIN_AMPLITUDE, MAX_AMPLITUDE)
            self.frequency = random.uniform(MIN_FREQUENCY, MAX_FREQUENCY)
            self.speed = random.uniform(MIN_SPEED, MAX_SPEED)
            self.brightness = random.uniform(MIN_BRIGHTNESS, MAX_BRIGHTNESS)
            self.phase = random.uniform(0, TWO_PI)
            self.pulsation_phase_offset = random.uniform(0, TWO_PI)
            self.saturation = random.uniform(0.8, 1.0)
            self.secondary_freq = random.uniform(MIN_FREQUENCY * 1.5, MAX_FREQUENCY * 1.5)
            self.secondary_amp = random.uniform(MIN_AMPLITUDE * 0.3, MAX_AMPLITUDE * 0.6)
            self.flow_offset = random.uniform(0, TWO_PI)
            self.target_y_centre = self.y_centre
            self.target_amplitude = self.amplitude
            self.target_frequency = self.frequency
            self.target_speed = self.speed
            self.target_brightness = self.brightness
            self.target_hue = self.hue
            self.target_saturation = self.saturation
            self.flaring = False
            self.flare_intensity = 0.0
            self.flare_duration = 0.0
            self.flare_time = 0.0
            self.time_to_next_change = random.uniform(MIN_CHANGE_TIME, MAX_CHANGE_TIME)

        def _weighted_random_hue(self):
            r = random.uniform(0, TOTAL_COLOUR_WEIGHT)
            cumulative_weight = 0.0
            for colour in AURORA_COLOURS:
                cumulative_weight += float(colour["weight"])
                if r <= cumulative_weight:
                    variation = random.uniform(-0.04, 0.04)
                    hue = float(colour["hue"]) + variation
                    if hue < 0.0: hue += 1.0
                    elif hue >= 1.0: hue -= 1.0
                    return hue
            return random.uniform(0.0, 1.0)

        def _randomize_targets(self):
            self.target_y_centre = random.uniform(MIN_Y_CENTRE, MAX_Y_CENTRE)
            self.target_amplitude = random.uniform(MIN_AMPLITUDE, MAX_AMPLITUDE)
            self.target_frequency = random.uniform(MIN_FREQUENCY, MAX_FREQUENCY)
            self.target_speed = random.uniform(MIN_SPEED, MAX_SPEED)
            self.target_brightness = random.uniform(MIN_BRIGHTNESS, MAX_BRIGHTNESS)
            self.target_hue = self._weighted_random_hue()
            self.target_saturation = random.uniform(0.8, 1.0)
            self.secondary_freq = random.uniform(MIN_FREQUENCY * 1.5, MAX_FREQUENCY * 1.5)
            self.secondary_amp = random.uniform(MIN_AMPLITUDE * 0.3, MAX_AMPLITUDE * 0.6)
            self.time_to_next_change = random.uniform(MIN_CHANGE_TIME, MAX_CHANGE_TIME)

        def _trigger_flare(self):
            self.flaring = True
            self.flare_intensity = random.uniform(0.9, 1.0)
            self.flare_duration = random.uniform(0.4, 1.2)
            self.flare_time = 0.0

        def update(self, dt, global_time):
            self.time_to_next_change -= dt
            if self.time_to_next_change <= 0:
                self._randomize_targets()
            if not self.flaring and random.random() < FLARE_CHANCE:
                self._trigger_flare()
            flare_active = self.flaring
            flare_factor = 0.0
            if flare_active:
                self.flare_time += dt
                if self.flare_time >= self.flare_duration:
                    self.flaring = False
                    flare_active = False
                    self.flare_time = 0.0
                else:
                    ramp_up_time = self.flare_duration * _FLARE_RAMP_UP_FACTOR
                    if self.flare_time < ramp_up_time:
                        flare_factor = self.flare_time / ramp_up_time if ramp_up_time > 0.0 else 1.0
                    else:
                        fade_duration = self.flare_duration * _FLARE_FADE_FACTOR
                        flare_factor = 1.0 - ((self.flare_time - ramp_up_time) / fade_duration) if fade_duration > 0.0 else 0.0
                    if flare_factor < 0.0: flare_factor = 0.0
            lerp = QUICK_LERP_FACTOR if flare_active else LERP_FACTOR
            self.y_centre += (self.target_y_centre - self.y_centre) * LERP_FACTOR
            self.amplitude += (self.target_amplitude - self.amplitude) * LERP_FACTOR
            self.frequency += (self.target_frequency - self.frequency) * LERP_FACTOR
            self.speed += (self.target_speed - self.speed) * LERP_FACTOR
            sin1 = fast_sin(global_time * 8.31 + self.pulsation_phase_offset)
            sin2 = fast_sin(global_time * 12.71 + self.flow_offset)
            dancing_factor = 1.0 + DANCING_INTENSITY * (0.7 * sin1 + 0.3 * sin2)
            current_target_brightness = self.target_brightness * dancing_factor
            if flare_active:
                current_target_brightness = max(current_target_brightness, self.flare_intensity * flare_factor)
            self.brightness += (current_target_brightness - self.brightness) * lerp
            self.saturation += (self.target_saturation - self.saturation) * LERP_FACTOR
            hue_diff = self.target_hue - self.hue
            if hue_diff > 0.5: hue_diff -= 1.0
            elif hue_diff < -0.5: hue_diff += 1.0
            self.hue += hue_diff * LERP_FACTOR
            if self.hue < 0.0: self.hue += 1.0
            elif self.hue >= 1.0: self.hue -= 1.0
            self.phase += self.speed * dt * 18.0
            self.flow_offset += FLOW_SPEED * dt

        def get_intensity_at(self, norm_x, y, time_now):
            y_centre = self.y_centre
            amplitude = self.amplitude
            frequency = self.frequency
            phase = self.phase
            secondary_freq = self.secondary_freq
            secondary_amp = self.secondary_amp
            brightness = self.brightness
            pulsation_phase_offset = self.pulsation_phase_offset
            flow_offset = self.flow_offset

            angle = norm_x * TWO_PI + phase
            flow = fast_sin(time_now * 0.5 + norm_x * 10.0 + flow_offset) * 0.7
            sin1 = fast_sin(angle * frequency)
            sin2 = fast_sin(angle * secondary_freq + phase * 0.7)
            sin3 = fast_sin(angle * frequency * 3.1 + phase * 1.2)
            y_centre_at_x = (y_centre + amplitude * sin1 + secondary_amp * sin2 + amplitude * 0.3 * sin3 + flow)
            dy = y - y_centre_at_x
            dy2 = dy * dy
            intensity_factor = 1.0 / (1.0 + dy2 * INV_FALLOFF_FACTOR)
            if intensity_factor < 0.0: intensity_factor = 0.0
            if intensity_factor > 1.0: intensity_factor = 1.0
            t1 = time_now * PULSATION_FREQ_TWO_PI + pulsation_phase_offset
            t2 = time_now * PULSATION_FREQ_1_63_TWO_PI + flow_offset
            pulsation = (fast_sin(t1) + 1.0) * 0.35 + (fast_sin(t2) + 1.0) * 0.15
            current_brightness = brightness * (1.0 - PULSATION_DEPTH + pulsation * PULSATION_DEPTH)
            intensity = current_brightness * intensity_factor
            intensity = intensity * intensity
            if intensity < 0.0: intensity = 0.0
            if intensity > 1.0: intensity = 1.0
            return intensity

    curtains = [Curtain() for _ in range(NUM_CURTAINS)]
    last_time = utime.ticks_ms()
    global_time = 0.0
    # pre-calc normalised x values
    norm_x_values = array.array('f', [(x + 0.5) / WIDTH for x in range(WIDTH)])
    black_pen = graphics.create_pen(0, 0, 0)

    while not interrupt_event.is_set():
        current_time = utime.ticks_ms()
        dt = utime.ticks_diff(current_time, last_time) / 1000.0
        last_time = current_time
        if dt > 0.1: dt = 0.1
        global_time += dt

        for curtain in curtains:
            curtain.update(dt, global_time)

        graphics.set_pen(black_pen)
        graphics.clear()

        # main loop: for each pixel, sum curtain intensities (slow but pretty)
        for x in range(WIDTH):
            norm_x = norm_x_values[x]
            for y in range(HEIGHT):
                total_r = 0.0
                total_g = 0.0
                total_b = 0.0
                y_float = float(y)
                for curtain in curtains:
                    intensity = curtain.get_intensity_at(norm_x, y_float, global_time)
                    if intensity > INTENSITY_THRESHOLD:
                        r_cur, g_cur, b_cur = hsv_to_rgb(
                            curtain.hue, curtain.saturation, intensity
                        )
                        total_r += float(r_cur) * (1.0/255.0)
                        total_g += float(g_cur) * (1.0/255.0)
                        total_b += float(b_cur) * (1.0/255.0)
                if total_r > 1.0: total_r = 1.0
                if total_g > 1.0: total_g = 1.0
                if total_b > 1.0: total_b = 1.0
                r_i = int(total_r * 255.0 + 0.5)
                g_i = int(total_g * 255.0 + 0.5)
                b_i = int(total_b * 255.0 + 0.5)
                if r_i > 0 or g_i > 0 or b_i > 0:
                    pen = graphics.create_pen(max(0, r_i), max(0, g_i), max(0, b_i))
                    graphics.set_pen(pen)
                    graphics.pixel(x, y)

        gu.update(graphics)
        if global_time % 2 < 0.05:
            gc.collect()
        await uasyncio.sleep(0.001)
