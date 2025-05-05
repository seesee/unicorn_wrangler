import uasyncio
import random

async def run(graphics, gu, state, interrupt_event):
    # take the rgb pill, neo
    WIDTH, HEIGHT = graphics.get_bounds()
    num_cols = WIDTH

    # colour families: (name, main, trail, dark_bg)
    COLOUR_FAMILIES = {
        "green": {
            "main": (150, 255, 150),
            "trail": (0, 100, 0),
            "bg": (0, 20, 0)
        },
        "red": {
            "main": (255, 80, 80),
            "trail": (100, 0, 0),
            "bg": (20, 0, 0)
        },
        "blue": {
            "main": (80, 180, 255),
            "trail": (0, 0, 100),
            "bg": (0, 0, 20)
        }
    }
    COLOUR_NAMES = list(COLOUR_FAMILIES.keys())

    # decide mode this iteration
    mode_roll = random.random()
    if mode_roll < 0.6:
        # 60%: matching colour
        rain_colour = random.choice(COLOUR_NAMES)
        bg_colour = rain_colour
        mode = "mono"
    elif mode_roll < 0.9:
        # 30%: clashing colour
        rain_colour = random.choice(COLOUR_NAMES)
        bg_colour = random.choice([c for c in COLOUR_NAMES if c != rain_colour])
        mode = "clash"
    else:
        # 10%: multicolour rain, random dark bg
        rain_colour = None
        bg_colour = random.choice(COLOUR_NAMES)
        mode = "multi"

    # set background pen
    bg_rgb = COLOUR_FAMILIES[bg_colour]["bg"]
    bg_pen = graphics.create_pen(*bg_rgb)

    # assign a rain colour
    col_colours = []
    for _ in range(num_cols):
        if mode == "multi":
            col_colour = random.choice(COLOUR_NAMES)
        else:
            col_colour = rain_colour
        col_colours.append(col_colour)

    # each column: [y position, speed, digit, colour_name]
    cols = []
    for x in range(num_cols):
        cols.append([
            random.randint(-HEIGHT*2, 0),  # y position (negative = above screen)
            random.uniform(0.2, 0.7),      # falling speed
            random.randint(0, 15),         # digit value (hex 0-F)
            col_colours[x]
        ])

    while not interrupt_event.is_set():
        graphics.set_pen(bg_pen)
        graphics.clear()

        for x, col in enumerate(cols):
            col[0] += col[1]
            if col[0] > HEIGHT + 5:
                col[0] = random.randint(-HEIGHT, -5)
                col[1] = random.uniform(0.2, 0.7)
                # keep the same colour for this column for the whole animation

            y_pos = int(col[0])
            colour_name = col[3]
            colour_info = COLOUR_FAMILIES[colour_name]
            if 0 <= y_pos < HEIGHT:
                if random.random() < 0.1:
                    col[2] = random.randint(0, 15)
                # main rain drop
                graphics.set_pen(graphics.create_pen(*colour_info["main"]))
                graphics.pixel(x, y_pos)
                # draw trail
                for trail in range(1, 5):
                    trail_y = y_pos - trail
                    if 0 <= trail_y < HEIGHT:
                        fade = (5 - trail) / 5
                        trail_rgb = tuple(int(c * fade) for c in colour_info["trail"])
                        graphics.set_pen(graphics.create_pen(*trail_rgb))
                        graphics.pixel(x, trail_y)

        gu.update(graphics)
        await uasyncio.sleep(0.07)
