import uasyncio
import math
import random

from animations.utils import hsv_to_rgb

async def run(graphics, gu, state, interrupt_event):
    # checker wipe. TODO: improve or nuke
    WIDTH, HEIGHT = graphics.get_bounds()
    WIPE_SPEED = 1.0
    CHECKER_SIZE = 4
    REVEAL_OFFSET = 0.6
    REST_DURATION = 2.5

    ALL_DIRECTIONS = ['ltr', 'rtl', 'ttb', 'btt', 'diag_tlbr', 'diag_trbl', 'expand', 'contract', 'spiral_in', 'spiral_out']
    ALL_MODES = ['pattern_crossfade', 'pattern_slide', 'pattern_zoom', 'pattern_ripple']
    MIN_WIPE_SPEED = 0.5
    MAX_WIPE_SPEED = 2.0
    MIN_CHECKER_SIZE = 3
    MAX_CHECKER_SIZE = 7
    MIN_REVEAL_OFFSET = 0.3
    MAX_REVEAL_OFFSET = 1.5

    def lerp(a, b, t):
        return a + (b - a) * t

    def ease_in_out(t):
        return t * t * (3 - 2 * t)

    def ease_out_elastic(t):
        t = min(1.0, max(0.0, t))
        p = 0.3
        return 1 - pow(2, -10 * t) * math.sin((t - p/4) * (2 * math.pi) / p)

    def lerp_hsv(hsv_a, hsv_b, t):
        h_a, s_a, v_a = hsv_a
        h_b, s_b, v_b = hsv_b
        hue_diff = h_b - h_a
        if hue_diff > 0.5: hue_diff -= 1.0
        elif hue_diff < -0.5: hue_diff += 1.0
        h = (h_a + hue_diff * t) % 1.0
        s = lerp(s_a, s_b, t)
        v = lerp(v_a, v_b, t)
        return h, s, v

    centre_x = (WIDTH - 1) / 2.0
    centre_y = (HEIGHT - 1) / 2.0

    wipe_progress = 0.0
    rest_timer = 0
    is_resting = False

    source_pattern = {
        'checker_size': 4,
        'colour_a_hsv': (0.0, 0.0, 0.0),
        'colour_b_hsv': (0.5, 1.0, 0.8),
        'offset_x': 0,
        'offset_y': 0
    }
    target_pattern = {
        'checker_size': 6,
        'colour_a_hsv': (0.3, 1.0, 0.8),
        'colour_b_hsv': (0.8, 1.0, 0.8),
        'offset_x': 2,
        'offset_y': 2
    }

    current_wipe_speed = WIPE_SPEED
    current_reveal_offset = REVEAL_OFFSET
    current_wipe_direction = 'ltr'
    current_reveal_mode = 'pattern_crossfade'
    current_max_progress = 0

    def is_checker_position(x, y, pattern):
        pattern_x = (x + pattern['offset_x']) // pattern['checker_size']
        pattern_y = (y + pattern['offset_y']) // pattern['checker_size']
        return (pattern_x + pattern_y) % 2 == 0

    def get_pattern_colour(x, y, pattern):
        if is_checker_position(x, y, pattern):
            return pattern['colour_a_hsv']
        else:
            return pattern['colour_b_hsv']

    def randomize_parameters():
        nonlocal current_wipe_speed, current_reveal_offset, current_wipe_direction
        nonlocal current_reveal_mode, current_max_progress, source_pattern, target_pattern

        target_duration = random.uniform(10.0, 25.0)
        source_pattern = target_pattern.copy()
        new_target = {
            'checker_size': random.randint(MIN_CHECKER_SIZE, MAX_CHECKER_SIZE),
            'offset_x': random.randint(0, 4),
            'offset_y': random.randint(0, 4)
        }
        start_hue = random.random()
        colour_strategy = random.random()
        if colour_strategy < 0.4:
            end_hue = (start_hue + 0.5) % 1.0
        elif colour_strategy < 0.7:
            end_hue = (start_hue + random.choice([-0.08, 0.08])) % 1.0
        else:
            end_hue = (start_hue + 0.33) % 1.0
        new_target['colour_a_hsv'] = (start_hue, random.uniform(0.7, 0.95), random.uniform(0.6, 0.9))
        new_target['colour_b_hsv'] = (end_hue, random.uniform(0.7, 0.95), random.uniform(0.7, 0.9))
        target_pattern = new_target
        current_reveal_offset = random.uniform(MIN_REVEAL_OFFSET, MAX_REVEAL_OFFSET)
        current_wipe_direction = random.choice(ALL_DIRECTIONS)
        current_reveal_mode = random.choice(ALL_MODES)
        max_checker_size = max(source_pattern['checker_size'], target_pattern['checker_size'])
        norm_w = WIDTH / max_checker_size
        norm_h = HEIGHT / max_checker_size
        norm_cx = centre_x / max_checker_size
        norm_cy = centre_y / max_checker_size
        diag_dist = math.sqrt(norm_w * norm_w + norm_h * norm_h)
        if current_wipe_direction in ('ltr', 'rtl'):
            max_p = norm_w
        elif current_wipe_direction in ('ttb', 'btt'):
            max_p = norm_h
        elif current_wipe_direction in ('diag_tlbr', 'diag_trbl'):
            max_p = norm_w + norm_h
        elif current_wipe_direction in ('expand', 'contract'):
            max_dist = max(norm_cx, norm_cy, norm_w - norm_cx - 1, norm_h - norm_cy - 1)
            max_p = max_dist
        elif current_wipe_direction in ('spiral_in', 'spiral_out'):
            max_p = diag_dist / 2
        else:
            max_p = max(norm_w, norm_h)
        baseline_max_progress = max_p + current_reveal_offset + 2.5
        current_wipe_speed = baseline_max_progress / target_duration
        current_wipe_speed = max(MIN_WIPE_SPEED, min(MAX_WIPE_SPEED, current_wipe_speed))
        current_max_progress = baseline_max_progress

    randomize_parameters()
    wipe_progress = 0.0

    while not interrupt_event.is_set():
        if is_resting:
            rest_timer += 0.05
            if rest_timer >= REST_DURATION:
                randomize_parameters()
                wipe_progress = 0.0
                is_resting = False
                rest_timer = 0
                await uasyncio.sleep(0.1)
            else:
                gu.update(graphics)
                await uasyncio.sleep(0.1)
                continue
        else:
            wipe_progress += current_wipe_speed * 0.05
            if wipe_progress >= current_max_progress:
                is_resting = True
                rest_timer = 0
                gu.update(graphics)
                await uasyncio.sleep(0.1)
                continue

        ref_size = max(source_pattern['checker_size'], target_pattern['checker_size'])
        for cy in range(HEIGHT):
            for cx in range(WIDTH):
                checker_set = ((cx // ref_size) + (cy // ref_size)) % 2
                square_progress_value = 0
                norm_x = cx / ref_size
                norm_y = cy / ref_size
                norm_w = WIDTH / ref_size
                norm_h = HEIGHT / ref_size
                norm_cx = centre_x / ref_size
                norm_cy = centre_y / ref_size

                if current_wipe_direction == 'ltr':
                    square_progress_value = norm_x
                elif current_wipe_direction == 'rtl':
                    square_progress_value = norm_w - norm_x - 1
                elif current_wipe_direction == 'ttb':
                    square_progress_value = norm_y
                elif current_wipe_direction == 'btt':
                    square_progress_value = norm_h - norm_y - 1
                elif current_wipe_direction == 'diag_tlbr':
                    square_progress_value = norm_x + norm_y
                elif current_wipe_direction == 'diag_trbl':
                    square_progress_value = (norm_w - norm_x - 1) + norm_y
                elif current_wipe_direction == 'expand':
                    square_progress_value = max(abs(norm_x - norm_cx), abs(norm_y - norm_cy))
                elif current_wipe_direction == 'contract':
                    max_dist = max(norm_cx, norm_cy, norm_w - norm_cx - 1, norm_h - norm_cy - 1)
                    dist = max(abs(norm_x - norm_cx), abs(norm_y - norm_cy))
                    square_progress_value = max_dist - dist
                elif current_wipe_direction == 'spiral_in':
                    dx, dy = norm_x - norm_cx, norm_y - norm_cy
                    angle = math.atan2(dy, dx) / (2 * math.pi) + 0.5
                    dist = math.sqrt(dx*dx + dy*dy)
                    square_progress_value = 2 * dist + angle
                elif current_wipe_direction == 'spiral_out':
                    dx, dy = norm_x - norm_cx, norm_y - norm_cy
                    angle = math.atan2(dy, dx) / (2 * math.pi) + 0.5
                    dist = math.sqrt(dx*dx + dy*dy)
                    max_dist = math.sqrt(norm_w*norm_w + norm_h*norm_h) / 2
                    square_progress_value = max_dist - (2 * dist + angle)

                reveal_threshold = square_progress_value + (checker_set * current_reveal_offset)

                if wipe_progress >= reveal_threshold:
                    transition_factor = min(1.0, (wipe_progress - reveal_threshold) * 1.2)
                    source_colour = get_pattern_colour(cx, cy, source_pattern)
                    target_colour = get_pattern_colour(cx, cy, target_pattern)
                    if current_reveal_mode == 'pattern_crossfade':
                        eased_t = ease_in_out(transition_factor)
                        colour_hsv = lerp_hsv(source_colour, target_colour, eased_t)
                    else:
                        colour_hsv = target_colour if transition_factor > 0.5 else source_colour
                    r, g, b = hsv_to_rgb(*colour_hsv)
                    graphics.set_pen(graphics.create_pen(int(r), int(g), int(b)))
                    graphics.pixel(cx, cy)
                else:
                    source_colour = get_pattern_colour(cx, cy, source_pattern)
                    r, g, b = hsv_to_rgb(*source_colour)
                    graphics.set_pen(graphics.create_pen(int(r), int(g), int(b)))
                    graphics.pixel(cx, cy)

        gu.update(graphics)
        await uasyncio.sleep(0.05)
