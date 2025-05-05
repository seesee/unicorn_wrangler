import uasyncio
import utime
import random
import math
import sys

from animations.utils import hsv_to_rgb
from uw.hardware import MODEL, WIDTH, HEIGHT
from uw.logger import log

# --- CONFIGURABLE CONSTANTS ---
RAINBOW_POWERUP_DURATION = 10.0  # seconds
RAINBOW_ATTRACT_RADIUS = 3       # blocks
RANDOM_TURN_INTERVAL = 5         # steps between random turns when hunting

def shuffle(lst):
    for i in range(len(lst) - 1, 0, -1):
        j = int(random.uniform(0, i + 1))
        lst[i], lst[j] = lst[j], lst[i]

def toroidal_distance(a, b):
    dx = min(abs(a[0] - b[0]), WIDTH - abs(a[0] - b[0]))
    dy = min(abs(a[1] - b[1]), HEIGHT - abs(a[1] - b[1]))
    return max(dx, dy)

async def shrivel_and_pulse_loser(graphics, gu, winner_snake, loser_snake, t, duration=1.5):
    steps = max(3, len(loser_snake.body))
    interval = duration / steps
    loser_body = loser_snake.body.copy()
    winner_body = winner_snake.body.copy()
    h_win, s_win, v_win = winner_snake.colour
    h_lose, s_lose, v_lose = loser_snake.colour

    for i in range(steps):
        if loser_body:
            loser_body.pop()
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        # Draw loser snake, faded
        fade = max(0.0, 1.0 - i / steps)
        for j, (x, y) in enumerate(loser_body):
            r, g, b = hsv_to_rgb(h_lose, s_lose, v_lose * fade * 0.5)
            graphics.set_pen(graphics.create_pen(r, g, b))
            graphics.pixel(x, y)
        # Draw winner snake, pulsing
        pulse = 0.7 + 0.3 * math.sin(t * 6 + i)
        for j, (x, y) in enumerate(winner_body):
            if winner_snake.is_powered() and j >= 2:
                hue = (t * 0.5 + j / max(1, len(winner_body))) % 1.0
                r, g, b = hsv_to_rgb(hue, 1.0, pulse)
            else:
                fade_win = 1.0 - (j / max(1, len(winner_body)))
                r, g, b = hsv_to_rgb(h_win, s_win, v_win * fade_win * pulse)
            graphics.set_pen(graphics.create_pen(r, g, b))
            graphics.pixel(x, y)
        gu.update(graphics)
        t += interval
        await uasyncio.sleep(interval)

