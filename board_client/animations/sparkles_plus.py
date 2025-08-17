import uasyncio
import math

from animations.utils import hsv_to_rgb, uwPrng

def is_area_free(occupied, x, y, size, width, height):
    """Check if a sparkle area is free from overlap"""
    for dx in range(size):
        for dy in range(size):
            check_x = x + dx
            check_y = y + dy
            if 0 <= check_x < width and 0 <= check_y < height:
                if occupied[check_x][check_y]:
                    return False
    return True

def mark_area_occupied(occupied, x, y, size, width, height):
    """Mark a sparkle area as occupied"""
    for dx in range(size):
        for dy in range(size):
            mark_x = x + dx
            mark_y = y + dy
            if 0 <= mark_x < width and 0 <= mark_y < height:
                occupied[mark_x][mark_y] = True

async def run(graphics, gu, state, interrupt_event):
    # Enhanced sparkles with multi-pixel sizes but simplified rendering
    
    # Use uwPrng for better entropy on embedded systems
    prng = uwPrng()
    
    # Scale sparkle count based on display size
    # Cosmic (32x32=1024 pixels) gets 120 sparkles as baseline
    # Other displays scale proportionally by pixel count
    WIDTH, HEIGHT = graphics.get_bounds()
    total_pixels = WIDTH * HEIGHT
    cosmic_pixels = 32 * 32  # 1024
    cosmic_sparkles = 120
    
    # Calculate max sparkles based on pixel density
    MAX_SPARKLES_ON_SCREEN = max(20, int((total_pixels / cosmic_pixels) * cosmic_sparkles))
    
    # Scale new sparkles per frame proportionally too
    sparkle_density = MAX_SPARKLES_ON_SCREEN / 60  # Original was 60
    NEW_SPARKLES_MIN = max(1, int(2 * sparkle_density))
    NEW_SPARKLES_MAX = max(2, int(5 * sparkle_density))
    SPARKLE_SATURATION_MIN = 0.9
    SPARKLE_SATURATION_MAX = 1.0
    
    # Note: Creating pens dynamically as set_rgb method doesn't exist
    
    # Decay rates based on size (larger sparkles fade slower)
    DECAY_RATES = {
        2: (0.015, 0.06), # 2x2: baseline fade rate
        3: (0.01, 0.04),  # 3x3: slower fade
        4: (0.008, 0.03)  # 4x4: very slow fade
    }
    
    # Intensity scaling (2x2 now gets full brightness)
    INTENSITY_SCALE = {
        2: 1.0,   # 2x2: full brightness (new baseline)
        3: 0.8,   # 3x3: 80% brightness per pixel
        4: 0.65   # 4x4: 65% brightness per pixel
    }
    
    # Fade-in duration based on size (larger sparkles fade in slower)
    FADE_IN_DURATION = {
        2: 0.15,  # 2x2: quick fade-in
        3: 0.25,  # 3x3: medium fade-in
        4: 0.35   # 4x4: slow fade-in
    }
    
    FRAME_DELAY = 0.04
    
    sparkles = []
    
    # Pre-allocate black pen for clearing
    black_pen = graphics.create_pen(0, 0, 0)
    
    while not interrupt_event.is_set():
        # Clear screen
        graphics.set_pen(black_pen)
        graphics.clear()
        
        # Create occupancy grid to prevent sparkle overlap (rebuilt each frame)
        occupied = [[False for _ in range(HEIGHT)] for _ in range(WIDTH)]
        
        # Update sparkle states (fade in/out and remove)
        next_sparkles = []
        for s in sparkles:
            s['age'] += FRAME_DELAY
            
            if s['fading_in']:
                # Fade in: increase brightness from 0 to 1
                fade_progress = min(1.0, s['age'] / s['fade_in_duration'])
                s['v'] = fade_progress
                
                if fade_progress >= 1.0:
                    s['fading_in'] = False  # Switch to fade-out phase
            else:
                # Fade out: decrease brightness
                s['v'] -= s['decay']
            
            # Keep sparkle if still visible
            if s['v'] > 0:
                next_sparkles.append(s)
        sparkles = next_sparkles
        
        # Mark existing sparkles as occupied
        for s in sparkles:
            mark_area_occupied(occupied, s['x'], s['y'], s['size'], WIDTH, HEIGHT)
        
        # Add new sparkles (with collision detection)
        num_new = prng.randint(NEW_SPARKLES_MIN, NEW_SPARKLES_MAX)
        for _ in range(num_new):
            if len(sparkles) < MAX_SPARKLES_ON_SCREEN:
                # Choose size with weighted probability (smaller sparkles more common)
                # Updated weights: 2x2=60%, 3x3=30%, 4x4=10%
                rand_val = prng.randint(1, 100)  # 1-100 for percentage-based weights
                if rand_val <= 60:      # 60% chance
                    size = 2
                elif rand_val <= 90:    # 30% chance (60 + 30 = 90)
                    size = 3
                else:                   # 10% chance (remaining)
                    size = 4
                
                # Leave room based on size
                max_x = WIDTH - size
                max_y = HEIGHT - size
                
                # Skip if display too small for this size
                if max_x <= 0 or max_y <= 0:
                    continue
                
                # Try to find a free position (limited attempts to avoid infinite loops)
                attempts = 0
                max_attempts = 20  # Reasonable limit for embedded systems
                placed = False
                
                while attempts < max_attempts and not placed:
                    x = prng.randint(0, max_x)
                    y = prng.randint(0, max_y)
                    
                    if is_area_free(occupied, x, y, size, WIDTH, HEIGHT):
                        # Get decay rate for this size
                        decay_min, decay_max = DECAY_RATES[size]
                        
                        new_sparkle = {
                            'x': x,
                            'y': y,
                            'h': prng.randfloat(),
                            's': prng.randfloat(SPARKLE_SATURATION_MIN, SPARKLE_SATURATION_MAX),
                            'v': 0.0,  # Start at 0 brightness for fade-in
                            'decay': prng.randfloat(decay_min, decay_max),
                            'size': size,
                            'age': 0.0,  # Track sparkle age for fade-in
                            'fade_in_duration': FADE_IN_DURATION[size],
                            'fading_in': True
                        }
                        sparkles.append(new_sparkle)
                        
                        # Mark the area as occupied
                        mark_area_occupied(occupied, x, y, size, WIDTH, HEIGHT)
                        placed = True
                    
                    attempts += 1
        
        # Render sparkles directly to graphics (no blending)
        for s in sparkles:
            # Get sparkle color with current brightness
            r, g, b = hsv_to_rgb(s['h'], s['s'], s['v'])
            
            # Apply intensity scaling based on size
            size = s['size']
            intensity = INTENSITY_SCALE[size]
            
            # Render NxN sparkle
            for dx in range(size):
                for dy in range(size):
                    pixel_x = s['x'] + dx
                    pixel_y = s['y'] + dy
                    
                    # Ensure within bounds
                    if 0 <= pixel_x < WIDTH and 0 <= pixel_y < HEIGHT:
                        # Apply intensity scaling with slight center-to-edge variation
                        if size > 1:
                            center_x = (size - 1) / 2
                            center_y = (size - 1) / 2
                            dist_from_center = math.sqrt((dx - center_x)**2 + (dy - center_y)**2)
                            max_dist = math.sqrt(center_x**2 + center_y**2) if size > 1 else 1
                            
                            # Variation: center is full intensity, edges are 85% intensity
                            if max_dist > 0:
                                variation = 1.0 - 0.15 * (dist_from_center / max_dist)
                            else:
                                variation = 1.0
                        else:
                            variation = 1.0
                        
                        final_intensity = intensity * variation
                        final_r = int(r * final_intensity)
                        final_g = int(g * final_intensity)
                        final_b = int(b * final_intensity)
                        
                        # Draw pixel with dynamically created pen
                        pixel_pen = graphics.create_pen(final_r, final_g, final_b)
                        graphics.set_pen(pixel_pen)
                        graphics.pixel(pixel_x, pixel_y)
        
        gu.update(graphics)
        await uasyncio.sleep(FRAME_DELAY)