import uasyncio
import random

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT
from collections import deque

# 9x5 pixel "pi" symbol (1 = pixel on, 0 = pixel off)
PI_BITMAP = [
    [0,1,0,1,1,1,1,1,1],
    [1,0,1,0,0,0,1,0,0],
    [0,0,1,0,0,0,1,0,0],
    [0,0,1,0,0,0,1,0,1],
    [0,1,0,0,0,0,1,1,0],
]

PI_W = len(PI_BITMAP[0])
PI_H = len(PI_BITMAP)

TRAIL_LENGTH = 4
BRIGHTNESS_FALLOFF = 0.2

# Super saiyan mode settings
SUPER_SAIYAN_TRAIL_LENGTH = 12  # Longer trail when powered up
SUPER_SAIYAN_BOUNCES = 8        # Number of bounces in super mode
SUPER_SAIYAN_CHANCE = 0.1       # 10% chance on bounce

def _draw_pi(graphics, x, y, pen):
    graphics.set_pen(pen)
    for row in range(PI_H):
        for col in range(PI_W):
            if PI_BITMAP[row][col]:
                px = x + col
                py = y + row
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.pixel(px, py)

async def run(graphics, gu, state, interrupt_event):
    trail = deque((), TRAIL_LENGTH)

    x = random.randint(0, WIDTH - PI_W)
    y = random.randint(0, HEIGHT - PI_H)
    dx = random.choice([-1, 1])
    dy = random.choice([-1, 1])

    hue = random.random()
    
    # Super saiyan mode state
    super_saiyan_mode = False
    super_saiyan_bounces_left = 0
    rainbow_time = 0.0

    black_pen = graphics.create_pen(0, 0, 0)

    while not interrupt_event.is_set():
        # Store previous position for super saiyan trail
        prev_x, prev_y = x, y
        trail.append((x, y))

        x += dx
        y += dy

        bounced = False

        if x < 0:
            x = 0
            dx = 1
            bounced = True
        elif x > WIDTH - PI_W:
            x = WIDTH - PI_W
            dx = -1
            bounced = True

        if y < 0:
            y = 0
            dy = 1
            bounced = True
        elif y > HEIGHT - PI_H:
            y = HEIGHT - PI_H
            dy = -1
            bounced = True

        # Handle bouncing and super saiyan mode activation
        if bounced:
            if super_saiyan_mode:
                # In super saiyan mode, count down bounces
                super_saiyan_bounces_left -= 1
                if super_saiyan_bounces_left <= 0:
                    # End super saiyan mode
                    super_saiyan_mode = False
                    # Return to normal trail length
                    trail = deque(trail, TRAIL_LENGTH)
                    # Set normal color
                    hue = random.random()
            else:
                # Not in super saiyan mode - check for activation
                if random.random() < SUPER_SAIYAN_CHANCE:
                    # Activate super saiyan mode!
                    super_saiyan_mode = True
                    super_saiyan_bounces_left = SUPER_SAIYAN_BOUNCES
                    rainbow_time = 0.0
                    # Extend trail length for super mode
                    trail = deque(trail, SUPER_SAIYAN_TRAIL_LENGTH)
                else:
                    # Normal bounce - change color
                    hue = (hue + 0.18 + random.uniform(0, 0.2)) % 1.0

        # Update rainbow animation time if in super saiyan mode
        if super_saiyan_mode:
            rainbow_time += 0.2  # Fast rainbow cycling
        
        # Never clear the screen - let normal pi gradually overwrite super saiyan residue
        # Draw normal trail in normal mode only
        if not super_saiyan_mode:
            # Draw black "eraser" pi at previous position to clean up residue
            if prev_x != x or prev_y != y:  # Only if pi moved
                _draw_pi(graphics, prev_x, prev_y, black_pen)
            
            # Draw normal fading trail - convert deque to list for MicroPython compatibility
            trail_list = list(trail)
            for i, (trail_x, trail_y) in enumerate(trail_list):
                # Fade the trail out
                v = BRIGHTNESS_FALLOFF ** (len(trail_list) - i)
                r, g, b = hsv_to_rgb(hue, 1.0, v)
                trail_pen = graphics.create_pen(r, g, b)
                _draw_pi(graphics, trail_x, trail_y, trail_pen)

        # Draw the current pi
        if super_saiyan_mode:
            # In super saiyan mode: leave a dim rainbow trail at the previous position
            # This creates persistent trails since we don't clear the screen
            if prev_x != x or prev_y != y:  # Only draw trail if pi actually moved
                trail_hue = rainbow_time % 1.0
                r, g, b = hsv_to_rgb(trail_hue, 0.7, 0.08)  # Much dimmer persistent trail like meteor_shower
                trail_pen = graphics.create_pen(r, g, b)
                _draw_pi(graphics, prev_x, prev_y, trail_pen)
            
            # Bright rainbow current pi
            current_hue = (rainbow_time + 0.3) % 1.0  # Offset from trail color
            r, g, b = hsv_to_rgb(current_hue, 1.0, 1.0)
        else:
            # Normal color
            r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
            
        color_pen = graphics.create_pen(r, g, b)
        _draw_pi(graphics, x, y, color_pen)

        gu.update(graphics)
        await uasyncio.sleep(0.12)
