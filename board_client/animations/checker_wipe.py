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

# Fixed-point reciprocal optimization (Item 18) - removed cache as it was never hit

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
        
        # Choose relief direction for this entire slide (consistent across all checkers)
        slide_relief_inverted = random.choice([True, False])
        # Choose edge style for this entire slide
        slide_edge_style = random.randint(0, 9)  # 0-9 for consistent edge width per slide
        
        return {
            "pen1": graphics.create_pen(r1, g1, b1),
            "pen2": graphics.create_pen(r2, g2, b2),
            "base_color1": (r1, g1, b1),  # Store base colors for bas relief calculation
            "base_color2": (r2, g2, b2),
            "checker_size": random.randint(4, 9),
            "rotation_speed": random.uniform(0.1, 0.5),
            "scroll_x_scaled": 0,
            "scroll_y_scaled": 0,
            "angle_rad": 0.0,
            "slide_relief_inverted": slide_relief_inverted,  # Same relief direction for entire slide
            "slide_edge_style": slide_edge_style,  # Same edge style for entire slide
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
        
        # For now, revert to simple division as fixed-point math needs more precision
        # The performance gain isn't worth the complexity for this specific case
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

                # Optimize division operations with fixed-point reciprocal (Item 18)
                if use_reciprocal:
                    checker_x = (rotated_x * size_reciprocal) >> SHIFT_BITS
                    checker_y = (rotated_y * size_reciprocal) >> SHIFT_BITS
                else:
                    checker_x = rotated_x // size_scaled
                    checker_y = rotated_y // size_scaled

                is_color2 = (checker_x + checker_y) % 2 == 0
                
                # Apply bas relief effect to both colors
                if is_color2:
                    base_r, base_g, base_b = params["base_color2"]
                else:
                    base_r, base_g, base_b = params["base_color1"]
                
                # Calculate position within current checker square for lighting
                local_x = (rotated_x % size_scaled) / size_scaled  # 0.0 to 1.0 within square
                local_y = (rotated_y % size_scaled) / size_scaled
                
                # Use slide-consistent relief direction and edge style
                relief_inverted = params["slide_relief_inverted"]  # Same for entire slide
                falloff_type = params["slide_edge_style"]  # Same for entire slide
                
                # Determine edge width based on falloff type
                if falloff_type < 3:  # 30% - Sharp edges (1 pixel wide)
                    edge_width = 1.0 / max(1, size_scaled // SCALE)  # 1 pixel worth
                elif falloff_type < 6:  # 30% - Medium edges 
                    edge_width = 2.0 / max(1, size_scaled // SCALE)  # 2 pixels worth
                else:  # 40% - Soft edges
                    edge_width = 3.0 / max(1, size_scaled // SCALE)  # 3 pixels worth
                
                # Calculate distance from edges (0.0 = at edge, 0.5 = center)
                edge_dist_x = min(local_x, 1.0 - local_x)  # Distance from left/right edges
                edge_dist_y = min(local_y, 1.0 - local_y)  # Distance from top/bottom edges
                edge_dist = min(edge_dist_x, edge_dist_y)   # Distance from nearest edge
                
                # Default to flat center color
                brightness = 1.0
                
                # Apply edge lighting only near edges
                if edge_dist < edge_width:
                    # We're near an edge - determine which edge for lighting direction
                    at_top = local_y < edge_width
                    at_bottom = local_y > 1.0 - edge_width
                    at_left = local_x < edge_width  
                    at_right = local_x > 1.0 - edge_width
                    
                    # Calculate edge lighting based on which edge we're near
                    if relief_inverted:
                        # Inverted: brighten top/right edges, darken bottom/left edges
                        if at_top or at_right:
                            brightness = 1.0 + 0.7 * (1.0 - edge_dist / edge_width)  # Bright edges
                        elif at_bottom or at_left:
                            brightness = 1.0 - 0.7 * (1.0 - edge_dist / edge_width)  # Dark edges
                    else:
                        # Normal: darken top/right edges, brighten bottom/left edges  
                        if at_top or at_right:
                            brightness = 1.0 - 0.7 * (1.0 - edge_dist / edge_width)  # Dark edges
                        elif at_bottom or at_left:
                            brightness = 1.0 + 0.7 * (1.0 - edge_dist / edge_width)  # Bright edges
                
                # Apply lighting with bounds checking
                lit_r = max(0, min(255, int(base_r * brightness)))
                lit_g = max(0, min(255, int(base_g * brightness)))
                lit_b = max(0, min(255, int(base_b * brightness)))
                
                pen = graphics.create_pen(lit_r, lit_g, lit_b)
                
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
