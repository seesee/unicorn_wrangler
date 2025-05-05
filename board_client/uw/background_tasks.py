import gc
import uasyncio

from uw.hardware import gu
from uw.state import state
from uw.logger import log

async def button_monitor():
    # hardware button actions (placeholder)
    debounce_ms = 300
    while True:
        if gu.is_pressed(gu.SWITCH_A):
            log("Boop!", "INFO")
            # reset any looping animations
            state.next_animation = None            
            state.interrupt_event.set()
            await uasyncio.sleep_ms(debounce_ms)
        elif gu.is_pressed(gu.SWITCH_B):
            state.display_on = not state.display_on
            log(f"Toggle display to {state.display_on}", "INFO")
            await uasyncio.sleep_ms(debounce_ms)
        elif gu.is_pressed(gu.SWITCH_C):
            log("Scheduling moon for destruction", "INFO")
            await uasyncio.sleep_ms(debounce_ms)
        await uasyncio.sleep(0.05)

async def debug_monitor():
    while True:
        stream_info = ""
        if state.streaming_active:
            name = getattr(state, 'stream_current_name', 'N/A')
            rendered = getattr(state, 'stream_frames_rendered', 0)
            total = getattr(state, 'stream_total_frames', 0)
            stream_info = f", Stream: {name} {rendered}/{total}"

        log(
            f"State: anim={state.animation_active}, stream={state.streaming_active}, display={state.display_on}, mem={gc.mem_free()}{stream_info}",
            "DEBUG"
        )
        await uasyncio.sleep(30)
