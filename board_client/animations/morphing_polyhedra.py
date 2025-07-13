import uasyncio
import uarray
import micropython
from animations.utils import hsv_to_rgb, fast_sin, fast_cos, uwPrng
from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

# 3D polyhedra defined as (vertices, faces) with normalized coordinates
# Each face is a tuple of vertex indices.
SHAPES = {
    'tetrahedron': (
        uarray.array('f', [
            0.0, 1.2, 0.0,
            -1.0, -0.6, 0.8,
            1.0, -0.6, 0.8,
            0.0, -0.6, -1.2
        ]),
        (
            (0, 2, 1),
            (0, 3, 2),
            (0, 1, 3),
            (1, 2, 3)
        )
    ),
    'cube': (
        uarray.array('f', [
            -0.8, -0.8, -0.8, -0.8, -0.8, 0.8, -0.8, 0.8, -0.8, -0.8, 0.8, 0.8,
            0.8, -0.8, -0.8, 0.8, -0.8, 0.8, 0.8, 0.8, -0.8, 0.8, 0.8, 0.8
        ]),
        (
            (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3),
            (3, 7, 4, 0), (4, 7, 6, 5), (0, 3, 2, 1)
        )
    ),
    'octahedron': (
        uarray.array('f', [
            0.0, 1.3, 0.0, 0.0, -1.3, 0.0, 1.3, 0.0, 0.0,
            -1.3, 0.0, 0.0, 0.0, 0.0, 1.3, 0.0, 0.0, -1.3
        ]),
        (
            (0, 2, 4), (0, 4, 3), (0, 3, 5), (0, 5, 2),
            (1, 4, 2), (1, 3, 4), (1, 5, 3), (1, 2, 5)
        )
    ),
    'pyramid': (
        uarray.array('f', [
            0.0, 1.4, 0.0, -1.0, -0.7, 1.0, 1.0, -0.7, 1.0,
            1.0, -0.7, -1.0, -1.0, -0.7, -1.0
        ]),
        (
            (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (1, 4, 3, 2)
        )
    )
}

SHAPE_NAMES = list(SHAPES.keys())

# Display-adaptive parameters
@micropython.native 
def get_display_params():
    """Calculate display-specific parameters for optimal scaling"""
    min_dim = min(WIDTH, HEIGHT)
    max_dim = max(WIDTH, HEIGHT)
    
    # Base scale on smaller dimension but allow larger shapes
    base_scale = min_dim * 0.35
    
    # For wide displays like Galactic (53x11), scale up more aggressively  
    aspect_ratio = max_dim / min_dim
    if aspect_ratio > 3.0:  # Very wide display
        base_scale = min_dim * 0.4
    elif aspect_ratio > 2.0:  # Wide display
        base_scale = min_dim * 0.38
        
    camera_distance = 2.8  # Closer camera for larger apparent size
    
    return base_scale, camera_distance

@micropython.native
def project_3d_to_2d(x, y, z, center_x, center_y, scale, camera_distance):
    """Optimized 3D to 2D projection with perspective"""
    z_cam = z + camera_distance
    if z_cam <= 0.1:
        z_cam = 0.1
    
    proj_factor = scale / z_cam
    screen_x = int(center_x + x * proj_factor + 0.5)  # +0.5 for rounding
    screen_y = int(center_y + y * proj_factor + 0.5)
    depth = z_cam
    
    return screen_x, screen_y, depth

@micropython.native
def rotate_point(x, y, z, cos_rx, sin_rx, cos_ry, sin_ry, cos_rz, sin_rz):
    """Optimized rotation with pre-calculated trig values"""
    # Rotate around X axis
    y1 = y * cos_rx - z * sin_rx
    z1 = y * sin_rx + z * cos_rx
    
    # Rotate around Y axis  
    x1 = x * cos_ry + z1 * sin_ry
    z2 = -x * sin_ry + z1 * cos_ry
    
    # Rotate around Z axis
    x2 = x1 * cos_rz - y1 * sin_rz
    y2 = x1 * sin_rz + y1 * cos_rz
    
    return x2, y2, z2

@micropython.native
def interpolate_vertices(verts1, verts2, t, result_array):
    """Optimized interpolation using pre-allocated result array"""
    inv_t = 1.0 - t
    for i in range(len(result_array)):
        if i < len(verts1) and i < len(verts2):
            result_array[i] = verts1[i] * inv_t + verts2[i] * t
        elif i < len(verts1):
            result_array[i] = verts1[i]
        elif i < len(verts2):
            result_array[i] = verts2[i]
        else:
            result_array[i] = 0.0

@micropython.native
def calculate_normal(v1, v2, v3):
    """Calculates the normal vector of a face."""
    ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
    vx, vy, vz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    return nx, ny, nz

@micropython.native
def dot_product(v1, v2):
    """Calculates the dot product of two vectors."""
    return v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]

@micropython.native
def normalize_vector(v):
    """Normalizes a vector."""
    mag = (v[0]**2 + v[1]**2 + v[2]**2)**0.5
    if mag == 0:
        return 0.0, 0.0, 0.0
    return v[0] / mag, v[1] / mag, v[2] / mag

@micropython.native
def fill_polygon(graphics, polygon, r, g, b):
    """Fills a polygon using a scanline algorithm."""
    min_y = max(0, min(v[1] for v in polygon))
    max_y = min(HEIGHT - 1, max(v[1] for v in polygon))

    for y in range(min_y, max_y + 1):
        intersections = []
        for i in range(len(polygon)):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % len(polygon)]
            if p1[1] != p2[1]:
                if min(p1[1], p2[1]) <= y < max(p1[1], p2[1]):
                    x = (y - p1[1]) * (p2[0] - p1[0]) / (p2[1] - p1[1]) + p1[0]
                    intersections.append(x)
        
        intersections.sort()
        
        for i in range(0, len(intersections), 2):
            if i + 1 < len(intersections):
                x1 = int(max(0, intersections[i]))
                x2 = int(min(WIDTH - 1, intersections[i+1]))
                if x1 <= x2:
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.line(x1, y, x2, y)

