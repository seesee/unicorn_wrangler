import math
import micropython
import array
import utime

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