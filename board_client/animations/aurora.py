import uasyncio
import utime

from uw.logger import log
from animations.utils import (
    uwPrng, lerp, make_palette, falloff
)
from uw.hardware import WIDTH, HEIGHT

prng = uwPrng()

SINE_TABLE = [
    int(127.5 + 127.5 * __import__('math').sin(2 * 3.14159 * i / 64))
    for i in range(64)
]

def fast_sin(idx):
    return SINE_TABLE[idx % 64]

AURORA_KEYS = [
    (0, 0, 0),                                        # black
    (prng.randint(10, 21), 0, prng.randint(25, 37)),  # deep violetish
    (0, prng.randint(25, 37), 0),                     # deep greenish
    (prng.randint(25, 35), 0, prng.randint(25, 35)),  # deep magentaish
    (0, 0, 0),                                        # black
    (0, prng.randint(18, 28), prng.randint(4, 12)),   # dark greenish
    (prng.randint(10, 21), 0, prng.randint(25, 37)),  # deep violetish
    (0, prng.randint(25, 37), 0),                     # deep greenish
    (0, 0, 0),                                        # back to black
]

PALETTE_SIZE = 64
PALETTE = make_palette(AURORA_KEYS, PALETTE_SIZE)

# Pre-allocated pens for palette-based rendering (Item 9)
PALETTE_PENS = []

