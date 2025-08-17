import uasyncio
import utime
import random
import micropython

from animations.utils import hsv_to_rgb, fast_sin, fast_cos
from uw.hardware import WIDTH, HEIGHT, MODEL
from uw.logger import log

# Pre-calculated 3x3 digit patterns (same as original)
DIGITS_3x3 = [
    ["###", "# #", "###"],  # 0
    [" # ", " # ", " # "],  # 1
    ["###", " # ", "###"],  # 2
    ["# #", " ##", "# #"],  # 3
    ["# #", "###", "  #"],  # 4
    ["###", " # ", "###"],  # 5
    [" ##", "#  ", "## "],  # 6
    ["###", "  #", "  #"],  # 7
    ["# #", "# #", "# #"],  # 8
    ["###", "#  ", "#  "],  # 9
]

class ExplosionParticle:
    """Particle for fireworks-style explosion"""
    def __init__(self, x, y, vx, vy, color, life):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.life = life
        self.age = 0
        
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.08  # Gravity
        self.vx *= 0.98  # Air resistance
        self.age += 1
        return self.age < self.life

@micropython.native
def draw_small_digit(graphics, digit, x, y, color_pen):
    if 0 <= digit <= 9:
        pattern = DIGITS_3x3[digit]
        graphics.set_pen(color_pen)
        for row in range(3):
            line = pattern[row]
            py = y + row
            if 0 <= py < HEIGHT:
                for col in range(3):
                    if line[col] == "#":
                        px = x + col
                        if 0 <= px < WIDTH:
                            graphics.pixel(px, py)

@micropython.native
def draw_countdown(graphics, value, color_pen, y=1):
    num_str = f"{value:03d}"
    total_w = 11
    start_x = (WIDTH - total_w) >> 1
    for i in range(3):
        digit = int(num_str[i])
        x_pos = start_x + (i << 2)
        draw_small_digit(graphics, digit, x_pos, y, color_pen)

