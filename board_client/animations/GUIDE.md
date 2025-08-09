# Animation Development Guide

Complete guide to creating animations for Unicorn Wrangler. From simple effects to complex interactive displays, this guide covers everything you need to build engaging LED matrix animations.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Animation Structure](#animation-structure)
3. [API Reference](#api-reference)
4. [Graphics System](#graphics-system)
5. [Utilities & Performance](#utilities--performance)
6. [Advanced Techniques](#advanced-techniques)
7. [Debugging & Testing](#debugging--testing)
8. [Best Practices](#best-practices)
9. [Examples](#examples)

## Quick Start

### Minimal Animation Template

```python
import uasyncio
from animations.utils import hsv_to_rgb

async def run(graphics, gu, state, interrupt_event):
    """
    Main animation entry point.
    
    Args:
        graphics: Drawing canvas object
        gu: Graphics updater (call gu.update() to display)
        state: Global state object with config/data
        interrupt_event: AsyncIO event to check for early termination
    """
    t = 0.0
    
    while not interrupt_event.is_set():
        # Clear screen
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        
        # Draw your content here
        hue = (t * 0.1) % 1.0
        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
        graphics.set_pen(graphics.create_pen(r, g, b))
        graphics.circle(16, 8, 5)
        
        # Update display
        gu.update(graphics)
        
        # Control timing and frame rate
        t += 1
        await uasyncio.sleep(0.05)  # ~20 FPS
```

### Testing Your Animation

```bash
# Test in simulator
cd board_client-sim
./run.sh --animation your_animation_name

# Test specific display size
./run.sh --model cosmic --animation your_animation_name
```

## Animation Structure

### Required Function

Every animation must have this exact function signature:

```python
async def run(graphics, gu, state, interrupt_event):
    # Your animation code here
    pass
```

### File Organization

```
animations/
├── your_animation.py      # Your animation file
├── utils.py              # Shared utilities (DO NOT MODIFY)
├── README.md            # Animation catalog
└── GUIDE.md            # This file
```

### Animation Lifecycle

1. **Load**: Animation file is imported dynamically
2. **Initialize**: `run()` function is called with system objects
3. **Execute**: Animation loop runs until interrupted
4. **Cleanup**: Animation ends, memory is freed
5. **Next**: System loads next animation in sequence

## API Reference

### Graphics Object

The `graphics` object is your drawing canvas:

#### Basic Drawing
```python
# Pen management
pen = graphics.create_pen(r, g, b)  # Create RGB pen (0-255 each)
graphics.set_pen(pen)               # Set active drawing pen

# Basic shapes
graphics.clear()                    # Fill screen with current pen
graphics.pixel(x, y)               # Draw single pixel
graphics.line(x1, y1, x2, y2)      # Draw line
graphics.rectangle(x, y, w, h)     # Draw filled rectangle
graphics.circle(x, y, radius)      # Draw filled circle

# Text rendering
graphics.text(text, x, y, scale)   # Draw text (scale=1 is 8px high)
```

#### Advanced Graphics
```python
# Screen properties
width, height = graphics.get_bounds()

# Clipping (if supported)
graphics.set_clip(x, y, width, height)
graphics.remove_clip()
```

### Hardware Constants

```python
from uw.hardware import WIDTH, HEIGHT, MODEL

# WIDTH, HEIGHT: Display dimensions
# MODEL: "galactic", "cosmic", or "stellar"

# Display sizes:
# Stellar: 16x16
# Cosmic: 32x32  
# Galactic: 53x11
```

### State Object

Access global configuration and data:

```python
# Configuration access
brightness = state.config.get("general", "brightness", 0.75)
debug_mode = state.config.get("general", "debug", False)

# Animation control
if state.display_on:  # Check if display should be active
    # Draw animation
    pass
else:
    # Display is off, skip drawing or show minimal pattern
    pass

# Next animation override
if state.next_animation == "onair":
    # Switch to onair mode
    pass
```

### Interrupt Event

Always check for interruption in your main loop:

```python
while not interrupt_event.is_set():
    # Animation code here
    
    # Check more frequently for responsive animations
    if interrupt_event.is_set():
        break
        
    await uasyncio.sleep(0.016)
```

## Graphics System

### Color Management

```python
# RGB (0-255 per channel)
red_pen = graphics.create_pen(255, 0, 0)
green_pen = graphics.create_pen(0, 255, 0)
blue_pen = graphics.create_pen(0, 0, 255)

# HSV for dynamic colors
from animations.utils import hsv_to_rgb
hue = 0.5  # Blue (0.0=red, 0.33=green, 0.66=blue, 1.0=red)
saturation = 1.0  # Full saturation
value = 1.0  # Full brightness
r, g, b = hsv_to_rgb(hue, saturation, value)
pen = graphics.create_pen(r, g, b)
```

### Coordinate System

```python
# Origin (0,0) is top-left
# X increases rightward
# Y increases downward

# Center of display
center_x = WIDTH // 2
center_y = HEIGHT // 2

# Bounds checking
def safe_pixel(x, y):
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        graphics.pixel(x, y)
```

### Drawing Patterns

#### Pixel Art
```python
# Draw pixel-perfect sprites
sprite = [
    [1, 1, 0, 1, 1],
    [1, 0, 1, 0, 1],
    [0, 1, 1, 1, 0],
    [0, 1, 0, 1, 0],
    [0, 0, 1, 0, 0],
]

for y, row in enumerate(sprite):
    for x, pixel in enumerate(row):
        if pixel:
            graphics.pixel(start_x + x, start_y + y)
```

#### Geometric Patterns
```python
# Concentric circles
for radius in range(1, 10, 2):
    hue = radius * 0.1
    r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
    graphics.set_pen(graphics.create_pen(r, g, b))
    graphics.circle(center_x, center_y, radius)
```

## Utilities & Performance

### Fast Math Functions

```python
from animations.utils import fast_sin, fast_cos, hsv_to_rgb

# Use instead of math.sin/cos for 3-5x speed improvement
angle = t * 0.1
x = center_x + fast_cos(angle) * radius
y = center_y + fast_sin(angle) * radius
```

### Random Number Generation

```python
from animations.utils import uwPrng

# Seeded random number generator
rng = uwPrng(seed=12345)

# Generate numbers
random_int = rng.randint(0, 255)      # Integer in range
random_float = rng.random()           # Float 0.0-1.0
random_choice = rng.choice([1, 2, 3]) # Pick from list
```

### Interpolation

```python
from animations.utils import lerp

# Linear interpolation between values
start_value = 10
end_value = 50
current_time = 5
max_time = 10
interpolated = lerp(start_value, end_value, current_time, max_time)
# Result: 30 (halfway between 10 and 50)
```

### Memory Management

```python
# Pre-allocate arrays outside main loop
positions = [[0, 0] for _ in range(NUM_PARTICLES)]
colors = [(0, 0, 0) for _ in range(NUM_PARTICLES)]

while not interrupt_event.is_set():
    # Reuse existing objects, avoid creating new ones
    for i, pos in enumerate(positions):
        pos[0] += velocity_x[i]
        pos[1] += velocity_y[i]
        # Update in place, don't create new lists
```

## Advanced Techniques

### Multi-Layer Animations

```python
# Layer 1: Background
graphics.set_pen(graphics.create_pen(10, 10, 30))
graphics.clear()

# Layer 2: Background elements
draw_stars(graphics, star_positions)

# Layer 3: Main subject
draw_spaceship(graphics, ship_x, ship_y)

# Layer 4: Foreground effects
draw_particles(graphics, particle_list)
```

### Particle Systems

```python
class Particle:
    def __init__(self, x, y, vx, vy, life):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = life
        self.max_life = life
    
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        return self.life > 0
    
    def draw(self, graphics):
        alpha = self.life / self.max_life
        intensity = int(255 * alpha)
        graphics.set_pen(graphics.create_pen(intensity, intensity, 0))
        graphics.pixel(int(self.x), int(self.y))

# Usage
particles = []
while not interrupt_event.is_set():
    # Spawn new particles
    if len(particles) < MAX_PARTICLES:
        particles.append(Particle(x, y, random_vx, random_vy, 60))
    
    # Update and draw
    particles = [p for p in particles if p.update()]
    for particle in particles:
        particle.draw(graphics)
```

### State Machines

```python
class AnimationState:
    INTRO = 0
    MAIN = 1
    OUTRO = 2

state_machine = AnimationState.INTRO
state_timer = 0

while not interrupt_event.is_set():
    if state_machine == AnimationState.INTRO:
        draw_intro_sequence(graphics, state_timer)
        if state_timer > 60:  # 3 seconds at 20 FPS
            state_machine = AnimationState.MAIN
            state_timer = 0
    
    elif state_machine == AnimationState.MAIN:
        draw_main_animation(graphics, state_timer)
        # Main animation continues indefinitely
    
    state_timer += 1
    await uasyncio.sleep(0.05)
```

### Responsive Display Adaptation

```python
# Adapt to different display sizes
if MODEL == "galactic":
    # Wide format optimizations
    scroll_speed = 2
    text_scale = 1
elif MODEL == "cosmic":
    # Square format optimizations  
    scroll_speed = 1
    text_scale = 1
elif MODEL == "stellar":
    # Small format optimizations
    scroll_speed = 1
    text_scale = 1

# Scale elements proportionally
scale_factor = min(WIDTH / 32, HEIGHT / 32)
element_size = int(base_size * scale_factor)
```

## Debugging & Testing

### Debug Output

```python
from uw.logger import log

# Debug logging (only shows if debug=true in config)
log(f"Animation frame {frame_count}, position ({x}, {y})", "DEBUG")
log(f"Particle count: {len(particles)}", "INFO")
log(f"Error in animation: {error_msg}", "ERROR")
```

### Performance Monitoring

```python
import utime

# Frame timing
frame_start = utime.ticks_ms()
# ... animation code ...
frame_time = utime.ticks_diff(utime.ticks_ms(), frame_start)
if frame_time > 50:  # Slower than 20 FPS
    log(f"Slow frame: {frame_time}ms", "WARN")
```

### Memory Debugging

```python
import gc

# Monitor memory usage
gc.collect()
free_memory = gc.mem_free()
log(f"Free memory: {free_memory} bytes", "DEBUG")
```

### Simulator Testing

```bash
# Test different scenarios
./run.sh --animation my_animation --model galactic
./run.sh --animation my_animation --model cosmic --pixel-size 20
./run.sh --animation my_animation --model stellar

# Debug with larger pixels for detail inspection
./run.sh --animation my_animation --pixel-size 30
```

## Best Practices

### Performance Optimization

1. **Pre-calculate constants** outside the main loop
2. **Use fast_sin/fast_cos** for trigonometry
3. **Minimize object allocation** in animation loops
4. **Batch pen changes** to reduce graphics overhead
5. **Profile with timing** to identify bottlenecks

### Memory Management

1. **Pre-allocate arrays** for particles/objects
2. **Reuse objects** instead of creating new ones
3. **Use generators** for large datasets
4. **Call gc.collect()** during natural pauses

### Visual Design

1. **Design for all display sizes** - test on Galactic (wide) and Stellar (small)
2. **Consider viewing distance** - effects visible from 1-3 meters
3. **Balance contrast** - avoid pure white, use colorful highlights
4. **Smooth animations** - 15-30 FPS is sufficient, 60 FPS rarely needed

### Code Organization

1. **Single file per animation** - keep dependencies minimal
2. **Clear variable names** - `particle_x` not `px`
3. **Document complex math** - explain algorithms
4. **Handle edge cases** - bounds checking, division by zero

## Examples

### Simple Bouncing Ball

```python
import uasyncio
from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT

async def run(graphics, gu, state, interrupt_event):
    x, y = WIDTH // 2, HEIGHT // 2
    vx, vy = 1.5, 1.2
    hue = 0.0
    
    while not interrupt_event.is_set():
        # Clear screen
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        
        # Update position
        x += vx
        y += vy
        
        # Bounce off walls
        if x <= 0 or x >= WIDTH - 1:
            vx = -vx
            hue = (hue + 0.1) % 1.0
        if y <= 0 or y >= HEIGHT - 1:
            vy = -vy
            hue = (hue + 0.1) % 1.0
        
        # Draw ball
        r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
        graphics.set_pen(graphics.create_pen(r, g, b))
        graphics.circle(int(x), int(y), 2)
        
        gu.update(graphics)
        await uasyncio.sleep(0.05)
```

### Particle Fountain

```python
import uasyncio
import random
from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT

class Particle:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.x = WIDTH // 2
        self.y = HEIGHT - 1
        angle = random.uniform(-1.5, -1.5 - 1.0)  # Upward spray
        speed = random.uniform(1.0, 3.0)
        self.vx = fast_cos(angle) * speed
        self.vy = fast_sin(angle) * speed
        self.life = random.randint(30, 90)
        self.max_life = self.life
        self.hue = random.uniform(0.0, 1.0)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.1  # Gravity
        self.life -= 1
        
        return (self.life > 0 and 
                0 <= self.x < WIDTH and 
                0 <= self.y < HEIGHT)

    def draw(self, graphics):
        alpha = self.life / self.max_life
        r, g, b = hsv_to_rgb(self.hue, 1.0, alpha)
        graphics.set_pen(graphics.create_pen(r, g, b))
        graphics.pixel(int(self.x), int(self.y))

async def run(graphics, gu, state, interrupt_event):
    particles = [Particle() for _ in range(50)]
    
    while not interrupt_event.is_set():
        # Clear screen
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        
        # Update and draw particles
        for particle in particles:
            if not particle.update():
                particle.reset()  # Respawn
            particle.draw(graphics)
        
        gu.update(graphics)
        await uasyncio.sleep(0.05)
```

### Responsive Text Scroller

```python
import uasyncio
from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT

async def run(graphics, gu, state, interrupt_event):
    text = "UNICORN WRANGLER"
    text_width = len(text) * 6  # Approximate character width
    x_pos = WIDTH
    
    # Adapt scroll speed to display width
    scroll_speed = 1 if WIDTH > 40 else 0.5
    
    while not interrupt_event.is_set():
        # Clear screen
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        
        # Rainbow text effect
        for i, char in enumerate(text):
            char_x = x_pos + (i * 6)
            if -6 < char_x < WIDTH:  # Only draw visible characters
                hue = (char_x / WIDTH + 0.1) % 1.0
                r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.text(char, char_x, HEIGHT // 2 - 4, 1)
        
        # Move text
        x_pos -= scroll_speed
        if x_pos < -text_width:
            x_pos = WIDTH  # Reset to right side
        
        gu.update(graphics)
        await uasyncio.sleep(0.05)
```

## Animation Ideas

Need inspiration? Here are some animation concepts to explore:

- **Weather simulation**: Rain, snow, lightning storms
- **Mathematical visualizations**: Fractals, spirals, wave patterns
- **Game implementations**: Tetris, Pong, simple platformers  
- **Data displays**: Network activity, system monitoring, sensor data
- **Interactive effects**: Button-controlled games, sound-reactive patterns
- **Retro computers**: Classic screensavers, demo scene effects
- **Nature simulations**: Flocking birds, flowing water, growing plants

Remember: Start simple, test frequently, and optimize for the constraints of LED matrix displays. The most effective animations often use just a few well-chosen colors and clear, readable patterns.