import uasyncio
import math
import utime
import micropython

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT

# --- CONFIGURABLES ---
_HELIX_RADIUS = micropython.const(12)  # Radius of the helix strands
_HELIX_LENGTH = micropython.const(80)  # How long the DNA strand is
_NUM_POINTS = micropython.const(60)   # Number of points per strand
_NUM_PAIRS = micropython.const(15)    # Number of base pairs to draw

# --- ANIMATION SPEEDS ---
_HELIX_ROTATION_SPEED = 0.2
_CAMERA_ORBIT_SPEED = 0.1
_CAMERA_TILT_SPEED = 0.15
_CAMERA_ZOOM_SPEED = 0.25

# --- COLOR PALETTE (HSV: Hue, Saturation, Value) ---
_COLOR_BACKBONE_1 = (0.6, 1.0, 1.0)  # Blue
_COLOR_BACKBONE_2 = (0.5, 1.0, 1.0)  # Cyan
_COLOR_PAIR_A = (0.15, 1.0, 1.0) # Yellow
_COLOR_PAIR_B = (0.85, 1.0, 1.0) # Magenta

# --- 3D MATH HELPERS (optimized with @micropython.native) ---
@micropython.native
def rotate_x(p, angle: float):
    x, y, z = p
    c, s = math.cos(angle), math.sin(angle)
    return (x, y * c - z * s, y * s + z * c)

@micropython.native
def rotate_y(p, angle: float):
    x, y, z = p
    c, s = math.cos(angle), math.sin(angle)
    return (x * c + z * s, y, -x * s + z * c)

@micropython.native
def rotate_z(p, angle: float):
    x, y, z = p
    c, s = math.cos(angle), math.sin(angle)
    return (x * c - y * s, x * s + y * c, z)

@micropython.native
def project(p, zoom: float):
    """Project 3D point to 2D screen coordinates with depth cueing."""
    x, y, z = p
    # The '100' pushes the object further from the camera
    pos_z = z + 100.0
    if pos_z == 0: pos_z = 0.01
    
    # Perspective projection
    scale = zoom / pos_z
    sx = int(x * scale + WIDTH / 2)
    sy = int(y * scale + HEIGHT / 2)
    
    # Depth cueing: further points are dimmer
    brightness = max(0.1, min(1.0, 70.0 / pos_z))
    
    return (sx, sy, brightness)

async def run(graphics, gu, state, interrupt_event):
    helix_angle = 0.0
    
    # Scale the object to fit the display
    base_zoom = min(WIDTH, HEIGHT) * 3.5

    while not interrupt_event.is_set():
        # --- Update animation state ---
        current_time = utime.time()
        helix_angle += _HELIX_ROTATION_SPEED
        
        # --- Dynamic Camera Movement ---
        # Camera orbits around the Y axis
        cam_angle_y = math.sin(current_time * _CAMERA_ORBIT_SPEED) * 2.0
        # Camera tilts up and down on the X axis
        cam_angle_x = math.sin(current_time * _CAMERA_TILT_SPEED) * 0.8
        # Camera zooms in and out
        zoom_factor = base_zoom * (1.0 + 0.3 * math.sin(current_time * _CAMERA_ZOOM_SPEED))

        # --- Generate, Transform, and Project all points ---
        points_to_draw = []
        
        # Generate backbone points
        for i in range(_NUM_POINTS):
            progress = i / (_NUM_POINTS - 1)
            angle = progress * 10.0  # More twists
            z = -_HELIX_LENGTH / 2 + progress * _HELIX_LENGTH

            # Strand 1
            p1 = (_HELIX_RADIUS * math.cos(angle), _HELIX_RADIUS * math.sin(angle), z)
            # Strand 2 (180 degrees out of phase)
            p2 = (-p1[0], -p1[1], z)
            
            points_to_draw.append({'p': p1, 'type': 'b1'})
            points_to_draw.append({'p': p2, 'type': 'b2'})

        # Generate base pair points
        for i in range(_NUM_PAIRS):
            progress = i / (_NUM_PAIRS - 1)
            angle = progress * 10.0
            z = -_HELIX_LENGTH / 2 + progress * _HELIX_LENGTH
            
            p1 = (_HELIX_RADIUS * math.cos(angle), _HELIX_RADIUS * math.sin(angle), z)
            p2 = (-p1[0], -p1[1], z)
            
            # Alternate pair colors
            pair_type = 'pa' if i % 2 == 0 else 'pb'
            points_to_draw.append({'p_start': p1, 'p_end': p2, 'type': pair_type})

        # --- Transform and Project ---
        transformed_points = []
        for item in points_to_draw:
            if 'p' in item: # It's a backbone point
                p = item['p']
                p_rot_z = rotate_z(p, helix_angle)
                p_rot_y = rotate_y(p_rot_z, cam_angle_y)
                p_rot_x = rotate_x(p_rot_y, cam_angle_x)
                proj_p = project(p_rot_x, zoom_factor)
                transformed_points.append({'p': proj_p, 'type': item['type']})
            else: # It's a base pair line
                p_start, p_end = item['p_start'], item['p_end']
                ps_rot_z = rotate_z(p_start, helix_angle)
                pe_rot_z = rotate_z(p_end, helix_angle)
                ps_rot_y = rotate_y(ps_rot_z, cam_angle_y)
                pe_rot_y = rotate_y(pe_rot_z, cam_angle_y)
                ps_rot_x = rotate_x(ps_rot_y, cam_angle_x)
                pe_rot_x = rotate_x(pe_rot_y, cam_angle_x)
                proj_ps = project(ps_rot_x, zoom_factor)
                proj_pe = project(pe_rot_x, zoom_factor)
                transformed_points.append({'p_start': proj_ps, 'p_end': proj_pe, 'type': item['type']})

        # Sort points by depth (Z-coordinate of projection) for correct layering
        # Simple sort key: use the brightness which is derived from Z
        transformed_points.sort(key=lambda d: d.get('p', d.get('p_start'))[2])

        # --- Drawing ---
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # Draw sorted points and lines
        for i, item in enumerate(transformed_points):
            if 'p' in item: # Backbone point
                if i > 0 and 'p' in transformed_points[i-1] and item['type'] == transformed_points[i-1]['type']:
                    # Connect to previous point of the same strand
                    p1, b1 = item['p'], item['p'][2]
                    p0, b0 = transformed_points[i-1]['p'], transformed_points[i-1]['p'][2]
                    
                    h, s, v = _COLOR_BACKBONE_1 if item['type'] == 'b1' else _COLOR_BACKBONE_2
                    r, g, b = hsv_to_rgb(h, s, v * ((b0 + b1) / 2.0))
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.line(p0[0], p0[1], p1[0], p1[1])
            else: # Base pair line
                p_start, b_start = item['p_start'], item['p_start'][2]
                p_end, b_end = item['p_end'], item['p_end'][2]
                
                h, s, v = _COLOR_PAIR_A if item['type'] == 'pa' else _COLOR_PAIR_B
                r, g, b = hsv_to_rgb(h, s, v * ((b_start + b_end) / 2.0))
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.line(p_start[0], p_start[1], p_end[0], p_end[1])

        gu.update(graphics)
        await uasyncio.sleep(0.016)
