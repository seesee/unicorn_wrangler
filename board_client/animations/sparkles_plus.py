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
    # Sparkles appear individually and fade on same schedule, with collision detection
    
    # Use uwPrng for better entropy on embedded systems
    prng = uwPrng()
    
    # Scale sparkle count based on display size
    WIDTH, HEIGHT = graphics.get_bounds()
    total_pixels = WIDTH * HEIGHT
    cosmic_pixels = 32 * 32  # 1024
    cosmic_sparkles = 120
    
    # Calculate target sparkles based on pixel density
    TARGET_SPARKLES = max(20, int((total_pixels / cosmic_pixels) * cosmic_sparkles))
    
    # Allow sparkle count to vary within +/- 5 range
    MIN_SPARKLES = max(10, TARGET_SPARKLES - 5)
    MAX_SPARKLES = TARGET_SPARKLES + 5
    
    # Much slower sparkle appearance rate to spread them out over time
    NEW_SPARKLES_MIN = 0  # Sometimes no new sparkles
    NEW_SPARKLES_MAX = 1  # Maximum 1 per frame
    
    # Random fade durations between 1-2 seconds
    MIN_FADE_DURATION = 1.0  # 1 second minimum fade
    MAX_FADE_DURATION = 2.0  # 2 second maximum fade
    
    FRAME_DELAY = 0.04
    
    sparkles = []
    
    # Pre-allocate black pen for clearing
    black_pen = graphics.create_pen(0, 0, 0)
    
    while not interrupt_event.is_set():
        # Clear screen
        graphics.set_pen(black_pen)
        graphics.clear()
        
        # Create occupancy grid to prevent sparkle overlap
        occupied = [[False for _ in range(HEIGHT)] for _ in range(WIDTH)]
        
        # Update all sparkles - individual fade schedules
        next_sparkles = []
        for s in sparkles:
            s['age'] += FRAME_DELAY
            
            # Calculate fade progress based on individual fade duration
            fade_progress = s['age'] / s['fade_duration']
            
            # Linear fade from 1.0 to 0.0 over fade duration
            s['v'] = max(0.0, 1.0 - fade_progress)
            
            # Keep sparkle if still visible
            if s['v'] > 0:
                next_sparkles.append(s)
        sparkles = next_sparkles
        
        # Mark existing sparkles as occupied
        for s in sparkles:
            mark_area_occupied(occupied, s['x'], s['y'], s['size'], WIDTH, HEIGHT)
        
        # Add new sparkles individually (with collision detection)
        # Only add sparkles if we're within the target range
        if len(sparkles) < MAX_SPARKLES:
            num_new = prng.randint(NEW_SPARKLES_MIN, NEW_SPARKLES_MAX)
            for _ in range(num_new):
                if len(sparkles) >= MAX_SPARKLES:
                    break
                # Choose size with weighted probability
                rand_val = prng.randint(1, 100)
                if rand_val <= 60:      # 60% chance
                    size = 2
                elif rand_val <= 90:    # 30% chance
                    size = 3
                else:                   # 10% chance
                    size = 4
                
                # Leave room based on size
                max_x = WIDTH - size
                max_y = HEIGHT - size
                
                # Skip if display too small for this size
                if max_x <= 0 or max_y <= 0:
                    continue
                
                # Try to find a free position
                attempts = 0
                max_attempts = 20
                placed = False
                
                while attempts < max_attempts and not placed:
                    x = prng.randint(0, max_x)
                    y = prng.randint(0, max_y)
                    
                    if is_area_free(occupied, x, y, size, WIDTH, HEIGHT):
                        new_sparkle = {
                            'x': x,
                            'y': y,
                            'h': prng.randfloat(),
                            's': prng.randfloat(0.9, 1.0),
                            'v': 1.0,  # Appear immediately at full brightness
                            'size': size,
                            'age': 0.0,
                            'fade_duration': prng.randfloat(MIN_FADE_DURATION, MAX_FADE_DURATION)
                        }
                        sparkles.append(new_sparkle)
                        
                        # Mark the area as occupied
                        mark_area_occupied(occupied, x, y, size, WIDTH, HEIGHT)
                        placed = True
                    
                    attempts += 1
        
        # Render sparkles
        for s in sparkles:
            # Get sparkle color with current brightness
            r, g, b = hsv_to_rgb(s['h'], s['s'], s['v'])
            
            # Render NxN sparkle
            size = s['size']
            for dx in range(size):
                for dy in range(size):
                    pixel_x = s['x'] + dx
                    pixel_y = s['y'] + dy
                    
                    # Ensure within bounds
                    if 0 <= pixel_x < WIDTH and 0 <= pixel_y < HEIGHT:
                        # Apply slight center-to-edge variation for larger sparkles
                        if size > 2:
                            center_x = (size - 1) / 2
                            center_y = (size - 1) / 2
                            dist_from_center = math.sqrt((dx - center_x)**2 + (dy - center_y)**2)
                            max_dist = math.sqrt(center_x**2 + center_y**2)
                            
                            # Center is full intensity, edges are 85% intensity
                            if max_dist > 0:
                                variation = 1.0 - 0.15 * (dist_from_center / max_dist)
                            else:
                                variation = 1.0
                        else:
                            variation = 1.0
                        
                        final_r = int(r * variation)
                        final_g = int(g * variation)
                        final_b = int(b * variation)
                        
                        # Draw pixel
                        pixel_pen = graphics.create_pen(final_r, final_g, final_b)
                        graphics.set_pen(pixel_pen)
                        graphics.pixel(pixel_x, pixel_y)
        
        gu.update(graphics)
        await uasyncio.sleep(FRAME_DELAY)