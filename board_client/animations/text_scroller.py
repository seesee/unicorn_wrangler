import uasyncio
import math
import time

from animations.utils import hsv_to_rgb

# custom scrolling text animation, called from mqtt message

async def run(graphics, gu, state, interrupt_event, message, repeat_count=3):
    # scroll text across screen 
    WIDTH, HEIGHT = graphics.get_bounds()
    TEXT_COLOR_CYCLE_SPEED = 0.02
    SCROLL_SPEED = 1  # pixels per frame
    REPEAT_DELAY = 5  # num seconds between repeat_count

    graphics.set_font("bitmap8")
    text_width = graphics.measure_text(message, 1)
    scroll_pos = WIDTH
    hue_offset = 0
    repetitions_completed = 0
    waiting = False
    wait_start_time = 0

    while not interrupt_event.is_set():
        if waiting:
            if time.time() - wait_start_time >= REPEAT_DELAY:
                waiting = False
                scroll_pos = WIDTH
            else:
                graphics.set_pen(graphics.create_pen(0, 0, 0))
                graphics.clear()
                gu.update(graphics)
                await uasyncio.sleep(0.1)
                continue

        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        scroll_pos -= SCROLL_SPEED

        if scroll_pos < -text_width:
            repetitions_completed += 1
            if repetitions_completed >= repeat_count:
                break
            else:
                waiting = True
                wait_start_time = time.time()
                continue

        hue_offset += TEXT_COLOR_CYCLE_SPEED

        for i, char in enumerate(message):
            char_width = graphics.measure_text(char, 1)
            char_x = scroll_pos + graphics.measure_text(message[:i], 1)
            if char_x + char_width < 0 or char_x >= WIDTH:
                continue
            hue = (hue_offset + i * 0.05) % 1.0
            r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
            graphics.set_pen(graphics.create_pen(r, g, b))
            graphics.text(char, char_x, (HEIGHT - 8) // 2, -1, 1)

        gu.update(graphics)
        await uasyncio.sleep(0.03)
