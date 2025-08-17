import uasyncio
import math
import random

from animations.utils import hsv_to_rgb, fast_sin, fast_cos

async def run(graphics, gu, state, interrupt_event):
    # the third place effect
    WIDTH, HEIGHT = graphics.get_bounds()

    INITIAL_SHAPES = 8
    MIN_SHAPES = 4
    MAX_SHAPES = 10
    MIN_EACH_TYPE = 2
    SHAPE_TYPES = ["circle", "square", "triangle", "cross"]
    MAX_SIZE = 4.0
    MIN_SIZE = 1.5
    MAX_VELOCITY = 0.65
    COLLISION_ELASTICITY = 0.92
    ROTATION_SPEED_MAX = 0.08
    SCALE_SPEED_MAX = 0.03
    CIRCLE_SEGMENTS = 10
    
    # Note: Creating pens dynamically as set_rgb method doesn't exist

    class Shape:
        def __init__(self, shape_type=None):
            self.x = random.uniform(0, WIDTH)
            self.y = random.uniform(0, HEIGHT)
            min_speed_component = 0.15
            self.vx = random.uniform(-MAX_VELOCITY, MAX_VELOCITY)
            self.vy = random.uniform(-MAX_VELOCITY, MAX_VELOCITY)
            if math.sqrt(self.vx**2 + self.vy**2) < min_speed_component * 1.4:
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(min_speed_component, MAX_VELOCITY)
                self.vx = math.cos(angle) * speed
                self.vy = math.sin(angle) * speed
            self.type = shape_type if shape_type in SHAPE_TYPES else random.choice(SHAPE_TYPES)
            self.size = random.uniform(MIN_SIZE, MAX_SIZE)
            self.hue = random.random()
            self.angle = random.uniform(0, math.pi * 2)
            self.rotation_speed = random.uniform(-ROTATION_SPEED_MAX, ROTATION_SPEED_MAX)
            self.scale = random.uniform(0.7, 1.0)
            self.scale_speed = random.uniform(-SCALE_SPEED_MAX, SCALE_SPEED_MAX)
            self.radius = 0.0
            self.update_radius()

        def update_radius(self):
            current_size = self.size * self.scale
            if self.type == "circle":
                self.radius = current_size
            elif self.type == "square":
                self.radius = current_size * 1.415
            elif self.type == "triangle":
                self.radius = current_size * 1.2
            elif self.type == "cross":
                self.radius = current_size
            self.radius = max(1.0, self.radius)

        def update(self):
            self.x += self.vx
            self.y += self.vy
            self.angle += self.rotation_speed
            self.scale += self.scale_speed
            if self.scale < 0.5 or self.scale > 1.0:
                self.scale_speed *= -1
                self.scale = max(0.5, min(1.0, self.scale))
            self.update_radius()
            r_int = int(self.radius + 0.5)
            if self.x < r_int and self.vx < 0:
                self.vx *= -1 * COLLISION_ELASTICITY
                self.x = float(r_int)
            elif self.x > WIDTH - r_int and self.vx > 0:
                self.vx *= -1 * COLLISION_ELASTICITY
                self.x = float(WIDTH - r_int)
            if self.y < r_int and self.vy < 0:
                self.vy *= -1 * COLLISION_ELASTICITY
                self.y = float(r_int)
            elif self.y > HEIGHT - r_int and self.vy > 0:
                self.vy *= -1 * COLLISION_ELASTICITY
                self.y = float(HEIGHT - r_int)

        def get_vertices(self):
            vertices = []
            s = self.size * self.scale
            if self.type == "square":
                base_corners = [(s, s), (s, -s), (-s, -s), (-s, s)]
            elif self.type == "triangle":
                base_corners = [(0 * s, -1.2 * s), (1 * s, 0.6 * s), (-1 * s, 0.6 * s)]
            else:
                return []
            cos_a = fast_cos(self.angle)
            sin_a = fast_sin(self.angle)
            for corner in base_corners:
                rx = corner[0] * cos_a - corner[1] * sin_a
                ry = corner[0] * sin_a + corner[1] * cos_a
                px = self.x + rx
                py = self.y + ry
                vertices.append((px, py))
            return vertices

        def draw(self, t):
            h = (self.hue + t * 0.05) % 1.0
            r, g, b = hsv_to_rgb(h, 1.0, 1.0)
            shape_pen = graphics.create_pen(int(r), int(g), int(b))
            graphics.set_pen(shape_pen)
            points = []
            if self.type == "circle":
                size = self.radius
                for i in range(CIRCLE_SEGMENTS):
                    angle_rad = (i / CIRCLE_SEGMENTS) * math.pi * 2
                    px = self.x + fast_cos(angle_rad) * size
                    py = self.y + fast_sin(angle_rad) * size
                    points.append((int(px), int(py)))
                if len(points) > 1:
                    for i in range(len(points)):
                        x1, y1 = points[i]
                        x2, y2 = points[(i + 1) % len(points)]
                        graphics.line(x1, y1, x2, y2)
                elif len(points) == 1:
                    graphics.pixel(points[0][0], points[0][1])
            elif self.type == "cross":
                s = self.size * self.scale
                cos_a = fast_cos(self.angle)
                sin_a = fast_sin(self.angle)
                hx1_rel, hy1_rel = -s, 0
                hx2_rel, hy2_rel = s, 0
                vx1_rel, vy1_rel = 0, -s
                vx2_rel, vy2_rel = 0, s
                hx1 = self.x + (hx1_rel * cos_a - hy1_rel * sin_a)
                hy1 = self.y + (hx1_rel * sin_a + hy1_rel * cos_a)
                hx2 = self.x + (hx2_rel * cos_a - hy2_rel * sin_a)
                hy2 = self.y + (hx2_rel * sin_a + hy2_rel * cos_a)
                vx1 = self.x + (vx1_rel * cos_a - vy1_rel * sin_a)
                vy1 = self.y + (vx1_rel * sin_a + vy1_rel * cos_a)
                vx2 = self.x + (vx2_rel * cos_a - vy2_rel * sin_a)
                vy2 = self.y + (vx2_rel * sin_a + vy2_rel * cos_a)
                graphics.line(int(hx1), int(hy1), int(hx2), int(hy2))
                graphics.line(int(vx1), int(vy1), int(vx2), int(vy2))
            else:
                float_vertices = self.get_vertices()
                if not float_vertices:
                    return
                points = [(int(v[0]), int(v[1])) for v in float_vertices]
                if len(points) > 1:
                    for i in range(len(points)):
                        x1, y1 = points[i]
                        x2, y2 = points[(i + 1) % len(points)]
                        graphics.line(x1, y1, x2, y2)
                elif len(points) == 1:
                    graphics.pixel(points[0][0], points[0][1])

    # --- Initialize shapes ---
    shapes = []
    for _ in range(MIN_EACH_TYPE):
        for shape_type in SHAPE_TYPES:
            if len(shapes) < MAX_SHAPES:
                shapes.append(Shape(shape_type=shape_type))
    num_remaining = INITIAL_SHAPES - len(shapes)
    num_remaining = min(num_remaining, MAX_SHAPES - len(shapes))
    for _ in range(max(0, num_remaining)):
        shapes.append(Shape())
    
    # Pre-allocate black pen for clearing
    black_pen = graphics.create_pen(0, 0, 0)

    t = 0

    while not interrupt_event.is_set():
        if len(shapes) < MIN_SHAPES:
            num_to_add = random.randint(1, MIN_SHAPES - len(shapes) + 1)
            num_to_add = min(num_to_add, MAX_SHAPES - len(shapes))
            for _ in range(num_to_add):
                shapes.append(Shape())

        for shape in shapes:
            shape.update()

        num_shapes = len(shapes)
        for i in range(num_shapes):
            s1 = shapes[i]
            for j in range(i + 1, num_shapes):
                s2 = shapes[j]
                dx = s2.x - s1.x
                dy = s2.y - s1.y
                dist_sq = dx*dx + dy*dy
                min_dist = s1.radius + s2.radius
                min_dist_sq = min_dist * min_dist
                if dist_sq < min_dist_sq and dist_sq > 1e-4:
                    rel_vx = s2.vx - s1.vx
                    rel_vy = s2.vy - s1.vy
                    dot_product = rel_vx * dx + rel_vy * dy
                    if dot_product < 0:
                        dist = math.sqrt(dist_sq)
                        overlap = (min_dist - dist) * 0.51
                        nudge_x = (dx / dist) * overlap
                        nudge_y = (dy / dist) * overlap
                        s1.x -= nudge_x
                        s1.y -= nudge_y
                        s2.x += nudge_x
                        s2.y += nudge_y
                        s1.vx, s1.vy, s2.vx, s2.vy = s2.vx, s2.vy, s1.vx, s1.vy
                        s1.vx *= COLLISION_ELASTICITY
                        s1.vy *= COLLISION_ELASTICITY
                        s2.vx *= COLLISION_ELASTICITY
                        s2.vy *= COLLISION_ELASTICITY

        graphics.set_pen(black_pen)
        graphics.clear()
        for shape in shapes:
            shape.draw(t)
        t += 0.05
        gu.update(graphics)
        await uasyncio.sleep(0.015)
