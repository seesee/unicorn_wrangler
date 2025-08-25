import uasyncio
import math
import random

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

async def run(graphics, gu, state, interrupt_event):
    # Simple lissajous curve parameters - no complex persistence buffer
    a = 1.0
    b = 1.0
    delta = 0.0
    
    center_x = WIDTH // 2
    center_y = HEIGHT // 2
    amp_x = WIDTH // 2 - 1  # Leave 1 pixel margin
    amp_y = HEIGHT // 2 - 1
    
    t = 0.0
    hue = random.random()  # Start with random hue
    color_speed = 0.003
    
    # Pre-allocate pens to avoid repeated allocation
    black_pen = graphics.create_pen(0, 0, 0)
    
    # Simple trail effect - just store a few previous positions
    trail_length = min(8, WIDTH // 2)  # Adaptive trail length
    trail_positions = []
    
    # Pattern evolution for visual interest
    evolution_timer = 0
    pattern_cycle = 0
    
    while not interrupt_event.is_set():
        # Clear screen
        graphics.set_pen(black_pen)
        graphics.clear()
        
        # Simple pattern evolution every ~10 seconds
        evolution_timer += 1
        if evolution_timer > 600:  # ~10 seconds at 60fps
            evolution_timer = 0
            pattern_cycle = (pattern_cycle + 1) % 3
            
            if pattern_cycle == 0:  # Simple 1:1 ratio
                a, b = 1.0, 1.0
                delta = 0.0
            elif pattern_cycle == 1:  # 2:3 ratio with phase
                a, b = 2.0, 3.0 
                delta = math.pi / 4
            else:  # 3:4 ratio
                a, b = 3.0, 4.0
                delta = 0.0
            
            hue = random.random()  # New color for new pattern
        
        # Calculate current dot position
        x = int(center_x + amp_x * fast_sin(a * t + delta))
        y = int(center_y + amp_y * fast_sin(b * t))
        
        # Ensure position is within bounds
        x = max(0, min(WIDTH - 1, x))
        y = max(0, min(HEIGHT - 1, y))
        
        # Add to trail
        trail_positions.append((x, y))
        if len(trail_positions) > trail_length:
            trail_positions.pop(0)
        
        # Draw trail with fading lines connecting dots for persistence effect
        for i, (tx, ty) in enumerate(trail_positions):
            brightness = (i + 1) / len(trail_positions)  # Fade from dim to bright
            r, g, b = hsv_to_rgb(hue, 1.0, brightness * 0.8)  # Max 80% brightness for trail
            trail_pen = graphics.create_pen(int(r), int(g), int(b))
            graphics.set_pen(trail_pen)
            graphics.pixel(tx, ty)
            
            # Draw faint line to next position for persistence effect
            if i < len(trail_positions) - 1:
                next_x, next_y = trail_positions[i + 1]
                # Use dimmer color for the connecting line
                line_brightness = brightness * 0.4  # Much fainter than the dots
                r_line, g_line, b_line = hsv_to_rgb(hue, 0.8, line_brightness)
                line_pen = graphics.create_pen(int(r_line), int(g_line), int(b_line))
                graphics.set_pen(line_pen)
                graphics.line(tx, ty, next_x, next_y)
        
        # Draw current bright dot
        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
        dot_pen = graphics.create_pen(int(r), int(g), int(b))
        graphics.set_pen(dot_pen)
        graphics.pixel(x, y)
        
        gu.update(graphics)
        
        # Advance time and color
        t += 0.08  # Curve tracing speed
        hue = (hue + color_speed) % 1.0
        
        await uasyncio.sleep(0.016)  # ~60 FPS