import uasyncio
import math
import random

from animations.utils import hsv_to_rgb

class Blob:
    def __init__(self, x, y, radius, vx, vy, hue):
        self.x = x
        self.y = y
        self.radius = radius
        self.vx = vx
        self.vy = vy
        self.hue = hue
        self.group = None  # Will be set to a Group object

class Group:
    def __init__(self, blobs):
        self.blobs = set(blobs)
        for blob in blobs:
            blob.group = self

    def add_blob(self, blob):
        self.blobs.add(blob)
        blob.group = self

    def remove_blob(self, blob):
        self.blobs.remove(blob)
        blob.group = None

    def size(self):
        return len(self.blobs)

    def center(self):
        # Weighted center by radius
        total = sum(b.radius for b in self.blobs)
        if total == 0:
            return 0, 0
        x = sum(b.x * b.radius for b in self.blobs) / total
        y = sum(b.y * b.radius for b in self.blobs) / total
        return x, y

async def run(graphics, gu, state, interrupt_event):
    WIDTH, HEIGHT = graphics.get_bounds()
    base_hue = random.random()
    hue_shift = 0.001

    # Blob sizes: small, medium, large
    blob_sizes = [3, 5, 7]
    num_blobs = 7
    blobs = []
    for _ in range(num_blobs):
        radius = random.choice(blob_sizes)
        x = random.uniform(radius, WIDTH - radius)
        y = random.uniform(radius, HEIGHT - radius)
        vx = random.uniform(-0.05, 0.05)
        vy = random.uniform(-0.12, 0.12)
        hue = random.random()
        blobs.append(Blob(x, y, radius, vx, vy, hue))

    # Each blob starts in its own group
    groups = [Group([b]) for b in blobs]

    while not interrupt_event.is_set():
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()

        # --- Move blobs ---
        for blob in blobs:
            # Vertical movement dominates (rise/fall)
            blob.y += blob.vy
            blob.x += blob.vx
            # Add a little random drift
            blob.vx += random.uniform(-0.01, 0.01)
            blob.vx = max(-0.08, min(0.08, blob.vx))
            # Bounce off walls
            if blob.x < blob.radius:
                blob.x = blob.radius
                blob.vx *= -0.7
            elif blob.x > WIDTH - blob.radius:
                blob.x = WIDTH - blob.radius
                blob.vx *= -0.7
            # Bounce off top/bottom, reverse direction
            if blob.y < blob.radius:
                blob.y = blob.radius
                blob.vy = abs(blob.vy) * (0.7 + 0.3 * random.random())
            elif blob.y > HEIGHT - blob.radius:
                blob.y = HEIGHT - blob.radius
                blob.vy = -abs(blob.vy) * (0.7 + 0.3 * random.random())

        # --- Merge blobs into groups if they overlap and group size < 3 ---
        for i in range(len(blobs)):
            for j in range(i + 1, len(blobs)):
                a, b = blobs[i], blobs[j]
                if a.group is b.group:
                    continue
                dx = b.x - a.x
                dy = b.y - a.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < (a.radius + b.radius) * 0.7:
                    # Only merge if resulting group will have <= 3 blobs
                    if a.group.size() + b.group.size() <= 3:
                        # Merge groups
                        new_blobs = list(a.group.blobs | b.group.blobs)
                        new_group = Group(new_blobs)
                        # Remove old groups
                        groups = [g for g in groups if g not in (a.group, b.group)]
                        groups.append(new_group)

        # --- Split groups if too big or weakly connected ---
        for group in list(groups):
            if group.size() > 3:
                # Split off a random blob
                blob = random.choice(list(group.blobs))
                group.remove_blob(blob)
                groups.append(Group([blob]))
            elif group.size() > 1:
                # If any blob is drifting away, split it off
                cx, cy = group.center()
                for blob in list(group.blobs):
                    dx = blob.x - cx
                    dy = blob.y - cy
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist > blob.radius * 2.2:
                        group.remove_blob(blob)
                        groups.append(Group([blob]))

        # --- Repulsion: blobs in a group push each other apart, more so for big groups ---
        for group in groups:
            if group.size() > 1:
                repulsion = 0.04 * group.size()
                for a in group.blobs:
                    for b in group.blobs:
                        if a is b:
                            continue
                        dx = b.x - a.x
                        dy = b.y - a.y
                        dist_sq = dx * dx + dy * dy
                        if dist_sq < 0.01:
                            continue
                        dist = math.sqrt(dist_sq)
                        min_dist = (a.radius + b.radius) * 0.5
                        if dist < min_dist:
                            force = repulsion * (min_dist - dist) / min_dist
                            fx = (dx / dist) * force
                            fy = (dy / dist) * force
                            a.vx -= fx
                            a.vy -= fy
                            b.vx += fx
                            b.vy += fy

        # --- Draw blobs (visual merging) ---
        for y in range(HEIGHT):
            for x in range(WIDTH):
                value = 0
                max_contrib = 0
                dominant_blob = None
                # For each group, sum the "blob-ness" of its members
                for group in groups:
                    group_value = 0
                    group_max_contrib = 0
                    group_dominant_blob = None
                    for blob in group.blobs:
                        dx = x - blob.x
                        dy = y - blob.y
                        dist_sq = dx * dx + dy * dy
                        contrib = blob.radius * blob.radius / (dist_sq + 0.1)
                        group_value += contrib
                        if contrib > group_max_contrib:
                            group_max_contrib = contrib
                            group_dominant_blob = blob
                    if group_value > value:
                        value = group_value
                        max_contrib = group_max_contrib
                        dominant_blob = group_dominant_blob
                if value > 1.0 and dominant_blob is not None:
                    # Blending: core is blob's hue, edge is base hue
                    edge_blend = min(1.0, max_contrib / value)
                    hue = (dominant_blob.hue * edge_blend + base_hue * (1 - edge_blend)) % 1.0
                    sat = min(1.0, 0.7 + value * 0.05)
                    val = min(1.0, 0.6 + value * 0.1)
                    r, g, b = hsv_to_rgb(hue, sat, val)
                    graphics.set_pen(graphics.create_pen(r, g, b))
                    graphics.pixel(x, y)

        base_hue = (base_hue + hue_shift) % 1.0
        gu.update(graphics)
        await uasyncio.sleep(0.03)

