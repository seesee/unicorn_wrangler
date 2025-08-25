import uasyncio
import math
import random
from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import MODEL

class LavaBlob:
    def __init__(self, x, y, radius):
        self.x = x
        self.y = y
        self.radius = radius
        self.vx = 0.0  # Horizontal velocity (used for split momentum)
        self.vy = 0.0  # Vertical velocity (used for split momentum)
        self.state = "cold"  # "cold", "heating", "hot", "cooling", "merging", "splitting"
        self.heat_time = 0  # How long blob has been heating/cooling
        self.color_hue = random.uniform(0.0, 1.0)  # Individual color identity
        self.stretch_y = 1.0  # Vertical stretch factor for teardrop shapes
        self.at_bottom = True
        self.at_top = False
        
        # Transition state for gradual merging/splitting
        self.transition_timer = 0.0
        self.transition_duration = 1.5  # Seconds for merge/split animation
        self.target_radius = radius  # Target size during transitions
        self.original_radius = radius  # Original size before transition
        self.merge_partner = None  # Reference to blob we're merging with
        self.split_children = None  # List of blobs created from splitting
        
    def update_lifecycle(self, lamp_height, lamp_width, dt, rotated=False):
        """Update blob lifecycle with virtual heating/cooling zones"""
        # Extended physics space: 2 pixels above and below display
        # Virtual cooling zone: y = -2 to 0 (above display)
        # Display area: y = 0 to lamp_height  
        # Virtual heating zone: y = lamp_height to lamp_height + 2 (below display)
        
        pos = self.y
        display_top = 0
        display_bottom = lamp_height
        
        # Heat/cool zones include virtual areas
        heat_zone = display_bottom * 0.85  # Bottom 15% + virtual heating
        cool_zone = display_bottom * 0.15  # Top 15% + virtual cooling
        
        # Update position flags with virtual zones
        self.at_bottom = pos > heat_zone or pos > display_bottom
        self.at_top = pos < cool_zone or pos < display_top
        
        # Track virtual zone status for accelerated heating/cooling
        self.in_virtual_heating = pos > display_bottom  # Below display
        self.in_virtual_cooling = pos < display_top     # Above display
        
        # State machine for blob lifecycle
        if self.state == "cold":
            if self.at_bottom:
                self.state = "heating"
                self.heat_time = 0
                
        elif self.state == "heating":
            self.heat_time += dt
            # Faster heating if in virtual heating zone to unstick blobs
            heat_multiplier = 2.5 if hasattr(self, 'in_virtual_heating') and self.in_virtual_heating else 1.0
            heating_time = (3.0 / math.sqrt(self.radius)) / heat_multiplier
            if self.heat_time > heating_time:
                self.state = "hot"
                
        elif self.state == "hot":
            if self.at_top:
                self.state = "cooling"
                self.heat_time = 0
                
        elif self.state == "cooling":
            self.heat_time += dt
            # Faster cooling if in virtual cooling zone to unstick blobs
            cool_multiplier = 2.5 if hasattr(self, 'in_virtual_cooling') and self.in_virtual_cooling else 1.0
            cooling_time = (2.0 / math.sqrt(self.radius)) / cool_multiplier
            if self.heat_time > cooling_time:
                self.state = "cold"
                
        elif self.state == "merging":
            # Gradually grow towards target size and move towards merge point
            self.transition_timer += dt
            progress = min(1.0, self.transition_timer / self.transition_duration)
            
            # Smooth transition using ease-in-out curve
            smooth_progress = 0.5 * (1 + math.sin(math.pi * (progress - 0.5)))
            
            # Gradually change radius
            self.radius = self.original_radius + (self.target_radius - self.original_radius) * smooth_progress
            
            # Move towards merge partner if it still exists
            if self.merge_partner and hasattr(self.merge_partner, 'x'):
                target_x = (self.x + self.merge_partner.x) / 2
                target_y = (self.y + self.merge_partner.y) / 2
                self.x += (target_x - self.x) * smooth_progress * 0.3
                self.y += (target_y - self.y) * smooth_progress * 0.3
            
            # Complete merge when timer expires
            if progress >= 1.0:
                self.state = "hot"
                self.transition_timer = 0.0
                self.merge_partner = None
                
        elif self.state == "splitting":
            # Gradually shrink and separate from original position
            self.transition_timer += dt
            progress = min(1.0, self.transition_timer / self.transition_duration)
            
            # Smooth transition using ease-in-out curve
            smooth_progress = 0.5 * (1 + math.sin(math.pi * (progress - 0.5)))
            
            # Gradually change radius
            self.radius = self.original_radius - (self.original_radius - self.target_radius) * smooth_progress
            
            # Complete split when timer expires
            if progress >= 1.0:
                # Determine final state based on size
                if self.target_radius < self.original_radius * 0.7:
                    self.state = "cooling"  # Smaller blobs start cooling
                else:
                    self.state = "hot"  # Larger blobs stay hot
                self.transition_timer = 0.0
    
    def get_rise_speed(self, rotated=False):
        """Calculate how fast blob should rise/fall"""
        base_speed = 1.0 / math.sqrt(self.radius)  # Smaller = faster
        
        # For both modes: negative=rise (toward low y), positive=fall (toward high y)
        if self.state == "hot":
            return -base_speed * 1.5  # Rise quickly when hot
        elif self.state == "cold":
            return base_speed * 0.8   # Fall when cold
        elif self.state == "heating":
            progress = min(1.0, self.heat_time / (3.0 / math.sqrt(self.radius)))
            return base_speed * (1.0 - progress * 1.8)  # Gradually start rising
        elif self.state == "cooling":
            progress = min(1.0, self.heat_time / (2.0 / math.sqrt(self.radius)))
            return -base_speed * (1.5 - progress * 2.3)  # Gradually start falling
        elif self.state == "merging":
            # Slow movement during merge - gradually rise
            return -base_speed * 0.5
        elif self.state == "splitting":
            # Slow movement during split - maintain position mostly
            return base_speed * 0.1
        else:
            return 0.0
    
    def update_physics(self, lamp_height, lamp_width, dt, rotated=False):
        """Physics with split momentum and lifecycle behavior"""
        # Decrement split timer if it exists
        if hasattr(self, 'split_timer'):
            self.split_timer = max(0, self.split_timer - 1)
        
        # Get base rise/fall speed from lifecycle
        base_speed = self.get_rise_speed(rotated)
        
        # Apply movement with momentum from splitting
        # For both modes, blobs move vertically (y direction)
        self.vy = base_speed + (self.vy * 0.9)  # Split momentum decays
        self.y += self.vy * dt
        
        # Allow virtual zones: 2 pixels above (cooling) and 2 pixels below (heating) display
        if self.y < -2 + self.radius:  # Virtual cooling zone boundary
            self.y = -2 + self.radius
            self.vy = max(0, self.vy)  # Only bounce if moving up
        elif self.y > lamp_height + 2 - self.radius:  # Virtual heating zone boundary
            self.y = lamp_height + 2 - self.radius
            self.vy = min(0, self.vy)  # Only bounce if moving down too far
        
        # Apply horizontal velocity decay unconditionally to prevent accumulation
        self.vx *= 0.9
        
        # Handle horizontal boundaries (sides) - only update position when rotated
        if rotated:
            # For galactic, apply horizontal movement from splits
            self.x += self.vx * dt
            # Bounce off sides
            if self.x < self.radius:
                self.x = self.radius
                self.vx = abs(self.vx) * 0.3
            elif self.x > lamp_width - self.radius:
                self.x = lamp_width - self.radius
                self.vx = -abs(self.vx) * 0.3
        
        # Update stretch based on total movement (teardrop effect)
        velocity_mag = math.sqrt(self.vx*self.vx + self.vy*self.vy)
        if velocity_mag > 0.1:
            self.stretch_y = 1.0 + min(0.5, velocity_mag * 0.2)
        else:
            self.stretch_y = max(1.0, self.stretch_y - dt * 1.5)  # Gradually return to round
    
    def get_color(self, base_hue):
        """Get blob color based on state and individual hue"""
        if self.state == "cold":
            # Cool blues/purples
            hue = (base_hue + self.color_hue * 0.3 + 0.6) % 1.0
            saturation = 0.8
            value = 0.4
        elif self.state == "heating":
            # Warming up - mix of cool and warm
            progress = min(1.0, self.heat_time / (3.0 / math.sqrt(self.radius)))
            hue = (base_hue + self.color_hue * 0.2 + 0.5 - progress * 0.3) % 1.0
            saturation = 0.7 + progress * 0.2
            value = 0.4 + progress * 0.3
        elif self.state == "hot":
            # Hot reds/oranges/yellows
            hue = (base_hue + self.color_hue * 0.1) % 1.0
            saturation = 0.9
            value = 0.8
        elif self.state == "cooling":
            # Cooling down - mix of warm and cool
            progress = min(1.0, self.heat_time / (2.0 / math.sqrt(self.radius)))
            hue = (base_hue + self.color_hue * 0.1 + progress * 0.4) % 1.0
            saturation = 0.9 - progress * 0.2
            value = 0.8 - progress * 0.4
        elif self.state == "merging":
            # Bright, pulsing color during merge
            pulse = 0.8 + 0.2 * fast_sin(self.transition_timer * 8)  # Fast pulsing
            hue = (base_hue + self.color_hue * 0.05) % 1.0
            saturation = 1.0
            value = pulse
        elif self.state == "splitting":
            # Flickering, unstable color during split
            flicker = 0.6 + 0.4 * fast_sin(self.transition_timer * 12)  # Faster flickering
            hue = (base_hue + self.color_hue * 0.2 + self.transition_timer * 0.1) % 1.0
            saturation = 0.9
            value = flicker
        else:
            # Default fallback
            hue = (base_hue + self.color_hue * 0.2) % 1.0
            saturation = 0.8
            value = 0.6
            
        return hsv_to_rgb(hue, saturation, value)