def curtain_params(prng, HEIGHT):
    # Wider bands for cosmic, but still safe for small displays
    min_width = max(6, HEIGHT // 4)
    max_width = max(min_width + 1, HEIGHT // 2)
    width = prng.randint(min_width, max_width)

    # Amplitude: 60% to 100% of width, but not more than (HEIGHT//2 - margin)
    margin = width // 2 + 1
    max_amp = min(int(width * 1.0), (HEIGHT // 2) - margin)
    min_amp = max(3, int(width * 0.6))
    amplitude = prng.randint(min_amp, max_amp) if max_amp > min_amp else min_amp

    # y_offset: anywhere, but keep the band visible
    min_y = margin
    max_y = HEIGHT - margin - 1
    if max_y < min_y:
        min_y = 0
        max_y = HEIGHT - 1
    y_offset = prng.randint(min_y, max_y)

    speed = prng.randint(-3, 3)
    phase = prng.randint(0, 63)
    freq1 = prng.randint(1, 5)
    freq2 = prng.randint(3, 9)

    return (amplitude, speed, phase, y_offset, width, freq1, freq2)

CURTAINS = [curtain_params(prng, HEIGHT) for _ in range(3)]

#CURTAINS = [
#    (12, 1, 0, 8, 12, 1, 3),
#    (10, 2, 21, 16, 14, 2, 5),
#    (8, -1, 37, 24, 13, 3, 7),
#]

for c in CURTAINS:
    log(c, "DEBUG")

# Pre-calculated noise lookup table covering all x,y combinations (CR fix)
NOISE_TABLE_SIZE = 1024  # 32x32 = 1024 entries for all x,y combos
NOISE_TABLE = []
for i in range(NOISE_TABLE_SIZE):
    x, y = i & 0x1F, (i >> 5) & 0x1F  # Remove t from precomputation
    # Use t=0 baseline for lookup table
    n1 = (((x * 13 + y * 17) & 0x7) - 4) // 2
    n2 = (((x * 7 + y * 11) & 0x3) - 2)
    NOISE_TABLE.append(n1 + n2)

def hash_noise(x, y, t):
    # Use lookup table for x,y patterns with time variance when needed
    xy_idx = (x & 0x1F) | ((y & 0x1F) << 5)
    base_noise = NOISE_TABLE[xy_idx]  # Always valid now
    
    # Add time variance for animated effects (only when t != 0)
    if t & 0x3:  # Only add time cost when t changes significantly
        t1 = t // 6
        t2 = t // 11
        time_noise = (((t1 * 23) & 0x3) - 1) + (((t2 * 19) & 0x1) - 1)
        return base_noise + time_noise
    
    return base_noise

async def run(graphics, gu, state, interrupt_event):
    frame = 0
    palette_offset = 0
    black_pen = graphics.create_pen(0, 0, 0)
    palette_cycle_speed = 3
    movement_speed = 0.18
    
    # Pre-allocate all palette pens (Item 9)
    global PALETTE_PENS
    if not PALETTE_PENS:
        PALETTE_PENS = [graphics.create_pen(r, g, b) for r, g, b in PALETTE]

    # Fixed-point smoothing buffer using int16 (Item 8)
    # Scale factor: 256 for 8.8 fixed point arithmetic
    FIXED_SCALE = 256
    prev_idx = [[0 for _ in range(HEIGHT)] for _ in range(WIDTH)]
    alpha_fixed = int(0.18 * FIXED_SCALE)  # Convert to fixed-point
    alpha_inv_fixed = FIXED_SCALE - alpha_fixed

    while not interrupt_event.is_set():
        graphics.set_pen(black_pen)
        graphics.clear()

        global_y_drift = (fast_sin(frame // 24) - 127) // 14
        global_x_drift = (fast_sin((frame // 36) + 16) - 127) // 20

        # Pre-calculate per-curtain values to avoid repeated calculations
        curtain_params = []
        frame_speed_offset = int(frame * movement_speed)
        for i, (amp, speed, phase, y_offset, width, freq1, freq2) in enumerate(CURTAINS):
            tmod = frame // (40 + i * 8)
            phase_mod = (fast_sin((frame // (32 + i * 7)) + i * 21) - 127) // 4
            f1 = freq1 + ((fast_sin(tmod + phase + i * 13) - 127) // (64 + i * 8))
            f2 = freq2 + ((fast_sin(tmod + phase + 16 + i * 17) - 127) // (96 + i * 8))
            base_offset1 = frame_speed_offset * speed + phase + phase_mod
            base_offset2 = frame_speed_offset * speed + phase * 2 + phase_mod
            curtain_params.append((amp, y_offset, width, f1, f2, base_offset1, base_offset2))

        for x in range(WIDTH):
            x_plus_drift = x + global_x_drift
            for y in range(HEIGHT):
                total_intensity = 0
                noise = hash_noise(x, y, frame)  # Calculate noise once per pixel
                
                for amp, y_offset, width, f1, f2, base_offset1, base_offset2 in curtain_params:
                    idx1 = (x_plus_drift * f1 + base_offset1 + noise) % 64
                    idx2 = (x_plus_drift * f2 + base_offset2 + noise) % 64
                    y_centre = y_offset \
                        + (amp * (fast_sin(idx1) - 127)) // 127 \
                        + (amp * (fast_sin(idx2) - 127)) // 255 \
                        + global_y_drift \
                        + noise
                    intensity = falloff(y - y_centre, width)
                    total_intensity += intensity

                norm_intensity = total_intensity * total_intensity // (len(CURTAINS) * 255)
                palette_idx = (norm_intensity * (PALETTE_SIZE - 1)) // (len(CURTAINS) * 255)
                palette_idx = min(max(palette_idx + palette_offset, 0), PALETTE_SIZE - 1)

                # Fixed-point smoothing (Item 8)
                prev_fixed = prev_idx[x][y]
                palette_idx_fixed = palette_idx * FIXED_SCALE
                smoothed_fixed = (prev_fixed * alpha_inv_fixed + palette_idx_fixed * alpha_fixed) >> 8
                prev_idx[x][y] = smoothed_fixed
                
                # Convert back to palette index
                smoothed = smoothed_fixed >> 8
                smoothed = min(max(smoothed, 0), PALETTE_SIZE - 1)
                
                # Use pre-allocated pen (Item 9)
                graphics.set_pen(PALETTE_PENS[smoothed])
                graphics.pixel(x, y)
        gu.update(graphics)
        frame = (frame + 1) % 4096
        if frame % palette_cycle_speed == 0:
            palette_offset = (palette_offset + 1) % PALETTE_SIZE
        await uasyncio.sleep(0.04)

