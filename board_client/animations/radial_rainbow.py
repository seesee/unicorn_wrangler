import uasyncio
import math

from animations.utils import hsv_to_rgb, fast_sin, fast_cos

async def run(graphics, gu, state, interrupt_event):
    # Optimized dual orbiting radial rainbows - only render every other circle
    WIDTH, HEIGHT = graphics.get_bounds()
    time = 0

    # Animation parameters for three orbiting centers
    # Each center gets its own base hue 120° apart (1/3 of hue wheel)
    base_hue1 = 0.0    # Red/Orange progression
    base_hue2 = 0.333  # Green progression  
    base_hue3 = 0.667  # Blue/Purple progression
    
    orbit_rad = min(WIDTH, HEIGHT) / 4
    orbit_speed1 = 0.02
    orbit_speed2 = 0.015
    orbit_speed3 = 0.018  # Third speed between the other two
    
    # Pre-allocate white pen for background
    white_pen = graphics.create_pen(255, 255, 255)
    
    # Pre-calculate distance lookup tables for all pixels relative to display center
    # We'll adjust these for orbiting centers each frame
    center_x = WIDTH // 2
    center_y = HEIGHT // 2
    
    while not interrupt_event.is_set():
        # Fill background with white
        graphics.set_pen(white_pen)
        graphics.rectangle(0, 0, WIDTH, HEIGHT)
        
        # Calculate three orbiting center positions - no minimum distance constraints
        center1_x = center_x + orbit_rad * fast_cos(time * orbit_speed1)
        center1_y = center_y + orbit_rad * fast_sin(time * orbit_speed1)
        
        center2_x = center_x + orbit_rad * fast_cos(time * orbit_speed2 + math.pi)
        center2_y = center_y + orbit_rad * fast_sin(time * orbit_speed2 + math.pi)
        
        center3_x = center_x + orbit_rad * fast_cos(time * orbit_speed3 + math.pi / 2)
        center3_y = center_y + orbit_rad * fast_sin(time * orbit_speed3 + math.pi / 2)
        
        # Apply bounds checking to prevent centers from going too far off-screen
        margin = max(WIDTH, HEIGHT) // 2
        center1_x = max(-margin, min(WIDTH + margin, center1_x))
        center1_y = max(-margin, min(HEIGHT + margin, center1_y))
        center2_x = max(-margin, min(WIDTH + margin, center2_x))
        center2_y = max(-margin, min(HEIGHT + margin, center2_y))
        center3_x = max(-margin, min(WIDTH + margin, center3_x))
        center3_y = max(-margin, min(HEIGHT + margin, center3_y))
        
        # Calculate maximum radius to ensure we fill the entire screen
        # Use the distance from center to the farthest corner
        max_radius = int(math.sqrt((WIDTH//2)**2 + (HEIGHT//2)**2)) + max(WIDTH//2, HEIGHT//2)
        
        # Helper function to draw circle outline using line segments
        def draw_circle_outline(cx, cy, radius, pen):
            graphics.set_pen(pen)
            if radius == 0:
                graphics.pixel(int(cx), int(cy))
                return
            
            # Draw circle using more line segments for smoother circles
            points = []
            num_segments = max(8, min(16, radius // 2))  # More segments for larger circles
            for i in range(num_segments):
                angle_rad = (i * 2 * math.pi) / num_segments
                # Use floating point centers for smooth motion, round only at the end
                x = int(cx + radius * fast_cos(angle_rad))
                y = int(cy + radius * fast_sin(angle_rad))
                points.append((x, y))
            
            # Connect the points with lines to form circle outline
            for i in range(len(points)):
                x1, y1 = points[i]
                x2, y2 = points[(i + 1) % len(points)]
                graphics.line(x1, y1, x2, y2)
        
        # Draw circles from three centers, cycling which center gets each radius
        for radius in range(0, max_radius, 2):  # Every 2nd radius (1 in 2 rendering)
            # Cycle between the three centers based on radius
            center_index = (radius // 2) % 3
            
            if center_index == 0:
                center_x_draw = center1_x
                center_y_draw = center1_y
                base_hue = base_hue1
            elif center_index == 1:
                center_x_draw = center2_x
                center_y_draw = center2_y
                base_hue = base_hue2
            else:  # center_index == 2
                center_x_draw = center3_x
                center_y_draw = center3_y
                base_hue = base_hue3
            
            # Calculate hue for this radius - each center has its own color progression
            # Use actual radius value to create distinct rings from each center
            scale = 4.0  # Scale for color progression - larger = slower color change
            hue = (base_hue + (radius * 0.5) / scale + time * 0.001) % 1.0
            
            # Get color and create pen
            r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
            pen = graphics.create_pen(int(r), int(g), int(b))
            
            # Draw the circle outline
            draw_circle_outline(center_x_draw, center_y_draw, radius, pen)
        
        # Update animation - time drives color shifting
        time += 1
        
        gu.update(graphics)
        await uasyncio.sleep(0.025)  # Balanced refresh rate
