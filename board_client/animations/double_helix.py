import uasyncio
import math
from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT, MODEL

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
        
        # Enhanced depth-based brightness for better 3D effect
        # Closer objects (smaller z_cam) get brighter, farther objects get much dimmer
        brightness = max(0.05, min(1.0, (50.0 / z_cam) ** 1.8))  # More aggressive falloff
        
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
        """Project and draw double-thickness line if both points are on screen"""
        x1, y1, b1, z1 = self.p1.project(zoom, camera_distance)
        x2, y2, b2, z2 = self.p2.project(zoom, camera_distance)
        
        # Only draw if both points are roughly on screen
        if (-10 <= x1 <= WIDTH + 10 and -10 <= y1 <= HEIGHT + 10 and
            -10 <= x2 <= WIDTH + 10 and -10 <= y2 <= HEIGHT + 10):
            
            avg_brightness = (b1 + b2) / 2
            r, g, b = hsv_to_rgb(self.color_hue, 0.9, avg_brightness)
            # Create pen dynamically (no set_rgb method exists)
            line_pen = graphics.create_pen(int(r), int(g), int(b))
            graphics.set_pen(line_pen)
            
            # Draw multiple lines for thickness - adjust thickness based on depth for consistent 3D appearance
            graphics.line(x1, y1, x2, y2)  # Original line
            
            # Scale thickness based on brightness (closer = thicker, farther = thinner)
            # This compensates for perspective and keeps visual thickness consistent
            thickness_scale = max(0.3, avg_brightness)  # Never go below 30% thickness
            
            # Only add thickness if the scale suggests the line is close enough
            if thickness_scale > 0.5:  # Only thick lines for closer parts
                graphics.line(x1 + 1, y1, x2 + 1, y2)  # Right offset
                graphics.line(x1, y1 + 1, x2, y2 + 1)  # Down offset
                graphics.line(x1 - 1, y1, x2 - 1, y2)  # Left offset
                graphics.line(x1, y1 - 1, x2, y2 - 1)  # Up offset
                
                # For larger displays and very close lines, add more thickness
                if WIDTH > 16 and thickness_scale > 0.7:
                    graphics.line(x1 + 1, y1 + 1, x2 + 1, y2 + 1)  # Down-right diagonal
                    graphics.line(x1 - 1, y1 - 1, x2 - 1, y2 - 1)  # Up-left diagonal
                    if WIDTH > 32 and thickness_scale > 0.8:  # Only thickest for galactic and very close
                        graphics.line(x1 + 1, y1 - 1, x2 + 1, y2 - 1)  # Up-right diagonal
                        graphics.line(x1 - 1, y1 + 1, x2 - 1, y2 + 1)  # Down-left diagonal
                    
            return (z1 + z2) / 2  # Average depth for sorting
        return float('inf')

def generate_helix_lines():
    """Generate line segments to approximate DNA double helix structure"""
    lines = []
    
    # Helix parameters - optimized for double-thickness lines
    if MODEL == "galactic":
        # Galactic is wide (53x11) - make longer strand to use width better
        helix_radius = 12  # Slightly smaller radius to accommodate thicker lines
        helix_height = 85  # Slightly shorter to keep proportions
        num_segments = 44  # Adjust segment count for optimal thick line appearance
        twist_factor = 5.5  # Slightly fewer rotations for cleaner thick lines
    elif WIDTH >= 32:
        # Cosmic (32x32) - medium parameters
        helix_radius = 10  # Good balance for thick lines
        helix_height = 55  
        num_segments = 36  # More segments for smoother thick curves
        twist_factor = 3.8  # Optimal twist for thick line visibility
    else:
        # Stellar (16x16) - compact parameters
        helix_radius = 6   # Smaller radius for tiny display with thick lines
        helix_height = 35  # Shorter to fit better
        num_segments = 24  # Fewer segments but still smooth with thick lines
        twist_factor = 3.0  # Fewer rotations to avoid overcrowding
    
    # Generate line segments directly (no individual points)
    for i in range(num_segments):
        t1 = i / num_segments
        t2 = (i + 1) / num_segments
        
        # Calculate positions at both ends of segment
        angle1 = t1 * twist_factor * 2 * math.pi
        angle2 = t2 * twist_factor * 2 * math.pi
        z1 = -helix_height / 2 + t1 * helix_height
        z2 = -helix_height / 2 + t2 * helix_height
        
        # Strand 1 (blue) - segment from point i to point i+1
        x1_start = helix_radius * fast_cos(angle1)
        y1_start = helix_radius * fast_sin(angle1)
        x1_end = helix_radius * fast_cos(angle2)
        y1_end = helix_radius * fast_sin(angle2)
        
        p1_start = Point3D(x1_start, y1_start, z1, 0.6, 'strand')  # Blue hue
        p1_end = Point3D(x1_end, y1_end, z2, 0.6, 'strand')
        lines.append(HelixLine(p1_start, p1_end, 0.6))  # Blue
        
        # Strand 2 (red) - opposite side
        x2_start = -x1_start
        y2_start = -y1_start
        x2_end = -x1_end
        y2_end = -y1_end
        
        p2_start = Point3D(x2_start, y2_start, z1, 0.0, 'strand')  # Red hue
        p2_end = Point3D(x2_end, y2_end, z2, 0.0, 'strand')
        lines.append(HelixLine(p2_start, p2_end, 0.0))  # Red
    
    return lines

async def run(graphics, gu, state, interrupt_event):
    """Main animation loop with 3D camera movement"""
    
    # Generate the helix structure (lines only for better performance)
    helix_lines = generate_helix_lines()
    
    # Pre-allocate pens to avoid memory allocation in animation loop
    black_pen = graphics.create_pen(0, 0, 0)
    # Create reusable pen for dynamic colors
    temp_pen = graphics.create_pen(0, 0, 0)
    
    # Animation state
    time = 0.0
    rotation_speed = 0.06  # Slower for simulator
    camera_orbit_speed = 0.04
    camera_tilt_speed = 0.025
    zoom_speed = 0.03
    corkscrew_speed = 0.08  # Much slower corkscrew
    
    # Base parameters - model-specific zoom
    if MODEL == "galactic":
        # Galactic (53x11) - zoom in more to fill the wide display better
        base_zoom = WIDTH * 1.8  # Use width instead of min, zoom in closer
    else:
        # Cosmic/Stellar - standard zoom
        base_zoom = min(WIDTH, HEIGHT) * 2.5
    
    while not interrupt_event.is_set():
        # Clear screen
        graphics.set_pen(black_pen)
        graphics.clear()
        
        # Calculate camera parameters
        helix_rotation = time * rotation_speed
        camera_orbit = fast_sin(time * camera_orbit_speed) * 1.2
        camera_tilt = fast_sin(time * camera_tilt_speed) * 0.6
        zoom = base_zoom * (1.0 + 0.2 * fast_sin(time * zoom_speed))
        corkscrew_twist = time * corkscrew_speed
        
        # Transform all geometry with uniform corkscrew rotation
        transformed_lines = []
        for line in helix_lines:
            # Apply corkscrew as an additional Z-axis rotation to the entire helix
            total_z_rotation = helix_rotation + corkscrew_twist
            t_line = line.transform(camera_tilt, camera_orbit, total_z_rotation)
            transformed_lines.append(t_line)
        
        # Project and draw lines only (no individual points for better performance)
        for line in transformed_lines:
            line.project_and_draw(graphics, zoom, 80)
        
        # Update display
        gu.update(graphics)
        
        # Advance animation
        time += 1.0
        await uasyncio.sleep(0.04)  # ~25 FPS