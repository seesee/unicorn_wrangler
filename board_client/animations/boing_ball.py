import uasyncio
import math
import random

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT, MODEL

# "tick" logo in relative coordinates
LOGO_PIXELS = [
    (0, 8), (1, 8), (2, 8), (-1, 7), (0, 7), (1, 7), 
    (2, 7), (3, 7), (-2, 6), (-1, 6), (0, 6), (-3, 5), 
    (-2, 5), (-1, 5), (2, 6), (3, 6), (4, 6), (3, 5), 
    (4, 5), (5, 5), (4, 4), (5, 4), (6, 4), (5, 3), 
    (6, 3), (7, 3), (6, 2), (7, 2), (8, 2), (7, 1), 
    (8, 1), (9, 1), (8, 0), (9, 0), (10, 0), (9, -1), 
    (10, -1), (11, -1),
]

# logo bounding box
logo_xs = [x for x, y in LOGO_PIXELS]
logo_ys = [y for x, y in LOGO_PIXELS]
logo_min_x, logo_max_x = min(logo_xs), max(logo_xs)
logo_min_y, logo_max_y = min(logo_ys), max(logo_ys)
logo_width = logo_max_x - logo_min_x + 1
logo_height = logo_max_y - logo_min_y + 1
logo_offset_x = (WIDTH - logo_width) // 2 - logo_min_x
logo_offset_y = (HEIGHT - logo_height) // 2 - logo_min_y

LOGO_HUE_START = 0.6
LOGO_HUE_END = 0.0
LOGO_SATURATION = 1.0
LOGO_VALUE = 0.45
LOGO_HUE_SPEED = 0.1

def map_range(value, in_min, in_max, out_min, out_max, clamp=True):
    if in_max == in_min: return out_min
    t = (value - in_min) / (in_max - in_min)
    if clamp: t = max(0.0, min(1.0, t))
    return out_min + t * (out_max - out_min)

def draw_logo(graphics, t):
    hue_offset = (t * LOGO_HUE_SPEED) % 1.0
    for rel_x, rel_y in LOGO_PIXELS:
        px = rel_x + logo_offset_x
        py = rel_y + logo_offset_y
        if 0 <= px < WIDTH and 0 <= py < HEIGHT:
            progress = map_range(rel_x + rel_y, logo_min_x + logo_min_y, logo_max_x + logo_max_y, 0.0, 1.0)
            hue_from_position = map_range(progress, 0.0, 1.0, LOGO_HUE_START, LOGO_HUE_END)
            final_hue = (hue_from_position + hue_offset) % 1.0
            r, g, b = hsv_to_rgb(final_hue, LOGO_SATURATION, LOGO_VALUE)
            graphics.set_pen(graphics.create_pen(r, g, b))
            graphics.pixel(int(px), int(py))