async def run(graphics, gu, state, interrupt_event):
    log("Trench run animation started", "INFO")
    MAX_RUNTIME = getattr(state, "max_runtime_s", 270)  # Use actual config value, default 4.5 minutes
    # Reduce max runtime by 25% to ensure explosion is fully visible before animation ends
    MAX_RUNTIME = int(MAX_RUNTIME * 0.75)
    MIN_RUNTIME_BEFORE_DESTRUCTION = 60  # Minimum 60s before destruction sequence
    EXPLOSION_TIME_SECONDS = 17  # 15-20s for explosion sequence (17s gives good middle ground)

    SEGMENTS = 14 if MODEL == "cosmic" else 18
    SPEED = 0.25

    vanishing_x = WIDTH >> 1
    vanishing_y = 5 + ((HEIGHT - 5) >> 1)

    if (MODEL == "galactic") or (WIDTH > HEIGHT * 2):
        trench_width = 2.5  # Narrower (was 3.0)
    else:
        trench_width = 1.2  # Narrower (was 1.5)
    trench_height = 2.0  # Taller (was 1.5)
    grid_spacing = 1.2

    black_pen = graphics.create_pen(0, 0, 0)
    red_pen = graphics.create_pen(255, 0, 0)
    blue_pen = graphics.create_pen(0, 180, 255)
    white_pen = graphics.create_pen(255, 255, 255)
    explosion_orange_pen = graphics.create_pen(255, 150, 0)
    explosion_yellow_pen = graphics.create_pen(255, 220, 0)
    explosion_orange_pen = graphics.create_pen(255, 150, 0)
    explosion_yellow_pen = graphics.create_pen(255, 220, 0)

    brightness_pens = []
    edge_pens = []
    outline_pens = []
    for i in range(SEGMENTS):
        distance_factor = i / SEGMENTS
        brightness_factor = max(0.05, (1.0 - distance_factor) ** 2.5)
        brightness = max(15, min(255, int(255 * brightness_factor)))
        brightness_pens.append(graphics.create_pen(brightness, brightness, brightness))

        edge_brightness_factor = max(0.1, (1.0 - distance_factor) ** 2.0)
        edge_brightness = max(20, min(255, int(200 * edge_brightness_factor)))
        edge_pens.append(graphics.create_pen(edge_brightness, edge_brightness, edge_brightness))

        outline_brightness = max(30, min(255, int(255 * edge_brightness_factor)))
        outline_pens.append(graphics.create_pen(int(outline_brightness * 0.7),
                                               int(outline_brightness * 0.7),
                                               int(outline_brightness * 0.7)))

    towers = []
    explosion_active = False
    explosion_start = 0
    explosion_particles = []
    missiles = []
    lasers = []
    explosion_circles = []  # For expanding circle effects
    missile_hang = False
    missile_hang_time = 0.0
    missile_hang_duration = 0.5
    explosion_total_duration = 4.0

    start_time = utime.ticks_ms()
    
    # Dynamic frame rate measurement - wait 2 seconds to measure actual performance
    frame_measurement_time = 2.0  # seconds to measure frame rate
    frame_count = 0
    frame_rate_measured = False
    measured_fps = 50.0  # default assumption
    
    # Countdown will be calculated after frame rate measurement
    countdown = None
    countdown_start = None
    countdown_start_interval = None
    countdown_end_interval = None
    last_countdown_update = None
    countdown_phase_started = False
    
    # Ensure minimum runtime before destruction
    actual_runtime = max(MAX_RUNTIME, MIN_RUNTIME_BEFORE_DESTRUCTION)
    log(f"Trench run: max_runtime={MAX_RUNTIME}s, using actual_runtime={actual_runtime}s", "INFO")

    @micropython.native
    def project_flight(x, y, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=False):
        if wall_mode:
            x_rot = x * cos_roll - y * sin_roll
            y_rot = y
        else:
            x_rot = x * cos_roll - y * sin_roll
            y_rot = x * sin_roll + y * cos_roll
        y_with_altitude = y_rot - altitude
        y_pitched = y_with_altitude * cos_pitch
        z_pitched = z + y_with_altitude * sin_pitch
        z_final = max(0.1, z_pitched)
        scale = (HEIGHT * 1.1) / (z_final * trench_height)
        screen_x = vanishing_x + int((x_rot + shake_x) * scale)
        screen_y = vanishing_y - int((y_pitched + shake_y) * scale)
        return screen_x, screen_y

    current_offset = 0.0
    elapsed = 0.0

    while not interrupt_event.is_set():
        current_time = utime.ticks_ms()
        elapsed = (utime.ticks_diff(current_time, start_time)) * 0.001

        # Frame rate measurement phase
        if not frame_rate_measured:
            frame_count += 1
            if elapsed >= frame_measurement_time:
                measured_fps = frame_count / elapsed
                frame_rate_measured = True
                
                # Calculate countdown with gradual acceleration - slow start, fast finish
                total_countdown_time = actual_runtime - EXPLOSION_TIME_SECONDS
                
                # Acceleration curve: start slow (1.0s), accelerate to minimum (0.1s) at the end
                start_interval = 1.0   # Start slow for dramatic buildup
                end_interval = 0.1     # End fast for maximum tension
                acceleration_power = 2.5  # Same as used in countdown logic
                
                # Calculate exact countdown_start that will consume the available time
                # For our curve: interval = start * (1 - progress^2.5) + end * progress^2.5
                # Total time = sum of all intervals from progress 0 to 1
                # We need to find N such that sum equals total_countdown_time
                
                def calculate_total_time(N):
                    """Calculate total time for N countdown steps with acceleration curve"""
                    total = 0.0
                    for i in range(N):
                        progress = (N - i) / N  # From 1.0 at start to 0.0 at end
                        acceleration_curve = (1.0 - progress) ** acceleration_power
                        interval = start_interval * (1.0 - acceleration_curve) + end_interval * acceleration_curve
                        total += interval
                    return total
                
                # Binary search to find the right countdown_start
                low, high = 50, 999
                countdown_start = 200  # Starting guess
                for _ in range(20):  # 20 iterations should be enough for precision
                    estimated_time = calculate_total_time(countdown_start)
                    if abs(estimated_time - total_countdown_time) < 1.0:  # Within 1 second
                        break
                    elif estimated_time > total_countdown_time:
                        high = countdown_start
                        countdown_start = (low + countdown_start) // 2
                    else:
                        low = countdown_start
                        countdown_start = (countdown_start + high) // 2
                
                # Verify our countdown start makes sense
                if countdown_start < 100:
                    # Very short time - use minimum countdown but adjust intervals
                    countdown_start = 100
                    # Scale intervals to fit available time
                    average_interval = (start_interval + end_interval) / 2.0
                    scale_factor = (total_countdown_time / countdown_start) / average_interval
                    start_interval *= scale_factor
                    end_interval *= scale_factor
                    log(f"Short runtime - scaled intervals: {start_interval:.2f}s → {end_interval:.2f}s", "INFO")
                
                countdown = countdown_start
                
                # Store acceleration parameters for dynamic interval calculation
                countdown_start_interval = start_interval
                countdown_end_interval = end_interval
                last_countdown_update = current_time
                countdown_phase_started = True
                
                final_estimated_time = calculate_total_time(countdown_start)
                log(f"Frame rate: {measured_fps:.1f} FPS, countdown: {countdown_start} ({final_estimated_time:.1f}s/{total_countdown_time:.1f}s) {start_interval:.1f}s→{end_interval:.1f}s", "INFO")

        # Calculate urgency factor based on countdown progress (if countdown has started)
        if countdown_phase_started and countdown is not None and countdown_start > 0:
            urgency_factor = max(0.3, 1.0 - (countdown / countdown_start))
        else:
            urgency_factor = 0.3  # Low urgency during frame measurement phase

        # Enhanced movement for better speed sensation
        base_roll = fast_sin(elapsed * 1.8) * 0.12 + fast_sin(elapsed * 0.7) * 0.06  # Increased frequency and amplitude
        banking = fast_sin(elapsed * 1.0) * 0.25 * urgency_factor  # Increased banking
        pitch_base = fast_sin(elapsed * 1.3) * 0.18 * urgency_factor  # Enhanced pitch movement
        pitch_dodge = fast_sin(elapsed * 3.2) * 0.10 * urgency_factor  # Faster, more pronounced dodging
        
        # Special swooping descent during frame measurement phase
        if not frame_rate_measured:
            # Cinematic swoop down into trench during countdown calculation
            swoop_progress = min(1.0, elapsed / frame_measurement_time)  # 0.0 to 1.0 over 2 seconds
            # Start high above trench, swoop down smoothly
            swoop_altitude = 3.0 * (1.0 - swoop_progress * swoop_progress)  # Quadratic descent for smooth swooping
            altitude = max(0.4, swoop_altitude)  # End at normal flight altitude
            
            # Banking approach - reduce banking as we get lower to avoid clipping
            # Only bank when high above the trench, level out as we descend
            safe_banking_altitude = 1.5  # Only bank when above this altitude
            if altitude > safe_banking_altitude:
                # Banking turn during high altitude approach
                bank_intensity = (altitude - safe_banking_altitude) / (3.0 - safe_banking_altitude)  # 1.0 when highest, 0.0 at safe altitude
                bank_angle = fast_sin(swoop_progress * 3.14159) * -0.6 * bank_intensity  # Scale banking by altitude
                roll_angle = base_roll + bank_angle
            else:
                # Level flight when close to trench walls
                roll_angle = base_roll * 0.3  # Minimal rolling when low
            
            # Forward dive during swoop with leveling out
            dive_angle = swoop_progress * (1.0 - swoop_progress) * -0.5  # Slightly less aggressive dive
            pitch_angle = pitch_base + pitch_dodge + dive_angle
        else:
            # Normal flight after swoop is complete with smooth transition
            normal_roll = base_roll + banking
            normal_pitch = pitch_base + pitch_dodge
            normal_altitude_base = 0.4 + fast_sin(elapsed * 0.8) * 0.4  # More altitude variation
            normal_altitude_evasive = fast_sin(elapsed * 2.5) * 0.6 * urgency_factor  # More dramatic evasive moves
            normal_altitude = max(0.1, normal_altitude_base + abs(normal_altitude_evasive))
            
            # Smooth transition from swoop end values to normal flight
            transition_time = 1.0  # 1 second transition period
            transition_elapsed = elapsed - frame_measurement_time  # Time since swoop ended
            if transition_elapsed < transition_time:
                # Blend from swoop end state to normal flight
                blend_factor = transition_elapsed / transition_time
                blend_factor = blend_factor * blend_factor  # Ease-in transition
                
                # Values at end of swoop (what we're transitioning from)
                swoop_end_roll = base_roll * 0.3  # Last roll value from swoop
                swoop_end_pitch = pitch_base + pitch_dodge + 0  # Last pitch (dive_angle was 0 at end)
                swoop_end_altitude = 0.4  # End altitude of swoop
                
                # Blend the values
                roll_angle = swoop_end_roll * (1.0 - blend_factor) + normal_roll * blend_factor
                pitch_angle = swoop_end_pitch * (1.0 - blend_factor) + normal_pitch * blend_factor
                altitude = swoop_end_altitude * (1.0 - blend_factor) + normal_altitude * blend_factor
            else:
                # Full normal flight after transition period
                roll_angle = normal_roll
                pitch_angle = normal_pitch
                altitude = normal_altitude
        cos_roll = fast_cos(roll_angle)
        sin_roll = fast_sin(roll_angle)
        cos_pitch = fast_cos(pitch_angle)
        sin_pitch = fast_sin(pitch_angle)
        shake_intensity = 1.0 + urgency_factor * 2.5  # More intense shaking
        shake_x = fast_sin(elapsed * 4.2) * 0.08 * shake_intensity  # Faster, more pronounced shake
        shake_y = fast_sin(elapsed * 3.6) * 0.06 * shake_intensity

        graphics.set_pen(black_pen)
        graphics.clear()

        if not explosion_active:
            current_offset = (current_offset + SPEED) % grid_spacing

            # Draw floor grid lines
            for i in range(SEGMENTS):
                z = 0.5 + i * grid_spacing - (current_offset % grid_spacing)
                pen_idx = min(i, len(brightness_pens) - 1)
                px_left, py_left = project_flight(-trench_width, 0.0, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y)
                px_right, py_right = project_flight(trench_width, 0.0, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y)
                graphics.set_pen(brightness_pens[pen_idx])
                graphics.line(px_left, py_left, px_right, py_right)
                for side in [-trench_width, trench_width]:
                    if MODEL == "cosmic" and i % 2 == 1:
                        continue
                    px0, py0 = project_flight(side, 0.0, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    px1, py1 = project_flight(side, trench_height, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    graphics.set_pen(brightness_pens[pen_idx])
                    graphics.line(px0, py0, px1, py1)

            # Draw top edges of the trench
            for side in [-trench_width, trench_width]:
                prev_px, prev_py = None, None
                for i in range(SEGMENTS):
                    z = 0.5 + i * grid_spacing - (current_offset % grid_spacing)
                    px, py = project_flight(side, trench_height, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    if prev_px is not None:
                        pen_idx = min(i, len(edge_pens) - 1)
                        graphics.set_pen(edge_pens[pen_idx])
                        graphics.line(prev_px, prev_py, px, py)
                    prev_px, prev_py = px, py

            # Draw outer landscape
            outer_landscape_width = trench_width * 1.8
            for i in range(SEGMENTS):
                z = 0.5 + i * grid_spacing - (current_offset % grid_spacing)
                pen_idx = min(i, len(outline_pens) - 1)
                for side in [-1, 1]:
                    inner_x = side * trench_width
                    inner_px, inner_py = project_flight(inner_x, trench_height, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    outer_x = side * outer_landscape_width
                    outer_px, outer_py = project_flight(outer_x, trench_height, z, cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    graphics.set_pen(outline_pens[pen_idx])
                    graphics.line(inner_px, inner_py, outer_px, outer_py)

            # Tower spawning
            spawn_rate = 0.04 + urgency_factor * 0.02
            if random.random() < spawn_rate and len(towers) < 4:
                side = -trench_width if random.random() < 0.5 else trench_width
                tower = {
                    "z": 0.5 + SEGMENTS * grid_spacing,
                    "side": side,
                    "height": random.uniform(0.5, 1.0) * trench_height,
                    "hue": random.random(),
                }
                towers.append(tower)
                log(f"Tower spawned: {tower}", "DEBUG")

            # Draw towers
            for tower in towers:
                tower["z"] -= SPEED
                if tower["z"] > 0:
                    px0, py0 = project_flight(tower["side"], 0.0, tower["z"], cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    px1, py1 = project_flight(tower["side"], tower["height"], tower["z"], cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True)
                    distance_factor = tower["z"] / (SEGMENTS * grid_spacing)
                    brightness_factor = max(0.1, (1.0 - distance_factor) ** 2.0)
                    value = max(0.12, min(1.0, brightness_factor))
                    r, g, b = hsv_to_rgb(tower["hue"], 0.85, value)
                    tower_dynamic_pen = graphics.create_pen(int(r), int(g), int(b))
                    graphics.set_pen(tower_dynamic_pen)
                    graphics.line(px0, py0, px1, py1)
            towers = [t for t in towers if t["z"] > 0]

            # Missile logic - fire exactly on countdown 0
            if (not missile_hang and len(missiles) < 1 and countdown_phase_started and 
                countdown is not None and countdown == 0):
                missile = {"z": 0.5, "speed": SPEED * 1.5, "dipping": False, "dip_progress": 0.0}
                missiles.append(missile)
                log(f"Missile fired at countdown 0!", "INFO")

            for missile in missiles:
                if not missile["dipping"]:
                    missile["z"] += missile["speed"]
                    log(f"Missile z updated: {missile['z']}", "DEBUG")
                    if missile["z"] >= SEGMENTS * grid_spacing - 1.0:
                        missile["dipping"] = True
                        missile["dip_progress"] = 0.0
                        missile_hang = True
                        missile_hang_time = elapsed
                        log("Missile reached end, starting hang/dip", "DEBUG")
                else:
                    missile["dip_progress"] += 0.04
                    log(f"Missile dipping, progress: {missile['dip_progress']}", "DEBUG")

                missile_height = 0.5 - (missile["dip_progress"] * 0.6 if missile["dipping"] else 0.0)
                px, py = project_flight(0.0, missile_height,
                                        min(missile["z"], SEGMENTS * grid_spacing - 1.0),
                                        cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, 0, 0)
                graphics.set_pen(blue_pen)
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    graphics.pixel(px, py)

            if missile_hang and elapsed - missile_hang_time > missile_hang_duration:
                missiles.clear()
                missile_hang = False
                explosion_active = True
                explosion_start = utime.ticks_ms()
                
                # Create fireworks-style explosion particles
                center_x = WIDTH >> 1
                center_y = HEIGHT >> 1
                num_particles = 60  # Lots of particles for spectacular explosion
                
                # Create multi-colored bursts
                colors = [
                    (255, 255, 255),  # White core
                    (255, 220, 0),    # Yellow
                    (255, 150, 0),    # Orange  
                    (255, 50, 50),    # Red
                    (255, 100, 200),  # Pink
                ]
                
                for i in range(num_particles):
                    angle = (i / num_particles) * 6.28318  # Full circle
                    speed = random.uniform(0.8, 2.5)
                    color = random.choice(colors)
                    life = random.randint(25, 45)
                    
                    # Add some randomness to create irregular burst pattern  
                    angle += random.uniform(-0.3, 0.3)
                    
                    vx = fast_cos(angle) * speed
                    vy = fast_sin(angle) * speed
                    
                    explosion_particles.append(ExplosionParticle(
                        center_x, center_y, vx, vy, color, life
                    ))
                
                # Create expanding circles for spectacular effect
                circle_colors = [
                    (255, 255, 255),  # White
                    (255, 220, 0),    # Yellow  
                    (255, 150, 0),    # Orange
                    (255, 50, 50),    # Red
                ]
                
                for i, color in enumerate(circle_colors):
                    explosion_circles.append({
                        "start_time": utime.ticks_ms() + (i * 150),  # Stagger circle starts
                        "color": color,
                        "max_radius": 8 + i * 2,  # Different max sizes
                        "duration": 800 + i * 200,  # Different durations
                        "thickness": 1 if i < 2 else 2,  # Thicker outer circles
                    })
                
                log("Fireworks explosion with expanding circles triggered!", "INFO")

            # Laser effects
            laser_spawn_rate = 0.04 + urgency_factor * 0.02
            if random.random() < laser_spawn_rate and len(lasers) < 2 and towers:
                tower = random.choice(towers)
                
                # Add depth-based angle variation for more realistic 3D effect
                depth_factor = tower["z"] / (SEGMENTS * grid_spacing)
                
                # 40% chance for "towards viewer" shots, 60% for cross-trench shots
                if random.random() < 0.4:
                    # Shoot towards viewer (center screen, closer to camera)
                    target_side = tower["side"] * random.uniform(0.1, 0.3)  # Much closer to center
                    angle_variation = 0.8  # Large angle variation for dramatic effect
                    height_offset = random.uniform(-0.5, 0.5)  # Wide height variation
                    target_z_offset = -random.uniform(2.0, 4.0)  # Shoot towards camera
                else:
                    # Cross-trench shots (original behavior but enhanced)
                    target_side = -tower["side"]
                    angle_variation = (0.5 - depth_factor) * 0.6  # Increased angle variation
                    height_offset = random.uniform(-0.3, 0.4) * depth_factor
                    target_z_offset = 0.0
                
                laser = {
                    "source_tower": tower,
                    "target_side": target_side,
                    "z": tower["z"],
                    "target_z_offset": target_z_offset,
                    "progress": 0.0,
                    "angle_offset": random.uniform(-angle_variation, angle_variation),
                    "height_offset": height_offset,
                }
                lasers.append(laser)
                log(f"Laser spawned from tower: {tower}", "DEBUG")

            for laser in lasers:
                laser["progress"] += 0.12
                prog = min(1.0, laser["progress"])
                tower = laser["source_tower"]
                
                # Calculate start position (tower top)
                start_x, start_y = project_flight(
                    tower["side"], tower["height"], tower["z"],
                    cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True
                )
                
                # Calculate angled target position with depth-based variation
                target_x = laser["target_side"] + laser["angle_offset"]
                target_y = tower["height"] + laser["height_offset"]
                target_z = laser["z"] + laser["target_z_offset"]  # For "towards viewer" shots
                
                end_x, end_y = project_flight(
                    target_x, target_y, target_z,
                    cos_roll, sin_roll, cos_pitch, sin_pitch, altitude, shake_x, shake_y, wall_mode=True
                )
                
                curr_x = int(start_x + (end_x - start_x) * prog)
                curr_y = int(start_y + (end_y - start_y) * prog)
                tower_hue = tower["hue"]
                r, g, b = hsv_to_rgb(tower_hue, 1.0, 1.0)
                laser_pen = graphics.create_pen(int(r), int(g), int(b))
                graphics.set_pen(laser_pen)
                graphics.line(start_x, start_y, curr_x, curr_y)
            lasers = [l for l in lasers if l["progress"] < 1.0]

            # Countdown update with dynamic acceleration (only if countdown phase has started)
            if countdown_phase_started and countdown is not None and countdown > 0 and not missile_hang:
                now = utime.ticks_ms()
                
                # Calculate current countdown interval based on progress (accelerating)
                progress = 1.0 - (countdown / countdown_start)  # 0.0 at start, 1.0 at end
                # Use exponential curve for dramatic acceleration: slow start, rapid finish
                acceleration_curve = progress ** 2.5  # Exponential acceleration
                current_interval = countdown_start_interval * (1.0 - acceleration_curve) + countdown_end_interval * acceleration_curve
                
                if utime.ticks_diff(now, last_countdown_update) >= int(current_interval * 1000):
                    countdown -= 1
                    last_countdown_update = now
                    if countdown == 0:
                        log("Countdown reached 0 - missile will fire!", "INFO")
                    elif countdown % 10 == 0:  # Log every 10th countdown for debugging
                        log(f"Countdown: {countdown} (interval: {current_interval:.2f}s)", "DEBUG")

            # Only draw countdown if countdown phase has started
            if countdown_phase_started and countdown is not None:
                draw_countdown(graphics, countdown, red_pen, y=1)

        else:
            log("Explosion animation running", "DEBUG")
            explosion_time = (utime.ticks_ms() - explosion_start) * 0.001
            
            # Initial flash effect
            if explosion_time < 0.15:
                if int(explosion_time * 30) % 2 == 0:
                    graphics.set_pen(white_pen)
                else:
                    graphics.set_pen(explosion_yellow_pen)
                graphics.clear()
            else:
                graphics.set_pen(black_pen)
                graphics.clear()
                
                # Update and draw explosion particles
                i = 0
                while i < len(explosion_particles):
                    particle = explosion_particles[i]
                    if particle.update():
                        # Calculate fade based on particle age
                        fade = 1.0 - (particle.age / particle.life)
                        fade = max(0.0, fade)
                        
                        px = int(particle.x)
                        py = int(particle.y)
                        
                        if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                            r, g, b = particle.color
                            r = int(r * fade)
                            g = int(g * fade)
                            b = int(b * fade)
                            graphics.set_pen(graphics.create_pen(r, g, b))
                            graphics.pixel(px, py)
                            
                            # Add sparkle effect for some particles
                            if random.random() < 0.3 and fade > 0.5:
                                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                                    sx, sy = px + dx, py + dy
                                    if 0 <= sx < WIDTH and 0 <= sy < HEIGHT:
                                        sparkle_fade = fade * 0.4
                                        sr = int(r * sparkle_fade)
                                        sg = int(g * sparkle_fade)  
                                        sb = int(b * sparkle_fade)
                                        graphics.set_pen(graphics.create_pen(sr, sg, sb))
                                        graphics.pixel(sx, sy)
                        i += 1
                    else:
                        # Remove dead particle
                        explosion_particles[i] = explosion_particles[-1]
                        explosion_particles.pop()
                        
                # Draw expanding circles
                current_time = utime.ticks_ms()
                center_x = WIDTH >> 1
                center_y = HEIGHT >> 1
                
                i = 0
                while i < len(explosion_circles):
                    circle = explosion_circles[i]
                    if current_time >= circle["start_time"]:
                        elapsed = current_time - circle["start_time"]
                        
                        if elapsed < circle["duration"]:
                            # Calculate current radius and fade
                            progress = elapsed / circle["duration"]
                            radius = int(circle["max_radius"] * progress)
                            fade = 1.0 - progress  # Fade out as it expands
                            
                            # Draw circle with fade
                            if radius > 0 and fade > 0.1:
                                r, g, b = circle["color"]
                                r = int(r * fade)
                                g = int(g * fade)
                                b = int(b * fade)
                                circle_pen = graphics.create_pen(r, g, b)
                                graphics.set_pen(circle_pen)
                                
                                # Draw circle outline - use multiple thickness for outer circles
                                for thickness in range(circle["thickness"]):
                                    for angle_step in range(0, 360, 8):  # Draw circle in 8-degree steps
                                        angle = angle_step * 0.017453  # Convert to radians
                                        px = center_x + int((radius + thickness) * fast_cos(angle))
                                        py = center_y + int((radius + thickness) * fast_sin(angle))
                                        if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                                            graphics.pixel(px, py)
                            i += 1
                        else:
                            # Remove expired circle
                            explosion_circles[i] = explosion_circles[-1]
                            explosion_circles.pop()
                    else:
                        i += 1
                        
            # End explosion when all particles and circles are gone
            if explosion_time > 1.0 and len(explosion_particles) == 0 and len(explosion_circles) == 0:
                log("Fireworks explosion with circles complete, exiting animation", "INFO")
                return

        gu.update(graphics)
        log(f"Elapsed: {elapsed:.2f}, missile_hang: {missile_hang}, explosion_active: {explosion_active}, missiles: {len(missiles)}", "DEBUG")
        await uasyncio.sleep(0.02)

    log("Trench run animation interrupted", "INFO")
