import uasyncio
import math

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

# --- CONFIGURABLES ---
BALL_SIZE = 20  # pixels (diameter)
BOX_SIZE = 80   # virtual box (width and height)
BALL_SPEED = 1.2  # pixels per frame (tweak for smoothness)
SPIN_SPEED_X = 0.05  # radians per frame
SPIN_SPEED_Y = 0.08  # radians per frame

# --- AMIGA TICK LOGO (as bitmap array) ---
# Array is [row][col] where each row represents a y-coordinate from top to bottom
# x ranges from -3 to 11 (15 columns), y ranges from -1 to 8 (10 rows)
# Array indices: x_offset = 3, y_offset = 1 (to handle negative coordinates)
TICK_BITMAP = [
    [0,0,0,0,0,0,0,0,0,0,0,0,1,0,1],
    [0,0,0,0,0,0,0,0,0,0,0,1,0,1,0],
    [0,0,0,0,0,0,0,0,0,0,1,0,1,0,0],
    [0,0,0,0,0,0,0,0,0,1,0,1,0,0,0],
    [0,0,0,0,0,0,0,0,1,0,1,0,0,0,0],
    [0,0,0,0,0,0,0,1,0,1,0,0,0,0,0],
    [1,0,1,0,0,0,1,0,1,0,0,0,0,0,0],
    [0,1,0,1,0,1,0,1,0,0,0,0,0,0,0],
    [0,0,1,0,1,0,1,0,0,0,0,0,0,0,0],
    [0,0,0,1,1,1,0,0,0,0,0,0,0,0,0],
]

def draw_tick_rainbow(graphics, t):
    # Bitmap coordinates: x from -3 to 11, y from -1 to 8
    min_x, max_x = -3, 11
    min_y, max_y = -1, 8
    logo_w = max_x - min_x + 1  # 15
    logo_h = max_y - min_y + 1  # 10
    x_offset = 3  # to handle negative x coordinates
    y_offset = 1  # to handle negative y coordinates
    
    # Integer center (top-left of center pixel for even sizes)
    center_x = min_x + logo_w // 2  # 4
    center_y = min_y + logo_h // 2  # 3
    span = max(logo_w, logo_h) or 1

    # Center of display
    cx, cy = WIDTH // 2, HEIGHT // 2

    for row in range(len(TICK_BITMAP)):
        for col in range(len(TICK_BITMAP[row])):
            if TICK_BITMAP[row][col] == 1:
                # Convert array indices back to world coordinates
                rel_x = col - x_offset  # col 0 = x=-3
                rel_y = row - y_offset  # row 0 = y=-1
                
                # Offset so the tick's center is at the display center
                px = cx + (rel_x - center_x)
                py = cy + (rel_y - center_y)
                
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    # Rainbow: hue based on position and time
                    progress = ((rel_x - min_x) + (rel_y - min_y)) / (2 * span)
                    hue = (t * 0.12 + progress) % 1.0
                    r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(px, py)


def draw_ball(graphics, ball_x, ball_y, spin_x, spin_y, box_cx, box_cy, ball_radius, checker_squares=8):
    display_x0 = box_cx - WIDTH // 2
    display_y0 = box_cy - HEIGHT // 2

    s_x, c_x = fast_sin(spin_x), fast_cos(spin_x)
    s_y, c_y = fast_sin(spin_y), fast_cos(spin_y)
    ball_radius_sq = ball_radius * ball_radius
    inv_ball_radius = 1.0 / ball_radius
    checker_scale = (ball_radius * 2) / checker_squares

    for dx in range(-ball_radius, ball_radius + 1):
        for dy in range(-ball_radius, ball_radius + 1):
            dist_sq = dx*dx + dy*dy
            if dist_sq > ball_radius_sq:
                continue

            sx = int(ball_x + dx - display_x0)
            sy = int(ball_y + dy - display_y0)

            if 0 <= sx < WIDTH and 0 <= sy < HEIGHT:
                dz = math.sqrt(ball_radius_sq - dist_sq)

                # Inverse 3D rotation to find the point on the original texture sphere
                # This finds which point on the un-rotated sphere maps to the current screen pixel
                p_intermediate_z = -dy * s_x + dz * c_x
                
                px = dx * c_y - p_intermediate_z * s_y
                py = dy * c_x + dz * s_x
                pz = dx * s_y + p_intermediate_z * c_y

                # Generate a 3D checkerboard pattern from the un-rotated coordinates
                check_u = int(px / checker_scale)
                check_v = int(py / checker_scale)
                check_w = int(pz / checker_scale)

                if (check_u + check_v + check_w) % 2 == 0:
                    r, g, b = 255, 80, 30
                else:
                    r, g, b = 255, 255, 255

                shade = 0.7 + 0.3 * (dy * inv_ball_radius)
                r = int(r * shade)
                g = int(g * shade)
                b = int(b * shade)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(sx, sy)

async def run(graphics, gu, state, interrupt_event):
    box_cx = BOX_SIZE // 2
    box_cy = BOX_SIZE // 2
    ball_radius = BALL_SIZE // 2

    # Ball initial position
    ball_x = box_cx - BOX_SIZE // 4
    ball_y = box_cy - BOX_SIZE // 4
    angle = math.radians(35)
    vx = BALL_SPEED * math.cos(angle)
    vy = BALL_SPEED * math.sin(angle)

    # 3D rotation state
    spin_x, spin_y = 0.0, 0.0
    spin_x_vel = SPIN_SPEED_X
    spin_y_vel = SPIN_SPEED_Y

    t = 0.0

    while not interrupt_event.is_set():
        ball_x += vx
        ball_y += vy
        spin_x += spin_x_vel
        spin_y += spin_y_vel
        t += 0.016

        # Bounce off box edges and adjust spin
        if ball_x - ball_radius < 0:
            ball_x = ball_radius
            vx = abs(vx)
            spin_y_vel *= -1 # Reverse spin direction on vertical wall hit
            spin_x_vel = SPIN_SPEED_X * (1.0 + abs(vy) / BALL_SPEED) # Speed up/down based on graze angle
        elif ball_x + ball_radius > BOX_SIZE - 1:
            ball_x = BOX_SIZE - 1 - ball_radius
            vx = -abs(vx)
            spin_y_vel *= -1
            spin_x_vel = SPIN_SPEED_X * (1.0 + abs(vy) / BALL_SPEED)

        if ball_y - ball_radius < 0:
            ball_y = ball_radius
            vy = abs(vy)
            spin_x_vel *= -1 # Reverse spin direction on horizontal wall hit
            spin_y_vel = SPIN_SPEED_Y * (1.0 + abs(vx) / BALL_SPEED)
        elif ball_y + ball_radius > BOX_SIZE - 1:
            ball_y = BOX_SIZE - 1 - ball_radius
            vy = -abs(vy)
            spin_x_vel *= -1
            spin_y_vel = SPIN_SPEED_Y * (1.0 + abs(vx) / BALL_SPEED)

        # Clear display
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # Draw tick logo (centered in display, rainbow)
        draw_tick_rainbow(graphics, t)

        # Draw ball (only if it overlaps the display)
        draw_ball(graphics, ball_x, ball_y, spin_x, spin_y, box_cx, box_cy, ball_radius)

        gu.update(graphics)
        await uasyncio.sleep(0.016)  # ~60 FPS
