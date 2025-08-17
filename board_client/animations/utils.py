import math
import micropython
import array
import utime
import ustruct
import gc

_TWO_PI = micropython.const(math.pi * 2.0)
_INV_TWO_PI = micropython.const(1.0 / (math.pi * 2.0))
_TABLE_SIZE = micropython.const(100)
_TABLE_SIZE_FLOAT = micropython.const(100.0)

SIN_TABLE = array.array('f', [math.sin(i / _TABLE_SIZE_FLOAT * _TWO_PI) for i in range(_TABLE_SIZE)])
COS_TABLE = array.array('f', [math.cos(i / _TABLE_SIZE_FLOAT * _TWO_PI) for i in range(_TABLE_SIZE)])

@micropython.native
def fast_sin(angle):
    angle %= _TWO_PI
    if angle < 0.0: angle += _TWO_PI
    index_f = angle * _INV_TWO_PI * _TABLE_SIZE_FLOAT
    index = int(index_f)
    if index < 0: index = 0
    if index >= _TABLE_SIZE: index = _TABLE_SIZE - 1
    return SIN_TABLE[index]

@micropython.native
def fast_cos(angle):
    angle %= _TWO_PI
    if angle < 0.0: angle += _TWO_PI
    index_f = angle * _INV_TWO_PI * _TABLE_SIZE_FLOAT
    index = int(index_f)
    if index < 0: index = 0
    if index >= _TABLE_SIZE: index = _TABLE_SIZE - 1
    return COS_TABLE[index]

@micropython.native
def hsv_to_rgb(h, s, v):
    # Bounds checking at the source - prevent all array index errors
    h = max(0.0, min(1.0, float(h)))
    s = max(0.0, min(1.0, float(s)))
    v = max(0.0, min(1.0, float(v)))
    
    if s == 0.0:
        v_int = int(v * 255.0 + 0.5)
        v_int = max(0, min(255, v_int))
        return v_int, v_int, v_int

    i = int(h * 6.0)
    f = (h * 6.0) - i
    p = int((v * (1.0 - s)) * 255.0 + 0.5)
    q = int((v * (1.0 - s * f)) * 255.0 + 0.5)
    t = int((v * (1.0 - s * (1.0 - f))) * 255.0 + 0.5)
    v_int = int(v * 255.0 + 0.5)

    p = max(0, min(255, p))
    q = max(0, min(255, q))
    t = max(0, min(255, t))
    v_int = max(0, min(255, v_int))

    i %= 6
    if i == 0: return v_int, t, p
    if i == 1: return q, v_int, p
    if i == 2: return p, v_int, t
    if i == 3: return p, q, v_int
    if i == 4: return t, p, v_int
    return v_int, p, q

def lerp(a, b, t, max_t):
    return a + (b - a) * t // max_t

def make_palette(keys, size):
    palette = []
    n = len(keys)
    seg = size // (n - 1)
    for i in range(n - 1):
        c1 = keys[i]
        c2 = keys[i + 1]
        for j in range(seg):
            r = lerp(c1[0], c2[0], j, seg)
            g = lerp(c1[1], c2[1], j, seg)
            b = lerp(c1[2], c2[2], j, seg)
            palette.append((r, g, b))
    while len(palette) < size:
        palette.append(keys[-1])
    return palette

def falloff(dy, width):
    dy = abs(dy)
    if dy > width:
        return 0
    return (255 * (width - dy)) // width

# Universal Memory Optimizations (Items 50, 51, 52)

# Item 50: Universal object pooling system
class UniversalObjectPool:
    """Generic object pool for any type with reset() method"""
    def __init__(self, factory_func, initial_size=10, max_size=50):
        self.factory_func = factory_func
        self.available = [factory_func() for _ in range(initial_size)]
        self.in_use = []
        self.max_size = max_size
    
    def acquire(self):
        if self.available:
            obj = self.available.pop()
        else:
            obj = self.factory_func()
        self.in_use.append(obj)
        return obj
    
    def release(self, obj):
        if obj in self.in_use:
            self.in_use.remove(obj)
            if len(self.available) < self.max_size:
                self.available.append(obj)
    
    def release_all(self):
        space = max(0, self.max_size - len(self.available))
        if space > 0:
            moved = self.in_use[:space]
            self.available.extend(moved)
            # Remove the moved objects from in_use
            self.in_use = self.in_use[space:]
        else:
            # No space available, just clear in_use (objects are discarded)
            self.in_use.clear()

# Item 51: Color depth reduction using 6-6-6 RGB palette quantization
COLOR_PALETTE_666 = []
# Pre-generate 6-6-6 RGB palette (216 colors)
for r in range(6):
    for g in range(6):
        for b in range(6):
            COLOR_PALETTE_666.append((
                r * 51,  # 0, 51, 102, 153, 204, 255
                g * 51,
                b * 51
            ))

