# TIE Fighter wireframe data
# Simplified ball cockpit with two square solar panels

SCALE = 40

VERTICES = [
    # Central cockpit (simplified sphere as octahedron)
    (0, SCALE//2, 0),      # 0: top
    (0, -SCALE//2, 0),     # 1: bottom
    (SCALE//2, 0, 0),      # 2: right
    (-SCALE//2, 0, 0),     # 3: left
    (0, 0, SCALE//2),      # 4: front
    (0, 0, -SCALE//2),     # 5: back
    
    # Left solar panel (taller and closer)
    (-SCALE*1.5, SCALE*1.5, SCALE),       # 6: left panel top-front
    (-SCALE*1.5, -SCALE*1.5, SCALE),      # 7: left panel bottom-front
    (-SCALE*1.5, -SCALE*1.5, -SCALE),     # 8: left panel bottom-back
    (-SCALE*1.5, SCALE*1.5, -SCALE),      # 9: left panel top-back
    
    # Right solar panel (taller and closer)
    (SCALE*1.5, SCALE*1.5, SCALE),        # 10: right panel top-front
    (SCALE*1.5, -SCALE*1.5, SCALE),       # 11: right panel bottom-front
    (SCALE*1.5, -SCALE*1.5, -SCALE),      # 12: right panel bottom-back
    (SCALE*1.5, SCALE*1.5, -SCALE),       # 13: right panel top-back
    
    # Connection struts (intermediate points)
    (-SCALE*0.8, 0, 0),                    # 14: left strut connection
    (SCALE*0.8, 0, 0),                     # 15: right strut connection
]

EDGES = [
    # Central cockpit octahedron
    (0, 2, 0, 1), (0, 3, 0, 2), (0, 4, 0, 3), (0, 5, 0, 4),     # top to sides
    (1, 2, 1, 5), (1, 3, 1, 6), (1, 4, 1, 7), (1, 5, 1, 8),     # bottom to sides
    (2, 4, 2, 9), (4, 3, 3, 9), (3, 5, 3, 10), (5, 2, 2, 10),   # side connections
    
    # Left solar panel
    (6, 7, 6, 7), (7, 8, 7, 8), (8, 9, 8, 9), (9, 6, 9, 6),     # outer edges
    (6, 8, 6, 8), (7, 9, 7, 9),                                   # cross braces
    
    # Right solar panel  
    (10, 11, 10, 11), (11, 12, 11, 12), (12, 13, 12, 13), (13, 10, 13, 10), # outer edges
    (10, 12, 10, 12), (11, 13, 11, 13),                                       # cross braces
    
    # Connection struts (cockpit to panels)
    (3, 14, 3, 14), (14, 6, 14, 6), (14, 7, 14, 7), (14, 8, 14, 8), (14, 9, 14, 9),   # left struts
    (2, 15, 2, 15), (15, 10, 15, 10), (15, 11, 15, 11), (15, 12, 15, 12), (15, 13, 15, 13), # right struts
    
    # Additional cockpit detail
    (4, 14, 4, 14), (5, 14, 5, 14),  # front/back to left strut
    (4, 15, 4, 15), (5, 15, 5, 15),  # front/back to right strut
]

FACES = [
    # Cockpit faces (octahedron)
    (0, 0, 1),    # top
    (0, 0, -1),   # bottom
    (1, 0, 0),    # right
    (-1, 0, 0),   # left
    (0, 1, 0),    # front
    (0, -1, 0),   # back
    (0.707, 0.707, 0),    # top-right
    (-0.707, 0.707, 0),   # top-left
    (0.707, -0.707, 0),   # bottom-right
    (-0.707, -0.707, 0),  # bottom-left
    (0.707, 0, 0.707),    # front-right
    (-0.707, 0, 0.707),   # front-left
    
    # Left solar panel
    (-1, 0, 0),   # left panel face
    
    # Right solar panel
    (1, 0, 0),    # right panel face
]

BACKFACE_CULLING = False
SCALE_FACTOR = 0.3
