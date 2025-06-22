# Icosahedron wireframe data
# Regular polyhedron with 20 triangular faces

import math

# Golden ratio for icosahedron construction
PHI = (1 + math.sqrt(5)) / 2
SCALE = 50

VERTICES = [
    # 12 vertices of icosahedron, scaled
    (0, SCALE, SCALE * PHI),
    (0, -SCALE, SCALE * PHI),
    (0, SCALE, -SCALE * PHI),
    (0, -SCALE, -SCALE * PHI),
    
    (SCALE, SCALE * PHI, 0),
    (-SCALE, SCALE * PHI, 0),
    (SCALE, -SCALE * PHI, 0),
    (-SCALE, -SCALE * PHI, 0),
    
    (SCALE * PHI, 0, SCALE),
    (-SCALE * PHI, 0, SCALE),
    (SCALE * PHI, 0, -SCALE),
    (-SCALE * PHI, 0, -SCALE)
]

EDGES = [
    # Top pentagon
    (0, 1, 0, 1), (0, 4, 0, 4), (0, 5, 0, 5), (0, 8, 0, 8), (0, 9, 0, 9),
    
    # Bottom pentagon  
    (3, 2, 3, 2), (3, 6, 3, 6), (3, 7, 3, 7), (3, 10, 3, 10), (3, 11, 3, 11),
    
    # Upper ring connections
    (1, 6, 1, 6), (1, 7, 1, 7), (1, 8, 1, 8), (1, 9, 1, 9),
    (4, 5, 4, 5), (4, 8, 4, 8), (4, 10, 4, 10), (4, 2, 4, 2),
    (5, 9, 5, 9), (5, 11, 5, 11), (5, 2, 5, 2),
    
    # Lower ring connections
    (6, 7, 6, 7), (6, 8, 6, 8), (6, 10, 6, 10),
    (7, 9, 7, 9), (7, 11, 7, 11),
    (8, 10, 8, 10), (9, 11, 9, 11),
    
    # Cross connections
    (2, 10, 2, 10), (2, 11, 2, 11)
]

FACES = [
    # 20 triangular faces (normals pointing outward)
    # Top cap faces
    (0.356, 0.934, 0.000), (-0.356, 0.934, 0.000), (0.000, 0.934, 0.356),
    (0.000, 0.934, -0.356), (0.577, 0.577, 0.577), (-0.577, 0.577, 0.577),
    (0.577, 0.577, -0.577), (-0.577, 0.577, -0.577),
    
    # Middle band faces
    (0.934, 0.000, 0.356), (-0.934, 0.000, 0.356), (0.934, 0.000, -0.356),
    (-0.934, 0.000, -0.356), (0.577, -0.577, 0.577), (-0.577, -0.577, 0.577),
    (0.577, -0.577, -0.577), (-0.577, -0.577, -0.577),
    
    # Bottom cap faces
    (0.356, -0.934, 0.000), (-0.356, -0.934, 0.000), (0.000, -0.934, 0.356),
    (0.000, -0.934, -0.356)
]
