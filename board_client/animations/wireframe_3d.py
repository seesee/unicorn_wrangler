import uasyncio
import math
import random
import gc
import sys
import os

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT, MODEL
from uw.logger import log

def get_wireframe_list():
    """Get list of available wireframe data files"""
    try:
        files = os.listdir("wireframes")
        wireframes = []
        for f in files:
            if f.endswith(".py") and not f.startswith("_"):
                wireframes.append(f[:-3]) # remove .py
        return sorted(wireframes)
    except OSError:
        return []

def rotate_vertex(v, ax, ay, az):
    x, y, z = v
    cy, sy = math.cos(ax), math.sin(ax)
    y, z = y * cy - z * sy, y * sy + z * cy
    cx, sx = math.cos(ay), math.sin(ay)
    x, z = x * cx + z * sx, -x * sx + z * cx
    cz, sz = math.cos(az), math.sin(az)
    x, y = x * cz - y * sz, x * sz + y * cz
    return (x, y, z)

def project_vertex(v, scale, xoff, yoff):
    x, y, z = v
    fov = 220
    viewer_distance = 300
    factor = fov / (z + viewer_distance)
    px = round(x * factor * scale + xoff)
    py = round(-y * factor * scale + yoff)
    return px, py

def get_model_width_projected(vertices, scale):
    xoff, yoff = 0, 0
    rotated = [rotate_vertex(v, 0, 0, 0) for v in vertices]
    projected = [project_vertex(v, scale, xoff, yoff) for v in rotated]
    xs = [x for x, y in projected]
    return max(xs) - min(xs)

def find_scale_for_width(vertices, target_width):
    lo, hi = 0.01, 10.0
    for _ in range(20):
        mid = (lo + hi) / 2
        width = get_model_width_projected(vertices, mid)
        if width < target_width:
            lo = mid
        else:
            hi = mid
    return lo

def shuffle(lst):
    n = len(lst)
    for i in range(n - 1, 0, -1):
        j = random.randrange(i + 1)
        lst[i], lst[j] = lst[j], lst[i]
    return lst

async def render_wireframe(graphics, gu, wireframe_data, interrupt_event, duration=30.0):
    vertices = wireframe_data['vertices']
    edges = wireframe_data['edges']
    faces = wireframe_data.get('faces', [])
    
    use_backface_culling = wireframe_data.get('backface_culling', False)
    initial_scale_factor = wireframe_data.get('scale_factor', 1.0)
    
    w, h = WIDTH, HEIGHT
    
    # Apply initial scale factor to vertices
    if initial_scale_factor != 1.0:
        scaled_vertices = [(x * initial_scale_factor, y * initial_scale_factor, z * initial_scale_factor) 
                          for x, y, z in vertices]
    else:
        scaled_vertices = vertices
    
    # Recalculate scaling based on scaled_vertices
    min_scale = find_scale_for_width(scaled_vertices, w * 1.25)
    if MODEL == "galactic":
        max_scale = find_scale_for_width(scaled_vertices, w * 2.0)
    else:
        max_scale = find_scale_for_width(scaled_vertices, w * 2.5)
    
    xoff = w // 2
    yoff = h // 2
    
    zoom_period = 12.0  # seconds for a full zoom in-out-in cycle
    
    t = 0.0
    color_hue = random.random()  # Random starting hue for each model
    start_time = t
    
    # Calc Z bounds for depth shading
    z_coords = [v[2] for v in scaled_vertices]
    model_z_near = max(z_coords)
    model_z_far = min(z_coords)
    
    while not interrupt_event.is_set() and (t - start_time) < duration:
        # Rotation
        ax = t * 0.7
        ay = t * 0.9
        az = t * 0.5
        
        # Zoom
        zoom_phase = (t / zoom_period) * 2 * math.pi
        scale = min_scale + (max_scale - min_scale) * (0.5 + 0.5 * math.sin(zoom_phase))
        
        # Rotate and project vertices
        rotated = [rotate_vertex(v, ax, ay, az) for v in scaled_vertices]
        projected = [project_vertex(v, scale, xoff, yoff) for v in rotated]
        rotated_z = [v[2] for v in rotated]
        
        # Backface culling if enabled
        visible_faces = set()
        if use_backface_culling and faces:
            transformed_normals = []
            for i, n in enumerate(faces):
                nx, ny, nz = rotate_vertex(n, ax, ay, az)
                transformed_normals.append((nx, ny, nz))
            
            # Reduce edge flickering
            visibility_threshold = -0.15
            visible_faces = set(i for i, n in enumerate(transformed_normals) if n[2] > visibility_threshold)
        
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        
        color_hue = (color_hue + 0.0007) % 1.0
        
        # Draw edges
        for v1, v2, f1, f2 in edges:
            # Apply backface culling if enabled
            if use_backface_culling and visible_faces:
                if f1 not in visible_faces and f2 not in visible_faces:
                    continue
            
            x1, y1 = projected[v1]
            x2, y2 = projected[v2]
            
            # Skip lines that are off-screen
            if (x1 < -10 and x2 < -10) or (x1 > w + 10 and x2 > w + 10) or \
               (y1 < -10 and y2 < -10) or (y1 > h + 10 and y2 > h + 10):
                continue
            
            # Depth shading
            z1 = rotated_z[v1]
            z2 = rotated_z[v2]
            z_avg = (z1 + z2) / 2
            
            # Map z_avg to brightness
            if model_z_near != model_z_far:
                z_norm = (z_avg - model_z_far) / (model_z_near - model_z_far)
            else:
                z_norm = 0.5
            brightness = 0.3 + 0.7 * z_norm
            brightness = max(0.2, min(1.0, brightness))
            
            r, g, b = hsv_to_rgb(color_hue, 1.0, brightness)
            pen = graphics.create_pen(r, g, b)
            graphics.set_pen(pen)
            graphics.line(x1, y1, x2, y2)
        
        gu.update(graphics)
        t += 0.04
        await uasyncio.sleep(0.001)

