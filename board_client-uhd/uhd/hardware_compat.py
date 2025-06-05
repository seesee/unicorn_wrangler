"""
Hardware compatibility layer for Unicorn HAT HD - Optimized for Rapid Updates
"""

import unicornhathd
import math # Keep math for potential future use, not directly used in this version
import gc
# PIL is not used for core display if streaming sends raw frames
# from PIL import Image, ImageDraw, ImageFont

# Hardware constants (fake a stellar unicorn)
WIDTH, HEIGHT = 16, 16
MODEL = "stellar"

class GraphicsWrapper:
    """Wrapper to make unicornhathd behave like Pimoroni graphics - Optimized"""
    
    def __init__(self):
        self.width = WIDTH
        self.height = HEIGHT
        
        # Pen Management:
        # self.current_pen_tuple stores the (r,g,b) tuple
        # self.pens_cache maps (r,g,b) tuples to integer IDs for compatibility
        # self.current_pen_id is the integer ID for compatibility with set_pen(id)
        self.current_pen_tuple = (255, 255, 255) # Default to white
        self.pens_cache = {} # Cache for (r,g,b) -> id
        self.pen_id_to_rgb_cache = {} # Cache for id -> (r,g,b)
        self.next_pen_id = 0
        
        # Buffer stores (r,g,b) tuples directly
        self.buffer = [[(0, 0, 0) for _ in range(HEIGHT)] for _ in range(WIDTH)]
        
        # Font setup for text rendering (using bitmap font to avoid PIL for now)
        # self.font = None # Not using PIL fonts in this optimized version for display
        # self._load_font() # If you need PIL text, uncomment and manage its memory
    
    def get_bounds(self):
        return (self.width, self.height)
    
    def create_pen(self, r, g, b):
        """Create a pen with RGB values. Reuses existing pens for the same color."""
        r, g, b = int(r), int(g), int(b)
        color_tuple = (r, g, b)
        
        if color_tuple in self.pens_cache:
            return self.pens_cache[color_tuple]
        else:
            pen_id = self.next_pen_id
            self.pens_cache[color_tuple] = pen_id
            self.pen_id_to_rgb_cache[pen_id] = color_tuple
            self.next_pen_id += 1
            return pen_id
    
    def set_pen(self, pen_id_or_tuple):
        """Set the current pen. Accepts an ID or an (r,g,b) tuple."""
        if isinstance(pen_id_or_tuple, tuple) and len(pen_id_or_tuple) == 3:
            # Direct RGB tuple
            r, g, b = int(pen_id_or_tuple[0]), int(pen_id_or_tuple[1]), int(pen_id_or_tuple[2])
            self.current_pen_tuple = (r, g, b)
            # Update/create ID for this tuple for consistency if needed elsewhere
            _ = self.create_pen(r, g, b) # Ensures it's in cache
        elif isinstance(pen_id_or_tuple, int):
            # Pen ID
            self.current_pen_tuple = self.pen_id_to_rgb_cache.get(pen_id_or_tuple, (255, 255, 255))
        else:
            # Fallback, should not happen with correct usage
            self.current_pen_tuple = (255, 255, 255) 
    
    def pixel(self, x, y):
        """Set a single pixel using the current_pen_tuple."""
        if 0 <= x < self.width and 0 <= y < self.height:
            # Directly assign the tuple, no new object creation here
            self.buffer[x][y] = self.current_pen_tuple
    
    def clear(self):
        """Clear the display buffer efficiently."""
        # Use the current_pen_tuple directly
        fill_color = self.current_pen_tuple
        for x_coord in range(self.width):
            for y_coord in range(self.height):
                self.buffer[x_coord][y_coord] = fill_color
    
    def line(self, x1, y1, x2, y2):
        """Draw a line using Bresenham's algorithm."""
        # This function will now use self.current_pen_tuple via self.pixel()
        # No changes needed here other than ensuring self.pixel() is efficient
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        
        curr_x, curr_y = x1, y1
        while True:
            self.pixel(curr_x, curr_y) # Uses optimized pixel setter
            if curr_x == x2 and curr_y == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                curr_x += sx
            if e2 < dx:
                err += dx
                curr_y += sy
    
    def text(self, text_str, x, y, wordwrap=-1, scale=1):
        """Render text using bitmap font to avoid PIL dependencies for display."""
        if not text_str:
            return
        self._draw_bitmap_text(text_str, x, y)

    def cleanup_text_cache(self):
        """No PIL cache to clean in this version for text."""
        pass # gc.collect() could be called here if other objects were created
    
    def _draw_bitmap_text(self, text_str, x_start, y_start):
        """Bitmap text renderer - memory safe."""
        # (Using a more compact char_map for brevity, expand as needed)
        char_map = {
            '0': [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]], '1': [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
            '2': [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]], '3': [[1,1,1],[0,0,1],[1,1,1],[0,0,1],[1,1,1]],
            '4': [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]], '5': [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
            '6': [[1,1,1],[1,0,0],[1,1,1],[1,0,1],[1,1,1]], '7': [[1,1,1],[0,0,1],[0,0,1],[0,0,1],[0,0,1]],
            '8': [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,1,1]], '9': [[1,1,1],[1,0,1],[1,1,1],[0,0,1],[1,1,1]],
            ' ': [[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,0,0]], ':': [[0,0,0],[0,1,0],[0,0,0],[0,1,0],[0,0,0]],
            # Add more characters as needed
        }
        
        char_x = x_start
        # self.current_pen_tuple is used by self.pixel()
        
        for char_code in text_str.upper(): # Iterate over characters
            if char_code in char_map:
                pattern = char_map[char_code]
                for y_offset, row in enumerate(pattern):
                    for x_offset, bit in enumerate(row):
                        if bit: # If pixel in char is set
                            # self.pixel will use self.current_pen_tuple
                            self.pixel(char_x + x_offset, y_start + y_offset)
                char_x += 4 # Character width + spacing (3px wide + 1px space)
            else:
                char_x += 4 # Space for unknown characters
    
    def measure_text(self, text_str, scale=1):
        """Return text width (based on 3px wide chars + 1px space)."""
        if not text_str:
            return 0
        return len(text_str) * 4 * scale # Each char takes 4 pixels width (char + space)
    
    def set_font(self, font_name):
        """Set font - ignored, always use internal bitmap font."""
        pass # In this version, we stick to the bitmap font

