import uasyncio
import random
import math
import utime
from collections import deque

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT, MODEL
from uw.config import config

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def get_datetime():
    try:
        import machine
        dt = machine.RTC().datetime()
        return dt
    except Exception:
        t = utime.localtime()
        return (t[0], t[1], t[2], (t[6]+1)%7, t[3], t[4], t[5], 0)

async def run(graphics, gu, state, interrupt_event):
    dt = get_datetime()
    year = dt[0]
    if year < 2025:
        # RTC not set, skip this animation
        return
    if MODEL == "galactic":
        await run_bouncing_datetime(graphics, gu, state, interrupt_event)
    else:
        await run_analog_clock(graphics, gu, state, interrupt_event)

async def run_bouncing_datetime(graphics, gu, state, interrupt_event):
    graphics.set_font("bitmap6")
    
    # Trail settings
    TRAIL_LENGTH = 4
    BRIGHTNESS_FALLOFF = 0.3
    trail = deque((), TRAIL_LENGTH)
    
    # Get actual font metrics by measuring a sample string
    sample_text = "00:00"
    actual_text_width = graphics.measure_text(sample_text, 1)
    actual_text_height = 8  # bitmap6 font is 8 pixels tall
    
    # Start at a random position that fits the text properly
    x = random.randint(0, max(0, WIDTH - actual_text_width))
    y = random.randint(0, max(0, HEIGHT - actual_text_height))
    dx = random.choice([-1, 1])
    dy = random.choice([-1, 1])
    hue = random.random()
    
    black_pen = graphics.create_pen(0, 0, 0)

    while not interrupt_event.is_set():
        # Add current position to trail
        trail.append((x, y))
        
        dt = get_datetime()
        year, month, mday, wday, hour, minute, second, _ = dt
        if year < 2025:
            return
        day_str = DAYS[wday % 7]
        
        #time_str = "{:02d}:{:02d}:{:02d}".format(hour, minute, second)
        time_str = "{:02d}:{:02d}".format(hour, minute)
        date_str = "{:02d}/{:02d}/{}".format(mday, month, year)
        msg = f"{time_str}"

        # Get actual text dimensions for this specific text
        text_width = graphics.measure_text(msg, 1)
        text_height = actual_text_height  # Use the measured font height
        
        # Adjust text width to account for extra spacing in measure_text
        # For "00:00" format, actual rendered width is typically 2 pixels less
        adjusted_text_width = max(1, text_width - 2)

        # Move by exactly one pixel diagonally
        x += dx
        y += dy

        bounced = False

        # Proper boundary checking using adjusted text dimensions
        if x < 0:
            x = 0
            dx = 1
            bounced = True
        elif x > WIDTH - adjusted_text_width:
            x = WIDTH - adjusted_text_width
            dx = -1
            bounced = True

        if y < 0:
            y = 0
            dy = 1
            bounced = True
        elif y > HEIGHT - text_height:
            y = HEIGHT - text_height
            dy = -1
            bounced = True

        if bounced:
            hue = (hue + 0.18 + random.uniform(0, 0.2)) % 1.0

        # Clear screen
        graphics.set_pen(black_pen)
        graphics.clear()

        # Draw trailing time displays with fade - convert deque to list for MicroPython
        trail_list = list(trail)
        for i, (trail_x, trail_y) in enumerate(trail_list):
            # Fade the trail out
            v = BRIGHTNESS_FALLOFF ** (len(trail_list) - i)
            r, g, b = hsv_to_rgb(hue, 1.0, v)
            trail_pen = graphics.create_pen(r, g, b)
            graphics.set_pen(trail_pen)
            graphics.text(msg, trail_x, trail_y, -1, 1)

        # Draw the current bright time display
        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
        current_pen = graphics.create_pen(r, g, b)
        graphics.set_pen(current_pen)
        graphics.text(msg, x, y, -1, 1)

        gu.update(graphics)
        await uasyncio.sleep(0.13)

async def run_analog_clock(graphics, gu, state, interrupt_event):
    center_x = WIDTH // 2
    center_y = HEIGHT // 2
    radius = min(WIDTH, HEIGHT) // 2 - 2
    hand_lengths = {
        "hour": int(radius * 0.5),
        "minute": int(radius * 0.8),
        "second": int(radius * 0.95),
    }
    font_height = -4 
    graphics.set_font("bitmap6")

    while not interrupt_event.is_set():
        dt = get_datetime()
        year, month, mday, wday, hour, minute, second, _ = dt
        if year < 2025:
            return
        day_str = DAYS[wday % 7]

        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        num_points = 60
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            x = int(center_x + math.cos(angle) * radius)
            y = int(center_y + math.sin(angle) * radius)
            if i % 5 == 0:
                r, g, b = hsv_to_rgb(0.6, 0.2, 1.0)
            else:
                r, g, b = hsv_to_rgb(0.6, 0.1, 0.4)
            graphics.set_pen(graphics.create_pen(r, g, b))
            graphics.pixel(x, y)

        w = graphics.measure_text(day_str, 1)
        graphics.set_pen(graphics.create_pen(89, 89, 0))
        graphics.text(day_str, center_x - w // 2, center_y - font_height // 2, -1, 1)

        hour_angle = 2 * math.pi * ((hour % 12) + minute / 60.0) / 12.0 - math.pi/2
        hx = int(center_x + math.cos(hour_angle) * hand_lengths["hour"])
        hy = int(center_y + math.sin(hour_angle) * hand_lengths["hour"])
        r, g, b = hsv_to_rgb(0.4, 0.7, 1.0)
        graphics.set_pen(graphics.create_pen(r, g, b))
        graphics.line(center_x, center_y, hx, hy)

        min_angle = 2 * math.pi * (minute + second / 60.0) / 60.0 - math.pi/2
        mx = int(center_x + math.cos(min_angle) * hand_lengths["minute"])
        my = int(center_y + math.sin(min_angle) * hand_lengths["minute"])
        r, g, b = hsv_to_rgb(0.3, 0.7, 1.0)
        graphics.set_pen(graphics.create_pen(r, g, b))
        graphics.line(center_x, center_y, mx, my)

        sec_angle = 2 * math.pi * (second) / 60.0 - math.pi/2
        sx = int(center_x + math.cos(sec_angle) * hand_lengths["second"])
        sy = int(center_y + math.sin(sec_angle) * hand_lengths["second"])
        r, g, b = hsv_to_rgb(0.0, 1.0, 1.0)
        graphics.set_pen(graphics.create_pen(r, g, b))
        graphics.line(center_x, center_y, sx, sy)

        graphics.set_pen(graphics.create_pen(255, 255, 255))
        graphics.pixel(center_x, center_y)

        gu.update(graphics)
        await uasyncio.sleep(0.2)
