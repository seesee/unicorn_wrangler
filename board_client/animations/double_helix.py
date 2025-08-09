import uasyncio
import math
from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

class Point3D:
    """Simple 3D point with transformation and projection"""
    def __init__(self, x, y, z, color_hue=0.6, point_type='strand'):
        self.x, self.y, self.z = x, y, z
        self.color_hue = color_hue
        self.point_type = point_type  # 'strand' or 'basepair'
        
    def transform(self, rot_x, rot_y, rot_z):
        """Apply 3D rotations"""
        # Rotate around X axis
        y1 = self.y * fast_cos(rot_x) - self.z * fast_sin(rot_x)
        z1 = self.y * fast_sin(rot_x) + self.z * fast_cos(rot_x)
        
        # Rotate around Y axis  
        x2 = self.x * fast_cos(rot_y) + z1 * fast_sin(rot_y)
        z2 = -self.x * fast_sin(rot_y) + z1 * fast_cos(rot_y)
        
        # Rotate around Z axis
        x3 = x2 * fast_cos(rot_z) - y1 * fast_sin(rot_z)
        y3 = x2 * fast_sin(rot_z) + y1 * fast_cos(rot_z)
        
        return Point3D(x3, y3, z2, self.color_hue, self.point_type)
    
    def project(self, zoom=100, camera_distance=80):
        """Project to 2D screen coordinates with depth"""
        # Perspective projection
        z_cam = self.z + camera_distance
        if z_cam <= 0:
            z_cam = 0.1
            
        scale = zoom / z_cam
        screen_x = int(self.x * scale + WIDTH / 2)
        screen_y = int(self.y * scale + HEIGHT / 2)
        
        # Depth-based brightness
        brightness = max(0.2, min(1.0, 60.0 / z_cam))
        
        return screen_x, screen_y, brightness, z_cam

class HelixLine:
    """Line segment connecting two 3D points"""
    def __init__(self, p1, p2, color_hue=0.3):
        self.p1, self.p2 = p1, p2
        self.color_hue = color_hue
        
    def transform(self, rot_x, rot_y, rot_z):
        """Transform both endpoints"""
        tp1 = self.p1.transform(rot_x, rot_y, rot_z)
        tp2 = self.p2.transform(rot_x, rot_y, rot_z)
        return HelixLine(tp1, tp2, self.color_hue)
    
    def project_and_draw(self, graphics, zoom, camera_distance):
        """Project and draw the line if both points are on screen"""
        x1, y1, b1, z1 = self.p1.project(zoom, camera_distance)
        x2, y2, b2, z2 = self.p2.project(zoom, camera_distance)
        
        # Only draw if both points are roughly on screen
        if (-10 <= x1 <= WIDTH + 10 and -10 <= y1 <= HEIGHT + 10 and
            -10 <= x2 <= WIDTH + 10 and -10 <= y2 <= HEIGHT + 10):
            
            avg_brightness = (b1 + b2) / 2
            r, g, b = hsv_to_rgb(self.color_hue, 0.9, avg_brightness)
            graphics.set_pen(graphics.create_pen(r, g, b))
            graphics.line(x1, y1, x2, y2)
            return (z1 + z2) / 2  # Average depth for sorting
        return float('inf')

def generate_helix_points():
    """Generate 3D points for DNA double helix structure"""
    points = []
    lines = []
    
    # Helix parameters
    helix_radius = 12
    helix_height = 60
    num_points = 40
    num_base_pairs = 12
    twist_factor = 4.0  # Number of full rotations
    
    # Generate strand points
    strand1_points = []
    strand2_points = []
    
    for i in range(num_points):
        t = i / (num_points - 1)
        angle = t * twist_factor * 2 * math.pi
        z = -helix_height / 2 + t * helix_height
        
        # Strand 1 (blue)
        x1 = helix_radius * fast_cos(angle)
        y1 = helix_radius * fast_sin(angle)
        p1 = Point3D(x1, y1, z, 0.6, 'strand')  # Blue hue
        strand1_points.append(p1)
        points.append(p1)
        
        # Strand 2 (red) - opposite side
        x2 = -x1
        y2 = -y1
        p2 = Point3D(x2, y2, z, 0.0, 'strand')  # Red hue
        strand2_points.append(p2)
        points.append(p2)
    
    # Connect strand backbones
    for i in range(len(strand1_points) - 1):
        lines.append(HelixLine(strand1_points[i], strand1_points[i + 1], 0.6))  # Blue
        lines.append(HelixLine(strand2_points[i], strand2_points[i + 1], 0.0))  # Red
    
    # Generate base pairs (connecting rungs)
    for i in range(num_base_pairs):
        t = i / (num_base_pairs - 1)
        angle = t * twist_factor * 2 * math.pi
        z = -helix_height / 2 + t * helix_height
        
        # Base pair endpoints
        x1 = helix_radius * fast_cos(angle)
        y1 = helix_radius * fast_sin(angle)
        p1 = Point3D(x1, y1, z, 0.3, 'basepair')  # Green hue
        
        x2 = -x1
        y2 = -y1  
        p2 = Point3D(x2, y2, z, 0.3, 'basepair')  # Green hue
        
        # Add base pair line
        lines.append(HelixLine(p1, p2, 0.3))  # Green
    
    return points, lines

async def run(graphics, gu, state, interrupt_event):
    """Main animation loop with 3D camera movement"""
    
    # Generate the helix structure
    helix_points, helix_lines = generate_helix_points()
    
    # Animation state
    time = 0.0
    rotation_speed = 0.12
    camera_orbit_speed = 0.08
    camera_tilt_speed = 0.05
    zoom_speed = 0.06
    
    # Base parameters
    base_zoom = min(WIDTH, HEIGHT) * 2.5
    
    while not interrupt_event.is_set():
        # Clear screen
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        
        # Calculate camera parameters
        helix_rotation = time * rotation_speed
        camera_orbit = fast_sin(time * camera_orbit_speed) * 1.2
        camera_tilt = fast_sin(time * camera_tilt_speed) * 0.6
        zoom = base_zoom * (1.0 + 0.2 * fast_sin(time * zoom_speed))
        
        # Transform all geometry
        transformed_lines = []
        for line in helix_lines:
            t_line = line.transform(camera_tilt, camera_orbit, helix_rotation)
            transformed_lines.append(t_line)
        
        # Project and collect lines with depth info
        line_depths = []
        for line in transformed_lines:
            depth = line.project_and_draw(graphics, zoom, 80)
            if depth != float('inf'):
                line_depths.append(depth)
        
        # Draw strand points for extra detail
        for point in helix_points:
            if point.point_type == 'strand':  # Only draw strand points, not base pair points
                t_point = point.transform(camera_tilt, camera_orbit, helix_rotation)
                x, y, brightness, z = t_point.project(zoom, 80)
                
                if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                    r, g, b = hsv_to_rgb(t_point.color_hue, 1.0, brightness)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(x, y)
        
        # Update display
        gu.update(graphics)
        
        # Advance animation
        time += 1.0
        await uasyncio.sleep(0.04)  # ~25 FPS