class UnicornWrapper:
    """Wrapper to emulate the Pimoroni Unicorn interface - Optimized for Rapid Updates"""
    
    def __init__(self):
        unicornhathd.rotation(270) # Or whatever your desired rotation is
        unicornhathd.brightness(0.5) # Default brightness
        
        self.width = WIDTH
        self.height = HEIGHT
        
        # Previous frame buffer to detect changed pixels
        self._previous_frame_buffer = [[None for _ in range(HEIGHT)] for _ in range(WIDTH)]
        self._force_redraw_all = True # Force full redraw on first update
        
        # Button constants
        self.SWITCH_A = 0 # Placeholder
        self.SWITCH_B = 1 # Placeholder
        self.SWITCH_C = 2 # Placeholder
    
    def update(self, graphics_obj): # Renamed from 'graphics' to avoid conflict
        """Update display efficiently by only sending changed pixels."""
        
        # The graphics_obj.buffer contains (r,g,b) tuples
        current_buffer = graphics_obj.buffer 
        changed_pixels = 0
        
        for y in range(self.height):
            for x in range(self.width):
                # current_pixel_color is an (r,g,b) tuple
                current_pixel_color = current_buffer[x][y] 
                
                if self._force_redraw_all or self._previous_frame_buffer[x][y] != current_pixel_color:
                    r, g, b = current_pixel_color
                    # Unicorn HAT HD expects x to be flipped for normal orientation with USB at top
                    # Adjust if your physical orientation is different
                    physical_x = self.width - 1 - x 
                    unicornhathd.set_pixel(physical_x, y, r, g, b)
                    self._previous_frame_buffer[x][y] = current_pixel_color
                    changed_pixels += 1
        
        if changed_pixels > 0 or self._force_redraw_all:
            unicornhathd.show()
            # print(f"[UnicornWrapper] Updated {changed_pixels} pixels.") # Debug
        
        self._force_redraw_all = False # Subsequent updates will be differential

    def clear_display(self):
        """Explicitly clear the physical display and internal previous_frame_buffer."""
        unicornhathd.clear()
        unicornhathd.show()
        # Reset previous buffer to ensure next update reflects the clear
        self._previous_frame_buffer = [[(0,0,0) for _ in range(HEIGHT)] for _ in range(WIDTH)]
        self._force_redraw_all = True # Next update should be a full draw if needed
        # print("[UnicornWrapper] Display cleared.") # Debug
    
    def _rgb_to_hsv(self, r, g, b): # Kept for reference, but set_pixel is simpler
        # ... (implementation from before, if you decide to use set_pixel_hsv) ...
        r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0
        cmax = max(r_norm, g_norm, b_norm)
        cmin = min(r_norm, g_norm, b_norm)
        diff = cmax - cmin
        h = 0
        if diff == 0: h = 0
        elif cmax == r_norm: h = (60 * ((g_norm - b_norm) / diff) + 360) % 360
        elif cmax == g_norm: h = (60 * ((b_norm - r_norm) / diff) + 120) % 360
        elif cmax == b_norm: h = (60 * ((r_norm - g_norm) / diff) + 240) % 360
        s = 0 if cmax == 0 else diff / cmax
        v = cmax
        return h / 360.0, s, v

    def set_brightness(self, level):
        """Set display brightness."""
        unicornhathd.brightness(max(0.0, min(1.0, level)))
    
    def is_pressed(self, button):
        """Button press simulation (Unicorn HAT HD doesn't have buttons)."""
        return False

# Create global instances
graphics = GraphicsWrapper()
gu = UnicornWrapper()

def set_brightness(level):
    """Global brightness function."""
    gu.set_brightness(level)
