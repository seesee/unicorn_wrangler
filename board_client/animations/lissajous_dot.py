import uasyncio
import math
import random

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

async def run(graphics, gu, state, interrupt_event):
    # CRT/Oscilloscope persistence buffer - each pixel fades independently
    persistence_buffer = [
        [(0, 0, 0) for _ in range(HEIGHT)] for _ in range(WIDTH)
    ]
    
    # Lissajous curve parameters with dynamic behavior
    base_a = 1.0  # Start simple
    base_b = 1.0
    delta = 0.0
    
    center_x = (WIDTH - 1) / 2
    center_y = (HEIGHT - 1) / 2
    amp_x = (WIDTH - 1) / 2 - 1  # Leave 1 pixel margin
    amp_y = (HEIGHT - 1) / 2 - 1
    
    t = 0.0
    curve_time = 0.0  # Separate time for dynamic parameter evolution
    hue = random.random()  # Start with random hue
    
    # CRT persistence settings - optimized for performance
    PERSISTENCE_FADE = 3  # Slightly faster fade for better performance
    fade_counter = 0  # Only fade every few frames for performance
    
    # Pattern evolution parameters
    complexity_cycle = 0.0
    pattern_phase = 0  # 0=simple, 1=building, 2=complex, 3=settling
    phase_timer = 0
    
    while not interrupt_event.is_set():
        # Only fade pixels every 3rd frame for better performance
        fade_counter += 1
        if fade_counter >= 3:
            fade_counter = 0
            for x in range(WIDTH):
                for y in range(HEIGHT):
                    r, g, b = persistence_buffer[x][y]
                    # Phosphor persistence decay
                    r = max(0, r - PERSISTENCE_FADE)
                    g = max(0, g - PERSISTENCE_FADE) 
                    b = max(0, b - PERSISTENCE_FADE)
                    persistence_buffer[x][y] = (r, g, b)
        
        # Draw all persisted pixels
        for x in range(WIDTH):
            for y in range(HEIGHT):
                r, g, b = persistence_buffer[x][y]
                if r > 0 or g > 0 or b > 0:
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(x, y)
        
        # Dynamic parameter evolution - creates the "complex mode" behavior
        curve_time += 0.005
        complexity_cycle += 0.003
        
        # Pattern phases: simple -> building -> complex -> settling -> repeat
        phase_timer += 1
        if phase_timer > 300:  # ~6 seconds per phase
            pattern_phase = (pattern_phase + 1) % 4
            phase_timer = 0
            if pattern_phase == 0:  # Reset to simple
                base_a = 1.0
                base_b = 1.0
                delta = 0.0
                hue = random.random()
        
        # Calculate dynamic parameters based on pattern phase
        if pattern_phase == 0:  # Simple baseline
            a = base_a
            b = base_b
            current_delta = delta
        elif pattern_phase == 1:  # Building complexity
            progress = phase_timer / 300.0
            a = base_a + progress * (2.0 + fast_sin(curve_time * 0.7))
            b = base_b + progress * (1.5 + fast_cos(curve_time * 0.5))
            current_delta = delta + progress * math.pi / 4
        elif pattern_phase == 2:  # Full complexity
            a = base_a + 2.0 + 1.5 * fast_sin(curve_time * 0.7)
            b = base_b + 1.5 + 1.0 * fast_cos(curve_time * 0.5)
            current_delta = delta + math.pi / 4 + 0.5 * fast_sin(curve_time * 0.3)
        else:  # pattern_phase == 3, settling back down
            progress = 1.0 - (phase_timer / 300.0)
            a = base_a + progress * (2.0 + fast_sin(curve_time * 0.7))
            b = base_b + progress * (1.5 + fast_cos(curve_time * 0.5))
            current_delta = delta + progress * math.pi / 4
        
        # Calculate current dot position
        x = int(round(center_x + amp_x * fast_sin(a * t + current_delta)))
        y = int(round(center_y + amp_y * fast_sin(b * t)))
        
        # Ensure position is within bounds
        x = max(0, min(WIDTH - 1, x))
        y = max(0, min(HEIGHT - 1, y))
        
        # Color shifts based on complexity
        if pattern_phase == 2:  # Complex mode gets faster color changes
            hue = (hue + 0.008) % 1.0
        else:
            hue = (hue + 0.003) % 1.0
        
        # Set the current pixel to full brightness in persistence buffer
        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
        persistence_buffer[x][y] = (r, g, b)
        
        # Draw the bright current dot
        graphics.set_pen(graphics.create_pen(r, g, b))
        graphics.pixel(x, y)
        
        gu.update(graphics)
        t += 0.05  # Slightly faster curve tracing
        await uasyncio.sleep(0.015)  # ~67 FPS, faster than before