async def run(graphics, gu, state, interrupt_event):
    # Room bounds scale with display size
    margin = max(2, min(WIDTH, HEIGHT) // 8)
    ROOM_X_MIN, ROOM_X_MAX = margin, WIDTH - margin - 1
    ROOM_Y_MIN, ROOM_Y_MAX = margin, HEIGHT - margin - 1
    ROOM_Z_MIN, ROOM_Z_MAX = 0, min(WIDTH, HEIGHT) // 2

    # Ball radius and speed scale with display size
    BASE_RADIUS = max(2, min(WIDTH, HEIGHT) // 7)
    BALL_RADIUS = BASE_RADIUS
    BALL_COLOR_1 = (0.0, 1.0, 1.0)  # red
    BALL_COLOR_2 = (0.0, 0.0, 1.0)  # white

    # For galactic, fix Y at center
    galactic_mode = (MODEL == "galactic")
    y_center = (ROOM_Y_MIN + ROOM_Y_MAX) / 2

    # Ball speed scales with display size
    speed_scale = max(0.15, min(WIDTH, HEIGHT) / 32.0)
    x = random.uniform(ROOM_X_MIN + BALL_RADIUS, ROOM_X_MAX - BALL_RADIUS)
    y = y_center if galactic_mode else random.uniform(ROOM_Y_MIN + BALL_RADIUS, ROOM_Y_MAX - BALL_RADIUS)
    z = random.uniform(ROOM_Z_MIN + BALL_RADIUS, ROOM_Z_MAX - BALL_RADIUS)
    vx = random.choice([-1, 1]) * (0.12 + random.random() * 0.25) * speed_scale
    vy = 0 if galactic_mode else random.choice([-1, 1]) * (0.12 + random.random() * 0.25) * speed_scale
    vz = random.choice([-1, 1]) * (0.18 + random.random() * 0.25) * speed_scale
    spin = random.uniform(0, 2 * math.pi)
    spin_rate = 0.12

    ELASTICITY = 1.00  # all we need for perpetual motion 

    t = 0.0

    # The "tick" floats at the midpoint in Z
    tick_z = (ROOM_Z_MIN + ROOM_Z_MAX) / 2

    FRAME_DELAY = 0.025  # ~40 FPS, adjust as needed

    while not interrupt_event.is_set():
        # Update ball position
        x += vx
        if not galactic_mode:
            y += vy
        z += vz

        bounced = False

        # bounce off X
        if x - BALL_RADIUS < ROOM_X_MIN:
            x = ROOM_X_MIN + BALL_RADIUS
            vx = -vx * ELASTICITY
            spin_rate += 0.08 * (1 if (vy if not galactic_mode else 1) > 0 else -1)
            bounced = True
        elif x + BALL_RADIUS > ROOM_X_MAX:
            x = ROOM_X_MAX - BALL_RADIUS
            vx = -vx * ELASTICITY
            spin_rate -= 0.08 * (1 if (vy if not galactic_mode else 1) > 0 else -1)
            bounced = True

        # bounce off Y (only if not galactic)
        if not galactic_mode:
            if y - BALL_RADIUS < ROOM_Y_MIN:
                y = ROOM_Y_MIN + BALL_RADIUS
                vy = -vy * ELASTICITY
                spin_rate -= 0.08 * (1 if vx > 0 else -1)
                bounced = True
            elif y + BALL_RADIUS > ROOM_Y_MAX:
                y = ROOM_Y_MAX - BALL_RADIUS
                vy = -vy * ELASTICITY
                spin_rate += 0.08 * (1 if vx > 0 else -1)
                bounced = True
        else:
            y = y_center  # always keep centered

        # bounce off Z (floor/ceiling)
        if z - BALL_RADIUS < ROOM_Z_MIN:
            z = ROOM_Z_MIN + BALL_RADIUS
            vz = -vz * ELASTICITY
            spin_rate += 0.12 * random.choice([-1, 1])
            bounced = True
        elif z + BALL_RADIUS > ROOM_Z_MAX:
            z = ROOM_Z_MAX - BALL_RADIUS
            vz = -vz * ELASTICITY
            spin_rate -= 0.12 * random.choice([-1, 1])
            bounced = True

        # dampen spin rate for variation
        spin_rate *= 0.98
        spin += spin_rate
        if spin > 2 * math.pi:
            spin -= 2 * math.pi
        elif spin < 0:
            spin += 2 * math.pi

        # adjust ball size/brightness on z axis (smaller, dimmer when further away)
        z_norm = (z - ROOM_Z_MIN) / (ROOM_Z_MAX - ROOM_Z_MIN)
        radius = BALL_RADIUS + 2.0 * z_norm
        brightness = 0.5 + 0.5 * z_norm

        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # Layering: draw tick and ball in correct order
        # If ball is "closer" (z > tick_z), draw tick first, then ball (ball in front)
        # If ball is "further" (z < tick_z), draw ball first, then tick (tick in front)
        if z < tick_z:
            # Ball is behind tick
            # Draw ball first, then tick
            draw_ball(graphics, x, y, radius, spin, brightness)
            draw_logo(graphics, t)
        else:
            # Ball is in front of tick
            # Draw tick first, then ball
            draw_logo(graphics, t)
            draw_ball(graphics, x, y, radius, spin, brightness)

        gu.update(graphics)
        t += 0.04
        await uasyncio.sleep(FRAME_DELAY)

def draw_ball(graphics, x, y, radius, spin, brightness):
    cx, cy = int(round(x)), int(round(y))
    r_int = int(round(radius))
    for px in range(cx - r_int, cx + r_int + 1):
        for py in range(cy - r_int, cy + r_int + 1):
            dx = px - cx
            dy = py - cy
            dist_sq = dx * dx + dy * dy
            if dist_sq <= r_int * r_int:
                # checker pattern based on angle/spin
                angle = math.atan2(dy, dx) + spin
                checker = int((angle / (math.pi / 4))) % 2
                if checker == 0:
                    h, s, v = (0.0, 1.0, 1.0)
                else:
                    h, s, v = (0.0, 0.0, 1.0)
                r, g, b = hsv_to_rgb(h, s, v * brightness)
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(px, py)
