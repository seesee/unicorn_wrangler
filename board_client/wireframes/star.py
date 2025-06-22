# 3D Star wireframe data
# Eight-pointed star (stellated octahedron)

SCALE_FACTOR = 0.5

SCALE = 60
INNER_SCALE = 25

VERTICES = [
    # Outer star points (8 points)
    (SCALE, 0, 0),      # 0: +X
    (-SCALE, 0, 0),     # 1: -X
    (0, SCALE, 0),      # 2: +Y  
    (0, -SCALE, 0),     # 3: -Y
    (0, 0, SCALE),      # 4: +Z
    (0, 0, -SCALE),     # 5: -Z
    
    # Inner vertices (cube corners scaled down)
    (INNER_SCALE, INNER_SCALE, INNER_SCALE),     # 6
    (-INNER_SCALE, INNER_SCALE, INNER_SCALE),    # 7
    (INNER_SCALE, -INNER_SCALE, INNER_SCALE),    # 8
    (-INNER_SCALE, -INNER_SCALE, INNER_SCALE),   # 9
    (INNER_SCALE, INNER_SCALE, -INNER_SCALE),    # 10
    (-INNER_SCALE, INNER_SCALE, -INNER_SCALE),   # 11
    (INNER_SCALE, -INNER_SCALE, -INNER_SCALE),   # 12
    (-INNER_SCALE, -INNER_SCALE, -INNER_SCALE),  # 13
    
    # Mid-points for more complex geometry
    (INNER_SCALE, 0, 0),    # 14: +X inner
    (-INNER_SCALE, 0, 0),   # 15: -X inner
    (0, INNER_SCALE, 0),    # 16: +Y inner
    (0, -INNER_SCALE, 0),   # 17: -Y inner
    (0, 0, INNER_SCALE),    # 18: +Z inner
    (0, 0, -INNER_SCALE),   # 19: -Z inner
]

EDGES = [
    # Outer star points to inner core
    (0, 14, 0, 1), (0, 6, 0, 2), (0, 8, 0, 3), (0, 10, 0, 4), (0, 12, 0, 5),
    (1, 15, 1, 6), (1, 7, 1, 7), (1, 9, 1, 8), (1, 11, 1, 9), (1, 13, 1, 10),
    (2, 16, 2, 11), (2, 6, 2, 12), (2, 7, 2, 13), (2, 10, 2, 14), (2, 11, 2, 15),
    (3, 17, 3, 16), (3, 8, 3, 17), (3, 9, 3, 18), (3, 12, 3, 19), (3, 13, 3, 0),
    (4, 18, 4, 1), (4, 6, 4, 2), (4, 7, 4, 3), (4, 8, 4, 4), (4, 9, 4, 5),
    (5, 19, 5, 6), (5, 10, 5, 7), (5, 11, 5, 8), (5, 12, 5, 9), (5, 13, 5, 10),
    
    # Inner cube structure
    (6, 7, 6, 7), (7, 9, 7, 8), (9, 8, 8, 9), (8, 6, 9, 6),     # Top face
    (10, 11, 10, 11), (11, 13, 11, 12), (13, 12, 12, 13), (12, 10, 13, 10), # Bottom face
    (6, 10, 6, 14), (7, 11, 7, 15), (8, 12, 8, 16), (9, 13, 9, 17),         # Vertical edges
    
    # Inner connection points
    (14, 16, 14, 16), (16, 15, 15, 16), (15, 17, 15, 17), (17, 14, 17, 14), # Mid ring
    (18, 14, 18, 14), (18, 16, 18, 16), (18, 15, 18, 15), (18, 17, 18, 17), # Front connections
    (19, 14, 19, 14), (19, 16, 19, 16), (19, 15, 19, 15), (19, 17, 19, 17), # Back connections
    (18, 19, 18, 19) # Through center
]

FACES = [
    # Star point faces (8 pyramidal faces)
    (1, 0, 0),    # +X point
    (-1, 0, 0),   # -X point  
    (0, 1, 0),    # +Y point
    (0, -1, 0),   # -Y point
    (0, 0, 1),    # +Z point
    (0, 0, -1),   # -Z point
    
    # Inner cube faces
    (0.577, 0.577, 0.577),    # Top-front-right
    (-0.577, 0.577, 0.577),   # Top-front-left
    (0.577, -0.577, 0.577),   # Bottom-front-right
    (-0.577, -0.577, 0.577),  # Bottom-front-left
    (0.577, 0.577, -0.577),   # Top-back-right
    (-0.577, 0.577, -0.577),  # Top-back-left
    (0.577, -0.577, -0.577),  # Bottom-back-right
    (-0.577, -0.577, -0.577), # Bottom-back-left
    
    # Intermediate faces
    (0.707, 0.707, 0),        # Top-right edge
    (-0.707, 0.707, 0),       # Top-left edge
    (0.707, -0.707, 0),       # Bottom-right edge
    (-0.707, -0.707, 0),      # Bottom-left edge
    (0.707, 0, 0.707),        # Front-right edge
    (-0.707, 0, 0.707),       # Front-left edge
    (0.707, 0, -0.707),       # Back-right edge
    (-0.707, 0, -0.707)       # Back-left edge
]
