import uasyncio
import math

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT, MODEL

# --- Cobra Mk III Data (from Elite) ---

VERTICES = [
    (32, 0, 76), (-32, 0, 76), (0, 26, 24), (-120, -3, -8), (120, -3, -8),
    (-88, 16, -40), (88, 16, -40), (128, -8, -40), (-128, -8, -40), (0, 26, -40),
    (-32, -24, -40), (32, -24, -40), (-36, 8, -40), (-8, 12, -40), (8, 12, -40),
    (36, 8, -40), (36, -12, -40), (8, -16, -40), (-8, -16, -40), (-36, -12, -40),
    (0, 0, 76), (0, 0, 90), (-80, -6, -40), (-80, 6, -40), (-88, 0, -40),
    (80, 6, -40), (88, 0, -40), (80, -6, -40)
]

EDGES = [
    (0, 1, 0, 11), (0, 4, 4, 12), (1, 3, 3, 10), (3, 8, 7, 10), (4, 7, 8, 12),
    (6, 7, 8, 9), (6, 9, 6, 9), (5, 9, 5, 9), (5, 8, 7, 9), (2, 5, 1, 5),
    (2, 6, 2, 6), (3, 5, 3, 7), (4, 6, 4, 8), (1, 2, 0, 1), (0, 2, 0, 2),
    (8, 10, 9, 10), (10, 11, 9, 11), (7, 11, 9, 12), (1, 10, 10, 11),
    (0, 11, 11, 12), (1, 5, 1, 3), (0, 6, 2, 4), (20, 21, 0, 11),
    (12, 13, 9, 9), (18, 19, 9, 9), (14, 15, 9, 9), (16, 17, 9, 9),
    (15, 16, 9, 9), (14, 17, 9, 9), (13, 18, 9, 9), (12, 19, 9, 9),
    (2, 9, 5, 6), (22, 24, 9, 9), (23, 24, 9, 9), (22, 23, 9, 9),
    (25, 26, 9, 9), (26, 27, 9, 9), (25, 27, 9, 9)
]

FACES = [
    (0, 62, 31), (-18, 55, 16), (18, 55, 16), (-16, 52, 14), (16, 52, 14),
    (-14, 47, 0), (14, 47, 0), (-61, 102, 0), (61, 102, 0), (0, 0, -80),
    (-7, -42, 9), (0, -30, 6), (7, -42, 9)
]

def rotate_vertex(v, ax, ay, az):
    x, y, z = v
    # X
    cy, sy = math.cos(ax), math.sin(ax)
    y, z = y * cy - z * sy, y * sy + z * cy
    # Y
    cx, sx = math.cos(ay), math.sin(ay)
    x, z = x * cx + z * sx, -x * sx + z * cx
    # Z
    cz, sz = math.cos(az), math.sin(az)
    x, y = x * cz - y * sz, x * sz + y * cz
    return (x, y, z)

def project_vertex(v, scale, xoff, yoff):
    x, y, z = v
    fov = 220
    viewer_distance = 300
    factor = fov / (z + viewer_distance)
    px = int(x * factor * scale + xoff)
    py = int(-y * factor * scale + yoff)
    return px, py

def face_normal(face):
    nx, ny, nz = face
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length == 0:
        return (0, 0, 1)
    return (nx / length, ny / length, nz / length)

def is_face_visible(normal, view=(0, 0, 1)):
    return (normal[2] > 0)

async def run(graphics, gu, state, interrupt_event):
    w, h = WIDTH, HEIGHT

    # Special-case for Galactic Unicorn: use a square viewport
    if MODEL == "galactic" and w > h * 2:
        # Use a 50x50 square viewport, centered
        viewport_size = min(50, h * 4, w)
        xoff = w // 2
        yoff = h // 2
        base_scale = viewport_size / 220
        # For zoom, keep the ship always inside the square
        zoom_min = base_scale * 0.75
        zoom_max = base_scale * 1.35
    else:
        # Default: use min(w, h) as before
        base_scale = min(w, h) / 220
        xoff = w // 2
        yoff = h // 2
        zoom_min = base_scale * 0.75
        zoom_max = base_scale * 1.35

    zoom_period = 8.0  # seconds for a full in-out-in cycle


    t = 0.0
    color_hue = 0.0

    while not interrupt_event.is_set():
        # --- Rotation ---
        ax = t * 0.7
        ay = t * 0.9
        az = t * 0.5

        # --- Zoom (slow, smooth, never clips) ---
        zoom_phase = (t / zoom_period) * 2 * math.pi
        scale = zoom_min + (zoom_max - zoom_min) * (0.5 + 0.5 * math.sin(zoom_phase))

        # --- Rotate and project vertices ---
        rotated = [rotate_vertex(v, ax, ay, az) for v in VERTICES]
        projected = [project_vertex(v, scale, xoff, yoff) for v in rotated]

        # --- Backface culling ---
        transformed_normals = []
        for i, n in enumerate(FACES):
            nx, ny, nz = rotate_vertex(n, ax, ay, az)
            transformed_normals.append((nx, ny, nz))
        visible_faces = set(i for i, n in enumerate(transformed_normals) if is_face_visible(n))

        # --- Draw ---
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # Very slow color cycling
        color_hue = (color_hue + 0.0007) % 1.0
        r, g, b = hsv_to_rgb(color_hue, 1.0, 1.0)
        pen = graphics.create_pen(r, g, b)
        graphics.set_pen(pen)

        for v1, v2, f1, f2 in EDGES:
            if f1 in visible_faces or f2 in visible_faces:
                x1, y1 = projected[v1]
                x2, y2 = projected[v2]
                # For Galactic, optionally clip to viewport (optional, but not strictly needed)
                if MODEL == "galactic" and w > h * 2:
                    # Only draw if both points are inside the square viewport
                    half = viewport_size // 2
                    if (abs(x1 - xoff) > half or abs(y1 - yoff) > half or
                        abs(x2 - xoff) > half or abs(y2 - yoff) > half):
                        continue
                graphics.line(x1, y1, x2, y2)

        gu.update(graphics)
        t += 0.04
        await uasyncio.sleep(0.001)