async def run(graphics, gu, state, interrupt_event):
    wireframe_list = get_wireframe_list()
    wireframe_queue = wireframe_list.copy()
    shuffle(wireframe_queue)

    if not wireframe_list:
        # Fallback - draw cube if no wireframe files
        fallback_data = {
            'vertices': [(-50, -50, -50), (50, -50, -50), (50, 50, -50), (-50, 50, -50),
                        (-50, -50, 50), (50, -50, 50), (50, 50, 50), (-50, 50, 50)],
            'edges': [(0, 1, 0, 1), (1, 2, 1, 2), (2, 3, 2, 3), (3, 0, 3, 0),
                     (4, 5, 4, 5), (5, 6, 5, 6), (6, 7, 6, 7), (7, 4, 7, 4),
                     (0, 4, 0, 4), (1, 5, 1, 5), (2, 6, 2, 6), (3, 7, 3, 7)],
            'faces': [(0, 0, -1), (0, 0, 1), (-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0)],
            'backface_culling': False,
            'scale_factor': 1.0
        }
        await render_wireframe(graphics, gu, fallback_data, interrupt_event, 30.0)
        return
    
    model_duration = 30.0  # seconds to show each model
    
    while not interrupt_event.is_set():
        # take wireframe from queue
        wireframe_name = wireframe_queue.pop(0)
        # and put it on the end for looping.
        wireframe_queue.append(wireframe_name)
        module_path = f"wireframes.{wireframe_name}"

        log(f"Wireframe: {wireframe_name}", "INFO")

        try:
            # load wireframe data
            mod = __import__(module_path, globals(), locals(), [wireframe_name], 0)
            
            wireframe_data = {
                'vertices': getattr(mod, 'VERTICES'),
                'edges': getattr(mod, 'EDGES'), 
                'faces': getattr(mod, 'FACES', []),
                'backface_culling': getattr(mod, 'BACKFACE_CULLING', False),
                'scale_factor': getattr(mod, 'SCALE_FACTOR', 1.0)
            }
            
            # render wireframe
            await render_wireframe(graphics, gu, wireframe_data, interrupt_event, model_duration)
            
        except Exception as e:
            print(f"Error loading wireframe {wireframe_name}: {e}")
            interrupt_event.set()
        finally:
            # clean up the module to free memory
            if module_path in sys.modules:
                del sys.modules[module_path]
            gc.collect()
        