@micropython.native
def get_auto_scaling_factor(vertices, center_x, center_y, camera_distance):
    """Calculates a scaling factor to fit the object to the screen width."""
    if not vertices:
        return 1.0

    min_x, max_x = float('inf'), float('-inf')

    for i in range(0, len(vertices), 3):
        x, y, z = vertices[i], vertices[i+1], vertices[i+2]
        z_cam = z + camera_distance
        if z_cam <= 0.1:
            z_cam = 0.1
        
        proj_factor = 1.0 / z_cam
        screen_x = center_x + x * proj_factor
        
        min_x = min(min_x, screen_x)
        max_x = max(max_x, screen_x)

    current_width = max_x - min_x
    if current_width == 0:
        return 1.0

    return WIDTH / current_width * 0.8  # 80% of width for some padding

async def run(graphics, gu, state, interrupt_event):
    # Configurable timings
    rotation_duration = 10.0  # seconds
    fade_duration = 1.0  # seconds

    # Get display-adaptive parameters
    _, camera_distance = get_display_params()
    
    # Animation parameters
    t = 0.0
    rotation_speed = 0.5
    
    center_x = WIDTH // 2
    center_y = HEIGHT // 2
    
    prng = uwPrng()
    current_shape_idx = prng.randint(0, len(SHAPE_NAMES) - 1)
    
    light_source = (0.5, 0.5, -1.0) # From front-right
    light_source = normalize_vector(light_source)

    # Animation phases
    FADING_IN, ROTATING, FADING_OUT = 0, 1, 2
    animation_phase = FADING_IN
    phase_timer = 0.0

    while not interrupt_event.is_set():
        dt = 0.035
        phase_timer += dt

        # Phase transitions
        if animation_phase == FADING_IN and phase_timer >= fade_duration:
            animation_phase = ROTATING
            phase_timer = 0.0
        elif animation_phase == ROTATING and phase_timer >= rotation_duration:
            animation_phase = FADING_OUT
            phase_timer = 0.0
        elif animation_phase == FADING_OUT and phase_timer >= fade_duration:
            animation_phase = FADING_IN
            phase_timer = 0.0
            
            previous_shape_idx = current_shape_idx
            while current_shape_idx == previous_shape_idx:
                current_shape_idx = prng.randint(0, len(SHAPE_NAMES) - 1)

            t = 0 # Reset rotation timer for new shape

        current_shape = SHAPES[SHAPE_NAMES[current_shape_idx]]
        
        scale = get_auto_scaling_factor(current_shape[0], center_x, center_y, camera_distance)

        rot_x = t * rotation_speed * 0.7
        rot_y = t * rotation_speed * 1.0
        rot_z = t * rotation_speed * 0.4
        
        cos_rx, sin_rx = fast_cos(rot_x), fast_sin(rot_x)
        cos_ry, sin_ry = fast_cos(rot_y), fast_sin(rot_y)
        cos_rz, sin_rz = fast_cos(rot_z), fast_sin(rot_z)
        
        hue_base = (t * 0.03) % 1.0
        
        # Fade factor
        fade_factor = 1.0
        if animation_phase == FADING_IN:
            fade_factor = phase_timer / fade_duration
        elif animation_phase == FADING_OUT:
            fade_factor = 1.0 - (phase_timer / fade_duration)

        # Background color
        bg_hue = (hue_base + 0.5) % 1.0
        bg_r, bg_g, bg_b = hsv_to_rgb(bg_hue, 0.7, 0.1 * fade_factor)
        graphics.set_pen(graphics.create_pen(bg_r, bg_g, bg_b))
        graphics.clear()
        
        rotated_vertices = []
        num_verts = len(current_shape[0]) // 3
        
        for i in range(num_verts):
            idx = i * 3
            x, y, z = current_shape[0][idx], current_shape[0][idx+1], current_shape[0][idx+2]
            rx, ry, rz = rotate_point(x, y, z, cos_rx, sin_rx, cos_ry, sin_ry, cos_rz, sin_rz)
            rotated_vertices.append((rx, ry, rz))

        faces_to_draw = []
        for face in current_shape[1]:
            v1 = rotated_vertices[face[0]]
            v2 = rotated_vertices[face[1]]
            v3 = rotated_vertices[face[2]]
            
            normal = calculate_normal(v1, v2, v3)
            
            if dot_product(normal, (0, 0, -1)) < 0:
                continue

            avg_depth = sum(rotated_vertices[i][2] for i in face) / len(face)
            
            projected_face = []
            for vertex_index in face:
                v = rotated_vertices[vertex_index]
                sx, sy, _ = project_3d_to_2d(v[0], v[1], v[2], center_x, center_y, scale, camera_distance)
                projected_face.append((sx, sy))

            faces_to_draw.append((avg_depth, projected_face, normal))

        faces_to_draw.sort(key=lambda x: x[0], reverse=True)

        for avg_depth, projected_face, normal in faces_to_draw:
            brightness = max(0.1, dot_product(normalize_vector(normal), light_source))
            
            hue = hue_base % 1.0
            saturation = 0.9
            
            r, g, b = hsv_to_rgb(hue, saturation, brightness * fade_factor)
            
            fill_polygon(graphics, projected_face, r, g, b)
            
        gu.update(graphics)
        t += dt
        await uasyncio.sleep(0.015)
