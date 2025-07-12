import uasyncio
import machine

from uw.config import config
from uw.logger import setup_logging, log
from uw.hardware import graphics, gu, set_brightness
from uw.state import state
from uw.animation_service import run_random_animation, run_named_animation, get_animation_list
from uw.background_tasks import button_monitor, debug_monitor
from uw.transitions import melt_off, countdown
from uw.service_manager import initialise_services

# conveyer belt
def rotate_sequence(seq):
    item = seq.pop(0)
    seq.append(item)
    return item

async def handle_text_interrupt():
    if state.interrupt_event.is_set():
        state.interrupt_event.clear()
        if state.text_message:
            from animations.text_scroller import run as run_text_scroller
            await run_text_scroller(
                graphics, gu, state, state.interrupt_event,
                state.text_message, state.text_repeat_count
            )
            state.text_message = None
            return True
    return False

async def main():
    setup_logging(config.get("general", "debug", False))
    set_brightness(config.get("general", "brightness", 0.75))

    await initialise_services()

    # button monitoring task
    uasyncio.create_task(button_monitor())

    # debug mode task (regularly print state to serial)
    if config.get("general", "debug", False):
        uasyncio.create_task(debug_monitor())

    # set animation sequence
    sequence = list(config.get("general", "sequence", ["streaming", "*"]))
    animation_list = get_animation_list()
    state.max_iterations = config.get("general", "max_iterations", -1)

    # main loop
    while True:
        if not state.display_on:
            await melt_off()
            while not state.display_on:
                await uasyncio.sleep(0.2)
            await countdown()

        # publish mqtt text message here (and later -- todo: probably refactor as above)
        if await handle_text_interrupt():
            continue

        if state.max_iterations != 0:
            # job sequence is an oraboros
            job = rotate_sequence(sequence)

            if state.max_iterations > 0 and state.next_animation != "onair":
                # onair can loop indefinitely; only count non-onair iterations
                state.max_iterations -= 1

            if job == "*" or job == "animation":
                await run_random_animation(config.get("general", "max_runtime_s", 120))
            elif job in animation_list:
                await run_named_animation(job, config.get("general", "max_runtime_s", 120))
            else:
                log(f"Unknown sequence job: {job}", "WARN")
        else:
            # Support maximum iteration limit to work around Pico 1 memory fragmentation
            log(f"Maximum iterations reached, resetting", "INFO")
            machine.reset()

        if await handle_text_interrupt():
            continue


if __name__ == "__main__":
    try:
        uasyncio.run(main())
    except Exception as e:
        log(f"Fatal error: {e}", "ERROR")
        # try to clear the display on crash
        try:
            graphics.set_pen(graphics.create_pen(255, 0, 0))
            graphics.clear()
            gu.update(graphics)
        except Exception:
            pass
        # try to reset/restart device 
        machine.reset()