async def run(graphics, gu, state, interrupt_event):
    SNAKE_COLOURS = [
        (0.58, 0.9, 1.0),  # blue (was green)
        (0.0, 0.9, 1.0),   # red
    ]
    FOOD_COLOUR = (0.13, 0.8, 1.0)  # orange
    RARE_FOOD_CHANCE = 0.08
    RARE_FOOD_GROW = 3
    NORMAL_FOOD_GROW = 1
    WIN_FILL_RATIO = 0.5

    DIRS = [(-1,0), (1,0), (0,-1), (0,1)]

    class Snake:
        def __init__(self, colour, start_pos, direction):
            self.colour = colour
            self.body = [start_pos]
            self.direction = direction
            self.grow_pending = 0
            self.alive = True
            self.vision = 2
            self.rainbow_timer = 0.0
            self.steps_since_random_turn = 0

        def head(self):
            if not self.body:
                log("head() called on empty body!", "DEBUG")
                return (None, None)
            return self.body[0]

        def is_powered(self):
            return self.rainbow_timer > 0

        def update_power(self, dt):
            if self.rainbow_timer > 0:
                self.rainbow_timer -= dt
                if self.rainbow_timer < 0:
                    self.rainbow_timer = 0

        def move(self, board, food, other_snake=None):
            if not self.alive or not self.body:
                log("move() called on dead or empty snake.", "DEBUG")
                return
            try:
                hx, hy = self.head()
                neck = self.body[1] if len(self.body) > 1 else None
                valid_moves = []
                for dx, dy in DIRS:
                    nx = (hx + dx) % WIDTH
                    ny = (hy + dy) % HEIGHT
                    if board[ny][nx] == 0 and (nx, ny) != neck:
                        valid_moves.append((dx, dy))
                if not valid_moves:
                    for dx, dy in DIRS:
                        nx = (hx + dx) % WIDTH
                        ny = (hy + dy) % HEIGHT
                        if board[ny][nx] == 0:
                            valid_moves.append((dx, dy))
                if not valid_moves:
                    log("No valid moves at all for snake. Snake dies.", "DEBUG")
                    self.alive = False
                    return
                if other_snake and other_snake.is_powered():
                    dist = toroidal_distance(self.head(), other_snake.head())
                    if dist <= RAINBOW_ATTRACT_RADIUS:
                        tx, ty = other_snake.head()
                        dx = (tx - hx + WIDTH) % WIDTH
                        dy = (ty - hy + HEIGHT) % HEIGHT
                        if dx > WIDTH // 2:
                            dx -= WIDTH
                        if dy > HEIGHT // 2:
                            dy -= HEIGHT
                        options = []
                        if dx != 0:
                            options.append((int(math.copysign(1, dx)), 0))
                        if dy != 0:
                            options.append((0, int(math.copysign(1, dy))))
                        shuffle(options)
                        for odx, ody in options:
                            if (odx, ody) in valid_moves:
                                self.direction = (odx, ody)
                                break
                        else:
                            self.direction = random.choice(valid_moves)
                        self.steps_since_random_turn = 0
                    else:
                        self._hunting_ai(valid_moves, food)
                else:
                    self._hunting_ai(valid_moves, food)
                dx, dy = self.direction
                nx = (hx + dx) % WIDTH
                ny = (hy + dy) % HEIGHT
                self.body.insert(0, (nx, ny))
                if self.grow_pending > 0:
                    self.grow_pending -= 1
                else:
                    self.body.pop()
                if self.body.count(self.head()) > 1:
                    log(f"Snake collided with itself at {self.head()}", "DEBUG")
                    self.alive = False
            except Exception as e:
                log(f"ERROR in Snake.move(): {e}", "DEBUG")
                sys.print_exception(e)
                log(f"Snake state: {self.__dict__}", "DEBUG")
                self.alive = False

        def _hunting_ai(self, valid_moves, food):
            if not self.body:
                log("_hunting_ai called on empty body!", "DEBUG")
                return
            hx, hy = self.head()
            visible_food = []
            for fx, fy, is_rare in food:
                dist = toroidal_distance((hx, hy), (fx, fy))
                if dist <= self.vision:
                    visible_food.append((fx, fy, is_rare))
            turned = False
            if visible_food:
                fx, fy, is_rare = random.choice(visible_food)
                dx = (fx - hx + WIDTH) % WIDTH
                dy = (fy - hy + HEIGHT) % HEIGHT
                if dx > WIDTH // 2:
                    dx -= WIDTH
                if dy > HEIGHT // 2:
                    dy -= HEIGHT
                options = []
                if dx != 0:
                    options.append((int(math.copysign(1, dx)), 0))
                if dy != 0:
                    options.append((0, int(math.copysign(1, dy))))
                shuffle(options)
                for odx, ody in options:
                    if (odx, ody) in valid_moves:
                        self.direction = (odx, ody)
                        turned = True
                        self.steps_since_random_turn = 0
                        break
            if not turned:
                self.steps_since_random_turn += 1
                if self.steps_since_random_turn >= RANDOM_TURN_INTERVAL:
                    if valid_moves:
                        shuffle(valid_moves)
                        self.direction = valid_moves[0]
                    else:
                        log("No valid moves available for snake in random turn. Snake dies.", "DEBUG")
                        self.alive = False
                    self.steps_since_random_turn = 0
                else:
                    if self.direction in valid_moves:
                        pass
                    elif valid_moves:
                        self.direction = valid_moves[0]
                    else:
                        log("No valid moves available for snake in keep-straight. Snake dies.", "DEBUG")
                        self.alive = False

        def grow(self, amount):
            self.grow_pending += amount

        def occupies(self, x, y):
            return (x, y) in self.body

        def length(self):
            return len(self.body)

    def random_empty_cell(board, snakes):
        attempts = 0
        while attempts < 100:
            x = random.randint(0, WIDTH-1)
            y = random.randint(0, HEIGHT-1)
            if board[y][x] == 0 and not any(s.occupies(x, y) for s in snakes):
                return (x, y)
            attempts += 1
        log("random_empty_cell failed after 100 attempts", "DEBUG")
        return None

    def draw_board(board, snakes, food, t):
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        for fx, fy, is_rare in food:
            if is_rare:
                hue = (t * 0.5 + fx * 0.1 + fy * 0.1) % 1.0
                r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
            else:
                r, g, b = hsv_to_rgb(*FOOD_COLOUR)
            graphics.set_pen(graphics.create_pen(r, g, b))
            graphics.pixel(fx, fy)
        for idx, snake in enumerate(snakes):
            if not snake.body:
                continue
            h, s, v = snake.colour
            for i, (x, y) in enumerate(snake.body):
                if snake.is_powered() and i >= 2:
                    hue = (t * 0.5 + i / max(1, len(snake.body))) % 1.0
                    r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
                else:
                    fade = 1.0 - (i / max(1, len(snake.body)))
                    r, g, b = hsv_to_rgb(h, s, v * fade)
                graphics.set_pen(graphics.create_pen(r, g, b))
                graphics.pixel(x, y)

    def victory_screen(winner_idx, snakes, t):
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        h, s, v = snakes[winner_idx].colour
        r, g, b = hsv_to_rgb(h, s, v)
        graphics.set_pen(graphics.create_pen(r, g, b))

        if MODEL != "galactic":
            lines = [
                "SNAKE",
                f"{winner_idx+1}",
                "WINS!"
            ]
            graphics.set_font("bitmap6") 
            font_height = 8
            total_height = len(lines) * font_height
            y0 = (HEIGHT - total_height) // 2
            for i, line in enumerate(lines):
                w = graphics.measure_text(line, 1)
                x = (WIDTH - w) // 2
                y = y0 + i * font_height
                graphics.text(line, x, y, -1, 1)
        else:
            msg = f"P{winner_idx+1} wins!"
            graphics.set_font("bitmap6")
            font_height = 6
            w = graphics.measure_text(msg, 1)
            x = (WIDTH - w) // 2
            y = (HEIGHT - font_height) // 2
            graphics.text(msg, x, y, -1, 1)

        gu.update(graphics)

    while not interrupt_event.is_set():
        board = [[0 for _ in range(WIDTH)] for _ in range(HEIGHT)]
        snakes = [
            Snake(SNAKE_COLOURS[0], (WIDTH // 4, HEIGHT // 2), (1, 0)),
            Snake(SNAKE_COLOURS[1], (3 * WIDTH // 4, HEIGHT // 2), (-1, 0)),
        ]
        food = []
        t = 0.0
        winner = None
        last_time = utime.ticks_ms()
        while not interrupt_event.is_set():
            while len(food) < 10:
                pos = random_empty_cell(board, snakes)
                if pos:
                    is_rare = random.random() < RARE_FOOD_CHANCE
                    food.append((pos[0], pos[1], is_rare))
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    board[y][x] = 0
            for idx, snake in enumerate(snakes):
                for x, y in snake.body:
                    board[y][x] = idx + 1
            current_time = utime.ticks_ms()
            dt = utime.ticks_diff(current_time, last_time) / 1000.0
            last_time = current_time
            for i, snake in enumerate(snakes):
                try:
                    if snake.alive and snake.body:
                        snake.move(board, food, other_snake=snakes[1-i])
                except Exception as e:
                    log(f"ERROR: Exception in snake {i} move: {e}", "DEBUG")
                    sys.print_exception(e)
                    log(f"Snake state: {snake.__dict__}", "DEBUG")
                    snake.alive = False
            for snake in snakes:
                try:
                    snake.update_power(dt)
                except Exception as e:
                    log(f"ERROR: Exception in update_power: {e}", "DEBUG")
                    sys.print_exception(e)
            new_food = []
            for fx, fy, is_rare in food:
                eaten = False
                for snake in snakes:
                    try:
                        if snake.head() == (fx, fy):
                            snake.grow(RARE_FOOD_GROW if is_rare else NORMAL_FOOD_GROW)
                            if snake.vision < 5:
                                snake.vision += 1
                            if is_rare:
                                snake.rainbow_timer = RAINBOW_POWERUP_DURATION
                            eaten = True
                    except Exception as e:
                        log(f"ERROR: Exception in food check: {e}", "DEBUG")
                        sys.print_exception(e)
                if not eaten:
                    new_food.append((fx, fy, is_rare))
            food = new_food

            for snake in snakes:
                try:
                    if snake.body and snake.body.count(snake.head()) > 1:
                        log("Snake self-collision detected in win logic.", "DEBUG")
                        snake.alive = False
                except Exception as e:
                    log(f"ERROR: Exception in win logic self-collision: {e}", "DEBUG")
                    sys.print_exception(e)
                    snake.alive = False

            if not snakes[0].alive and snakes[1].alive:
                winner = 1
            elif not snakes[1].alive and snakes[0].alive:
                winner = 0
            elif not snakes[0].alive and not snakes[1].alive:
                winner = random.choice([0, 1])
            elif (snakes[0].is_powered() or snakes[1].is_powered()) and snakes[0].head() == snakes[1].head():
                if snakes[0].is_powered() and not snakes[1].is_powered():
                    winner = 0
                elif snakes[1].is_powered() and not snakes[0].is_powered():
                    winner = 1
                else:
                    winner = random.choice([0, 1])
            elif (sum(s.length() for s in snakes) / (WIDTH * HEIGHT)) > WIN_FILL_RATIO:
                if snakes[0].length() > snakes[1].length():
                    winner = 0
                elif snakes[1].length() > snakes[0].length():
                    winner = 1
                else:
                    winner = random.choice([0, 1])

            draw_board(board, snakes, food, t)
            gu.update(graphics)
            t += 0.07
            await uasyncio.sleep(0.07)
            if winner is not None:
                log(f"Winner determined: Snake {winner+1}", "DEBUG")
                break
        if winner is not None:
            loser = 1 - winner
            await shrivel_and_pulse_loser(graphics, gu, snakes[winner], snakes[loser], t)
            for _ in range(30):
                victory_screen(winner, snakes, t)
                await uasyncio.sleep(0.07)
        for _ in range(10):
            graphics.set_pen(graphics.create_pen(0, 0, 0))
            graphics.clear()
            gu.update(graphics)
            await uasyncio.sleep(0.07)

