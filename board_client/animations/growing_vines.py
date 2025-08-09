import uasyncio
import random
import math

from animations.utils import hsv_to_rgb
from uw.hardware import WIDTH, HEIGHT

async def run(graphics, gu, state, interrupt_event):
    # growing vines effect

    NUM_VINES = 8
    MAX_ACTIVE_VINES = 12
    MAX_LENGTH = 40 + WIDTH // 2
    BRANCH_PROB = 0.06
    ANGLE_VARIATION = math.pi / 5
    FLOWER_CHANCE = 0.04
    FLOWER_COLOURS = [
        (0.95, 0.7, 1.0),  # Pink
        (0.12, 0.8, 1.0),  # Yellow
        (0.0, 0.8, 1.0),   # Red
        (0.6, 0.7, 1.0),   # Blue
        (0.33, 0.5, 1.0),  # Light green
    ]
    
    VINE_SHADES = [
        (0.33, 1.0, 1.0),  # Bright green
        (0.18, 0.7, 0.7),  # Olive
        (0.08, 0.8, 0.5),  # Brown
        (0.25, 0.8, 0.9),  # Forest green
        (0.40, 0.6, 0.8),  # Blue-green
        (0.15, 0.9, 0.6),  # Dark olive
    ]

    class Vine:
        __slots__ = ("x", "y", "angle", "shade", "length", "max_length", "alive", "growth_speed", "thickness", "vine_type")
        def __init__(self, x, y, angle, shade):
            self.x = x
            self.y = y
            self.angle = angle
            self.shade = shade
            self.length = 0
            self.max_length = random.randint(MAX_LENGTH // 2, MAX_LENGTH)
            self.alive = True
            self.growth_speed = random.uniform(0.7, 1.3)  # Varied growth speeds
            self.thickness = random.choice([1, 2])  # Some vines are thicker
            self.vine_type = random.choice(['straight', 'curvy', 'zigzag'])  # Growth patterns

        def grow(self):
            if not self.alive:
                return
            
            # Apply vine-type specific movement patterns
            if self.vine_type == 'curvy':
                # Smooth sine wave curves
                curve_factor = math.sin(self.length * 0.2) * 0.3
                self.angle += curve_factor
            elif self.vine_type == 'zigzag':
                # Sharp directional changes
                if self.length % 8 == 0:  # Change direction every 8 steps
                    self.angle += random.uniform(-ANGLE_VARIATION * 2, ANGLE_VARIATION * 2)
            
            # Move with varied speed
            step = self.growth_speed
            nx = self.x + math.cos(self.angle) * step
            ny = self.y + math.sin(self.angle) * step
            
            # Bounce off edges
            bounced = False
            if nx < 0:
                nx = 0
                self.angle = math.pi - self.angle + random.uniform(-ANGLE_VARIATION, ANGLE_VARIATION)
                bounced = True
            elif nx > WIDTH - 1:
                nx = WIDTH - 1
                self.angle = math.pi - self.angle + random.uniform(-ANGLE_VARIATION, ANGLE_VARIATION)
                bounced = True
            if ny < 0:
                ny = 0
                self.angle = -self.angle + random.uniform(-ANGLE_VARIATION, ANGLE_VARIATION)
                bounced = True
            elif ny > HEIGHT - 1:
                ny = HEIGHT - 1
                self.angle = -self.angle + random.uniform(-ANGLE_VARIATION, ANGLE_VARIATION)
                bounced = True
                
            # Random direction changes for variety
            if not bounced and random.random() < BRANCH_PROB:
                variation_strength = ANGLE_VARIATION * (2.0 if self.vine_type == 'zigzag' else 1.0)
                self.angle += random.uniform(-variation_strength, variation_strength)
                
            self.x, self.y = nx, ny
            self.length += 1
            if self.length >= self.max_length:
                self.alive = False
        
        def get_head_pos(self):
            """Get the current head position for interaction detection"""
            return (int(round(self.x)), int(round(self.y)))
        
        def interact_with(self, other_vine):
            """Interact when vine heads are close"""
            if not self.alive or not other_vine.alive:
                return False
                
            dx = self.x - other_vine.x
            dy = self.y - other_vine.y
            distance = math.sqrt(dx*dx + dy*dy)
            
            # Interact if heads are within 3 pixels
            if distance < 3.0:
                # Vines "attract" to each other slightly
                attraction_strength = 0.3
                if distance > 0:
                    # Adjust angles toward each other
                    attraction_angle = math.atan2(dy, dx)
                    self.angle += attraction_strength * (attraction_angle - self.angle)
                    other_vine.angle += attraction_strength * (attraction_angle + math.pi - other_vine.angle)
                return True
            return False

    t = 0.0

    while not interrupt_event.is_set():
        # Clear display
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # Start new vines
        vines = []
        for _ in range(NUM_VINES):
            if random.random() < 0.4:
                x = random.uniform(2, WIDTH - 3)
                y = HEIGHT - 1
                angle = -math.pi / 2 + random.uniform(-0.4, 0.4)
            elif random.random() < 0.5:
                side = random.choice([0, WIDTH - 1])
                x = side
                y = random.uniform(HEIGHT * 0.3, HEIGHT * 0.9)
                angle = math.pi if side == WIDTH - 1 else 0
                angle += random.uniform(-0.5, 0.5)
            else:
                x = WIDTH / 2 + random.uniform(-2, 2)
                y = HEIGHT / 2 + random.uniform(-2, 2)
                angle = random.uniform(-math.pi, math.pi)
            shade = random.choice(VINE_SHADES)
            vines.append(Vine(x, y, angle, shade))

        active_vines = list(vines)

        while active_vines and not interrupt_event.is_set():
            # Handle vine head interactions first
            for i in range(len(active_vines)):
                for j in range(i + 1, len(active_vines)):
                    if active_vines[i].interact_with(active_vines[j]):
                        # Create a flower at interaction point if close enough
                        if random.random() < 0.4:  # 40% chance of flower at interaction
                            ix = int((active_vines[i].x + active_vines[j].x) / 2)
                            iy = int((active_vines[i].y + active_vines[j].y) / 2)
                            if 0 <= ix < WIDTH and 0 <= iy < HEIGHT:
                                fr, fg, fb = hsv_to_rgb(*random.choice(FLOWER_COLOURS))
                                graphics.set_pen(graphics.create_pen(fr, fg, fb))
                                graphics.pixel(ix, iy)
            
            # Grow and draw all active vines
            new_vines = []
            for vine in active_vines:
                vine.grow()
                h, s, v = vine.shade
                px, py = int(round(vine.x)), int(round(vine.y))
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    # Draw vine with thickness
                    r, g, b = hsv_to_rgb(h, s, v)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(px, py)
                    
                    # Draw thicker vines with extra pixels
                    if vine.thickness == 2 and vine.length > 5:  # Only after some growth
                        # Add neighboring pixels for thickness
                        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                            thick_x, thick_y = px + dx, py + dy
                            if (0 <= thick_x < WIDTH and 0 <= thick_y < HEIGHT and 
                                random.random() < 0.6):  # 60% chance for natural look
                                # Slightly dimmer for thickness
                                tr, tg, tb = hsv_to_rgb(h, s, v * 0.8)
                                graphics.set_pen(graphics.create_pen(tr, tg, tb))
                                graphics.pixel(thick_x, thick_y)
                    
                    # Maybe draw a flower on vine head
                    if random.random() < FLOWER_CHANCE:
                        fr, fg, fb = hsv_to_rgb(*random.choice(FLOWER_COLOURS))
                        graphics.set_pen(graphics.create_pen(fr, fg, fb))
                        graphics.pixel(px, py)
                        
                # Branch with vine-type specific probability
                branch_prob = 0.03
                if vine.vine_type == 'zigzag':
                    branch_prob *= 1.5  # Zigzag vines branch more
                elif vine.vine_type == 'curvy':
                    branch_prob *= 0.7  # Curvy vines branch less
                    
                if (vine.alive and random.random() < branch_prob and
                    len(active_vines) + len(new_vines) < MAX_ACTIVE_VINES):
                    branch_angle = vine.angle + random.uniform(-ANGLE_VARIATION, ANGLE_VARIATION)
                    branch_shade = random.choice(VINE_SHADES)
                    # Branch inherits some characteristics but with variation
                    branch_vine = Vine(vine.x, vine.y, branch_angle, branch_shade)
                    # Sometimes branches have different patterns
                    if random.random() < 0.3:
                        branch_vine.vine_type = random.choice(['straight', 'curvy', 'zigzag'])
                    new_vines.append(branch_vine)
                    
            # Prune dead vines
            active_vines = [v for v in active_vines if v.alive]
            # Add new branches
            active_vines.extend(new_vines)
            gu.update(graphics)
            t += 0.04
            await uasyncio.sleep(0.02)