class LavaLamp:
    def __init__(self, width, height, rotated=False):
        self.width = width
        self.height = height
        self.rotated = rotated
        
        # Color scheme
        self.base_hue = random.uniform(0.0, 1.0)
        self.hue_shift_speed = 0.002
        self.background_time = 0.0  # Time for rainbow background cycling
        
        # Initialize blobs
        self.blobs = []
        self.spawn_initial_blobs()
        
    def spawn_initial_blobs(self):
        """Create initial blob configuration - all start at bottom"""
        # Scale blob count and sizes based on display dimensions
        total_pixels = self.width * self.height
        
        if total_pixels < 300:  # Small displays like Stellar (16x16=256)
            blob_count = 4  # More blobs for interaction
            radius_range = (1.5, 3.5)  # Slightly larger max
        elif total_pixels < 800:  # Medium displays like Galactic (11x53=583)
            blob_count = 5  # More blobs
            radius_range = (2, 4)  
        else:  # Large displays like Cosmic (32x32=1024)
            blob_count = 6  # More blobs
            radius_range = (2.5, 4.5)  # Reduced max size
        
        # All blobs start at bottom in "cold" state
        for _ in range(blob_count):
            radius = random.uniform(*radius_range)
            
            # For both modes, bottom = high y values
            x = random.uniform(radius, self.width - radius)
            y = random.uniform(self.height * 0.7, self.height - radius)
            
            self.blobs.append(LavaBlob(x, y, radius))
    
    def check_merging(self):
        """Initiate gradual merging for nearby blobs with size and state restrictions"""
        # Allow merging regardless of blob count since merging reduces blob count
        # This helps reduce visual clutter when there are too many blobs
            
        for i in range(len(self.blobs)):
            for j in range(i + 1, len(self.blobs)):
                blob1, blob2 = self.blobs[i], self.blobs[j]
                
                # Only merge if both are hot and not already in transition
                if (blob1.state not in ["hot"] or blob2.state not in ["hot"]):
                    continue
                
                # Size compatibility check - more lenient now
                size_ratio = max(blob1.radius, blob2.radius) / min(blob1.radius, blob2.radius)
                if size_ratio > 2.5:  # Allow slightly more size difference
                    continue
                
                # Skip recently split blobs (but shorter timer)
                if (hasattr(blob1, 'split_timer') and blob1.split_timer > 30) or \
                   (hasattr(blob2, 'split_timer') and blob2.split_timer > 30):
                    continue
                
                dx = blob2.x - blob1.x
                dy = blob2.y - blob1.y
                dist = math.sqrt(dx*dx + dy*dy)
                
                # More generous merge distance
                if dist < (blob1.radius + blob2.radius) * 0.85:
                    # Start gradual merge - keep the larger blob and remove the smaller one
                    if blob1.radius >= blob2.radius:
                        primary_blob = blob1
                        secondary_blob = blob2
                    else:
                        primary_blob = blob2
                        secondary_blob = blob1
                    
                    # Calculate merged properties
                    total_area = primary_blob.radius**2 + secondary_blob.radius**2
                    new_radius = math.sqrt(total_area)
                    
                    # Set up merge transition on primary blob
                    primary_blob.state = "merging"
                    primary_blob.transition_timer = 0.0
                    primary_blob.original_radius = primary_blob.radius
                    primary_blob.target_radius = new_radius
                    primary_blob.merge_partner = secondary_blob
                    primary_blob.color_hue = (primary_blob.color_hue + secondary_blob.color_hue) / 2
                    
                    # Remove secondary blob immediately (it will be absorbed)
                    self.blobs.remove(secondary_blob)
                    return  # Only merge one pair per frame
    
    def check_splitting(self):
        """Initiate gradual splitting for large unstable blobs"""
        # Scale max blob count and split threshold based on display size
        total_pixels = self.width * self.height
        if total_pixels < 300:
            max_blobs = 6
            split_threshold = 3.2  # Smaller threshold for small displays
            split_chance = 0.015   # Lower chance for more gradual splitting
        elif total_pixels < 800:
            max_blobs = 8
            split_threshold = 3.8  # Medium threshold 
            split_chance = 0.02    # Lower chance for more gradual splitting
        else:
            max_blobs = 10
            split_threshold = 4.2  # Larger threshold for big displays
            split_chance = 0.015   # Lower chance for more gradual splitting
            
        for blob in self.blobs:
            # Large hot blobs are unstable and split
            if (blob.radius > split_threshold and blob.state == "hot" and 
                random.random() < split_chance and len(self.blobs) < max_blobs):
                
                # Uneven split - one large blob, one small blob (like real lava lamps)
                large_fraction = random.uniform(0.6, 0.8)  # Large blob gets 60-80% of mass
                small_fraction = 1.0 - large_fraction
                
                # Calculate radii from area fractions
                large_radius = blob.radius * math.sqrt(large_fraction)
                small_radius = blob.radius * math.sqrt(small_fraction)
                
                # Position them with some separation
                separation = blob.radius * 1.2
                angle = random.uniform(0, 2 * math.pi)
                
                # Position with more separation to prevent immediate recombination
                offset_x = fast_cos(angle) * separation
                offset_y = fast_sin(angle) * separation
                
                # Create the larger blob (inherits hot state, continues rising)
                large_blob = LavaBlob(
                    blob.x + offset_x * 0.3,
                    blob.y + offset_y * 0.3,
                    large_radius
                )
                large_blob.state = "splitting"
                large_blob.transition_timer = 0.0
                large_blob.original_radius = blob.radius
                large_blob.target_radius = large_radius
                large_blob.heat_time = blob.heat_time
                large_blob.color_hue = (blob.color_hue + 0.05) % 1.0  # Slight hue shift
                # Add gentle velocity to push away from split
                large_blob.vx = fast_cos(angle) * 0.2
                large_blob.vy = fast_sin(angle) * 0.2
                
                # Create the smaller blob (starts cooling, will fall sooner)
                small_blob = LavaBlob(
                    blob.x - offset_x * 0.5,  # Opposite side, farther away
                    blob.y - offset_y * 0.5,
                    small_radius
                )
                small_blob.state = "splitting"
                small_blob.transition_timer = 0.0
                small_blob.original_radius = blob.radius
                small_blob.target_radius = small_radius
                small_blob.heat_time = 0
                small_blob.color_hue = (blob.color_hue - 0.15) % 1.0  # More dramatic hue shift
                # Add stronger velocity to push away
                small_blob.vx = -fast_cos(angle) * 0.4
                small_blob.vy = -fast_sin(angle) * 0.4
                
                # Add split timers to prevent immediate recombining (longer for gradual effect)
                large_blob.split_timer = 60  # ~5 seconds at 12fps
                small_blob.split_timer = 60
                
                # Replace original blob with the two new ones
                self.blobs.remove(blob)
                self.blobs.extend([large_blob, small_blob])
                return  # Only split one per frame
    
    def update(self, dt):
        """Update all lava lamp physics"""
        # Update each blob's lifecycle and physics
        for blob in self.blobs:
            blob.update_lifecycle(self.height, self.width, dt, self.rotated)
            blob.update_physics(self.height, self.width, dt, self.rotated)
        
        # Handle merging and splitting
        self.check_merging()
        self.check_splitting() 
        
        # Maintain minimum blob population for good interactions
        self.maintain_blob_population()
        
        # Slowly shift base color and background cycle
        self.base_hue = (self.base_hue + self.hue_shift_speed) % 1.0
        self.background_time += dt * 0.5  # Slow rainbow cycle
    
    def maintain_blob_population(self):
        """Ensure minimum blob count for good interactions"""
        total_pixels = self.width * self.height
        
        if total_pixels < 300:
            min_blobs = 3  # Stellar needs at least 3
        elif total_pixels < 800:
            min_blobs = 4  # Galactic needs at least 4  
        else:
            min_blobs = 5  # Cosmic needs at least 5
        
        # Add new blobs if below minimum
        while len(self.blobs) < min_blobs:
            # Create a small blob at the bottom
            radius = random.uniform(1.5, 2.5)  # Start small
            x = random.uniform(radius, self.width - radius)
            y = random.uniform(self.height * 0.8, self.height - radius)
            
            new_blob = LavaBlob(x, y, radius)
            new_blob.color_hue = random.uniform(0.0, 1.0)  # Random color
            self.blobs.append(new_blob)
    
    def render(self, graphics):
        """Render lava lamp with cycling rainbow gradient background"""
        display_width, display_height = graphics.get_bounds()
        
        # Create subtle cycling rainbow gradient background
        for y in range(display_height):
            # Calculate gradient position (0.0 to 1.0)
            # For both modes, gradient runs vertically
            gradient_pos = y / max(1, display_height - 1)
            
            # Create rainbow hue that cycles over time and position
            rainbow_hue = (self.background_time * 0.1 + gradient_pos * 0.8) % 1.0
            
            # Subtle rainbow colors with more saturation and brightness - compute once per row
            bg_r, bg_g, bg_b = hsv_to_rgb(rainbow_hue, 0.6, 0.08)  # More saturated and slightly brighter
            graphics.set_pen(graphics.create_pen(bg_r, bg_g, bg_b))
            
            # Draw entire row with the same color
            for x in range(display_width):
                graphics.pixel(x, y)
        
        # Render each blob
        for blob in self.blobs:
            r, g, b = blob.get_color(self.base_hue)
            
            # Calculate screen position
            if self.rotated:
                # For galactic mode, transform coordinates for display rotation
                # Our physics coords (x,y) become screen coords (y, height-x)
                screen_x = int(blob.y)
                screen_y = int(self.width - 1 - blob.x)
                stretch_x = blob.stretch_y  # Swap stretch for rotation
                stretch_y = 1.0
            else:
                # Direct mapping for normal displays
                screen_x = int(blob.x) 
                screen_y = int(blob.y)
                stretch_x = 1.0
                stretch_y = blob.stretch_y
            
            # Render stretched blob (teardrop/pear shape when moving)
            blob_radius = max(1, int(blob.radius))
            
            # Only render if roughly on screen
            if (-blob_radius*2 <= screen_x < display_width + blob_radius*2 and 
                -blob_radius*2 <= screen_y < display_height + blob_radius*2):
                
                for dy in range(-blob_radius*2, blob_radius*2 + 1):
                    for dx in range(-blob_radius*2, blob_radius*2 + 1):
                        # Apply stretch factors
                        norm_x = dx / stretch_x if stretch_x > 0 else dx
                        norm_y = dy / stretch_y if stretch_y > 0 else dy
                        
                        # Check if within blob shape
                        if norm_x*norm_x + norm_y*norm_y <= blob_radius*blob_radius:
                            pixel_x = screen_x + dx
                            pixel_y = screen_y + dy
                            
                            if 0 <= pixel_x < display_width and 0 <= pixel_y < display_height:
                                # Soft edges with brightness falloff
                                dist_sq = norm_x*norm_x + norm_y*norm_y
                                edge_factor = dist_sq / (blob_radius*blob_radius)
                                brightness = max(0.0, min(1.0, 1.0 - edge_factor * 0.4))
                                
                                final_r = max(0, min(255, int(r * brightness)))
                                final_g = max(0, min(255, int(g * brightness))) 
                                final_b = max(0, min(255, int(b * brightness)))
                                
                                graphics.set_pen(graphics.create_pen(final_r, final_g, final_b))
                                graphics.pixel(pixel_x, pixel_y)

async def run(graphics, gu, state, interrupt_event):
    """Main animation entry point"""
    display_width, display_height = graphics.get_bounds()
    
    # Determine if we should rotate for Galactic Unicorn
    rotated = (MODEL == "galactic")
    
    # Create lava lamp with appropriate dimensions
    if rotated:
        # For rotated display, use height as width and vice versa for physics
        lamp = LavaLamp(display_height, display_width, rotated=True)
    else:
        lamp = LavaLamp(display_width, display_height, rotated=False)
    
    frame_time = 0.08  # ~12 FPS for better performance
    
    while not interrupt_event.is_set():
        # Update physics
        lamp.update(frame_time)
        
        # Render
        lamp.render(graphics)
        
        # Update display
        gu.update(graphics)
        
        await uasyncio.sleep(frame_time)