def quantize_color_666(r, g, b):
    """Quantize RGB color to 6-6-6 palette with bounds checking"""
    # Ensure inputs are valid integers in 0-255 range
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g))) 
    b = max(0, min(255, int(b)))
    
    # Quantize to 6 levels (0-5) with proper bounds checking
    qr = max(0, min(5, r // 43))  # 255/6 ≈ 43
    qg = max(0, min(5, g // 43))
    qb = max(0, min(5, b // 43))
    
    # Calculate index with bounds checking
    index = qr * 36 + qg * 6 + qb
    index = max(0, min(len(COLOR_PALETTE_666) - 1, index))
    
    return COLOR_PALETTE_666[index]

# Item 52: Structured array packing using ustruct
class PackedData:
    """Base class for ustruct-based data packing"""
    def __init__(self, format_string):
        self.format = format_string
        self.size = ustruct.calcsize(format_string)
        self.buffer = bytearray(self.size)
    
    def pack(self, *values):
        ustruct.pack_into(self.format, self.buffer, 0, *values)
        return self.buffer
    
    def unpack(self, data=None):
        if data is None:
            data = self.buffer
        return ustruct.unpack(self.format, data)

class PackedPosition(PackedData):
    """Pack x, y, vx, vy as 4 signed shorts (8 bytes vs 16+ bytes for floats)"""
    def __init__(self):
        super().__init__('hhhh')  # 4 signed shorts
    
    def pack_position(self, x, y, vx, vy, scale=100):
        """Pack position data with fixed-point scaling"""
        return self.pack(
            int(x * scale), int(y * scale),
            int(vx * scale), int(vy * scale)
        )
    
    def unpack_position(self, data=None, scale=100):
        """Unpack position data back to floats"""
        x, y, vx, vy = self.unpack(data)
        return x / scale, y / scale, vx / scale, vy / scale

class PackedColor(PackedData):
    """Pack RGB + additional data as bytes"""
    def __init__(self):
        super().__init__('BBBB')  # 4 unsigned bytes
    
    def pack_color_data(self, r, g, b, extra=0):
        return self.pack(r & 0xFF, g & 0xFF, b & 0xFF, extra & 0xFF)
    
    def unpack_color_data(self, data=None):
        return self.unpack(data)

# Buffer reuse system (Item 49 - related to universal optimizations)
class BufferManager:
    """Manage reusable buffers to reduce allocations"""
    def __init__(self):
        self.float_buffers = {}  # size -> [buffer1, buffer2, ...]
        self.int_buffers = {}
        self.byte_buffers = {}
    
    def get_float_buffer(self, size):
        if size not in self.float_buffers:
            self.float_buffers[size] = []
        
        if self.float_buffers[size]:
            buf = self.float_buffers[size].pop()
            # Clear the buffer
            for i in range(len(buf)):
                buf[i] = 0.0
            return buf
        else:
            return [0.0] * size
    
    def return_float_buffer(self, buf, max_cached=3):
        size = len(buf)
        if size not in self.float_buffers:
            self.float_buffers[size] = []
        
        if len(self.float_buffers[size]) < max_cached:
            self.float_buffers[size].append(buf)
    
    def get_int_buffer(self, size):
        if size not in self.int_buffers:
            self.int_buffers[size] = []
        
        if self.int_buffers[size]:
            buf = self.int_buffers[size].pop()
            # Clear the buffer
            for i in range(len(buf)):
                buf[i] = 0
            return buf
        else:
            return [0] * size
    
    def return_int_buffer(self, buf, max_cached=3):
        size = len(buf)
        if size not in self.int_buffers:
            self.int_buffers[size] = []
        
        if len(self.int_buffers[size]) < max_cached:
            self.int_buffers[size].append(buf)

# Global buffer manager instance
buffer_manager = BufferManager()


# Strategic garbage collection (Item 53)
def strategic_gc():
    """Perform garbage collection at strategic times"""
    gc.collect()
    
def get_memory_info():
    """Get current memory usage info"""
    try:
        import gc
        return {
            'free': gc.mem_free(),
            'allocated': gc.mem_alloc()
        }
    except Exception as e:
        # Only catch non-system-exiting exceptions
        # Could add logging here if needed: log(f"Memory info unavailable: {e}", "DEBUG")
        return {'free': 0, 'allocated': 0}

class uwPrng:
    def __init__(self, seed=None):
        if seed is None:
            seed = utime.time()
        self.state = seed & 0xFFFFFFFF

    def next(self):
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state

    def randint(self, a, b):
        if a > b:
            a, b = b, a
        rng = b - a + 1
        return a + (self.next() % rng)

    def randfloat(self, a=0.0, b=1.0):
        fraction = self.next() / 4294967295.0  # 0xFFFFFFFF
        return a + (b - a) * fraction