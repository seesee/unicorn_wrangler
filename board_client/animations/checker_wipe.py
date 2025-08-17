import uasyncio
import math
import random
import utime

from animations.utils import hsv_to_rgb, SIN_TABLE, COS_TABLE
from uw.hardware import WIDTH, HEIGHT

CONFIG_CHANGE_INTERVAL_S = 20.0
WIPE_DURATION_S = 1.5
SCROLL_SPEED_X = 4.0
SCROLL_SPEED_Y = 2.0
ZOOM_SPEED = 0.15
ZOOM_MIN = 0.7
ZOOM_MAX = 1.3

SCALE = 1024

# Pre-scaled trigonometric tables at import time (Item 19)
SIN_TABLE_PRESCALED = [int(s * SCALE) for s in SIN_TABLE]
COS_TABLE_PRESCALED = [int(c * SCALE) for c in COS_TABLE]

# Pre-computed reciprocals for division optimization (Item 18)
RECIPROCAL_CACHE = {}
for size in range(1, 20):  # Common checker sizes
    RECIPROCAL_CACHE[size] = SCALE // size if size > 0 else SCALE

async def run(graphics, gu, state, interrupt_event):
    centre_x_scaled = int(((WIDTH - 1) / 2.0) * SCALE)
    centre_y_scaled = int(((HEIGHT - 1) / 2.0) * SCALE)

    # Use pre-scaled tables (Item 19)
    SIN_TABLE_SCALED = SIN_TABLE_PRESCALED
    COS_TABLE_SCALED = COS_TABLE_PRESCALED

    def get_scaled_trig(angle, table):
        angle %= (2 * math.pi)
        if angle < 0: angle += (2 * math.pi)
        idx = int(angle / (2 * math.pi) * len(SIN_TABLE))
        return table[idx % len(table)]

    def create_random_params():
        # Ensure distinct colors by guaranteeing hue separation and brightness contrast
        h1 = random.random()
        h2 = (h1 + random.uniform(0.4, 0.6)) % 1.0  # Ensure at least 40% hue separation
        
        # Ensure brightness contrast - one bright, one dim or vice versa
        if random.choice([True, False]):
            s1, s2 = random.uniform(0.9, 1.0), random.uniform(0.8, 1.0)
            v1, v2 = random.uniform(0.8, 1.0), random.uniform(0.4, 0.6)  # Bright vs dim
        else:
            s1, s2 = random.uniform(0.8, 1.0), random.uniform(0.9, 1.0) 
            v1, v2 = random.uniform(0.4, 0.6), random.uniform(0.8, 1.0)  # Dim vs bright
        
        r1, g1, b1 = hsv_to_rgb(h1, s1, v1)
        r2, g2, b2 = hsv_to_rgb(h2, s2, v2)
        return {
            "pen1": graphics.create_pen(r1, g1, b1),
            "pen2": graphics.create_pen(r2, g2, b2),
            "checker_size": random.randint(4, 9),
            "rotation_speed": random.uniform(0.1, 0.5),
            "scroll_x_scaled": 0,
            "scroll_y_scaled": 0,
            "angle_rad": 0.0,
        }

    def update_pattern_state(params, delta_t_s, zoom_scaled):
        params["angle_rad"] += params["rotation_speed"] * delta_t_s
        
        size_scaled = params["checker_size"] * zoom_scaled
        period_scaled = 2 * size_scaled if size_scaled > 0 else 1

        params["scroll_x_scaled"] = (params["scroll_x_scaled"] + int(SCROLL_SPEED_X * delta_t_s * SCALE)) % period_scaled
        params["scroll_y_scaled"] = (params["scroll_y_scaled"] + int(SCROLL_SPEED_Y * delta_t_s * SCALE)) % period_scaled

    def draw_pattern(params, start_x, end_x, zoom_scaled):
        if start_x >= end_x: return

        # Pre-calculate transformation matrix once (Item 17)
        sin_angle = get_scaled_trig(params["angle_rad"], SIN_TABLE_SCALED)
        cos_angle = get_scaled_trig(params["angle_rad"], COS_TABLE_SCALED)
        size_scaled = params["checker_size"] * zoom_scaled
        if size_scaled < 1: size_scaled = 1
        
        # Optimize division with reciprocal multiplication (Item 18)
        if size_scaled in RECIPROCAL_CACHE:
            size_reciprocal = RECIPROCAL_CACHE[size_scaled]
            use_reciprocal = True
        else:
            use_reciprocal = False
        
        # Pre-calculate scroll offsets (Item 17)
        scroll_x_offset = params["scroll_x_scaled"]
        scroll_y_offset = params["scroll_y_scaled"]
        
        # Pre-calculate common values (Item 17)
        cos_div_scale = cos_angle // SCALE if cos_angle != 0 else 0
        sin_div_scale = sin_angle // SCALE if sin_angle != 0 else 0

        for y in range(HEIGHT):
            # Pre-calculate y-dependent values once per row (Item 17)
            dy = y * SCALE - centre_y_scaled
            dy_cos_component = dy * cos_angle
            dy_sin_component = dy * sin_angle
            
            for x in range(start_x, end_x):
                dx = x * SCALE - centre_x_scaled

                # Use pre-calculated transformation matrix (Item 17)
                rotated_x = (dx * cos_angle - dy_cos_component) // SCALE + scroll_x_offset
                rotated_y = (dx * sin_angle + dy_sin_component) // SCALE + scroll_y_offset

                # Optimize division operations (Item 18)
                if use_reciprocal:
                    # Use bit shifts for power-of-2 sizes or reciprocal multiplication
                    if size_scaled & (size_scaled - 1) == 0:  # Power of 2
                        shift_amount = size_scaled.bit_length() - 1
                        checker_x = rotated_x >> shift_amount
                        checker_y = rotated_y >> shift_amount
                    else:
                        checker_x = (rotated_x * size_reciprocal) >> 10  # Approximate division
                        checker_y = (rotated_y * size_reciprocal) >> 10
                else:
                    checker_x = rotated_x // size_scaled
                    checker_y = rotated_y // size_scaled

                pen = params["pen2"] if (checker_x + checker_y) % 2 == 0 else params["pen1"]
                graphics.set_pen(pen)
                graphics.pixel(x, y)

    last_frame_time_ms = utime.ticks_ms()
    last_change_time_s = last_frame_time_ms / 1000.0
    in_transition = False
    transition_start_time = 0.0
    zoom_phase_rad = 0.0

    current_params = create_random_params()
    next_params = None

    while not interrupt_event.is_set():
        current_time_ms = utime.ticks_ms()
        delta_t_s = utime.ticks_diff(current_time_ms, last_frame_time_ms) / 1000.0
        last_frame_time_ms = current_time_ms
        current_time_s = current_time_ms / 1000.0

        zoom_phase_rad += ZOOM_SPEED * delta_t_s
        zoom_normalized = (math.sin(zoom_phase_rad) + 1.0) / 2.0
        current_zoom_scaled = int((ZOOM_MIN + (ZOOM_MAX - ZOOM_MIN) * zoom_normalized) * SCALE)
        if current_zoom_scaled < 1: current_zoom_scaled = 1

        update_pattern_state(current_params, delta_t_s, current_zoom_scaled)
        if in_transition and next_params:
            update_pattern_state(next_params, delta_t_s, current_zoom_scaled)

        if not in_transition and current_time_s - last_change_time_s >= CONFIG_CHANGE_INTERVAL_S:
            in_transition = True
            transition_start_time = current_time_s
            next_params = create_random_params()

        draw_pattern(current_params, 0, WIDTH, current_zoom_scaled)

        if in_transition and next_params:
            transition_elapsed = current_time_s - transition_start_time
            progress = min(1.0, transition_elapsed / WIPE_DURATION_S)
            wipe_line_x = int(progress * WIDTH)

            draw_pattern(next_params, 0, wipe_line_x, current_zoom_scaled)

            if progress >= 1.0:
                in_transition = False
                current_params = next_params
                next_params = None
                last_change_time_s = current_time_s

        gu.update(graphics)
        await uasyncio.sleep(0.01)  # 10ms = 0.01s
