import uasyncio
import random
import gc
import sys
import os

from uw.state import state
from uw.logger import log
from uw.hardware import graphics, gu

def get_animation_list():
    files = os.listdir("animations")
    # exclude utils, text_scroller & onair
    exclude = {"utils.py", "text_scroller.py", "onair.py"}
    anims = []
    for f in files:
        if f.endswith(".py") and f not in exclude:
            anims.append(f[:-3])  # remove .py extension
    return sorted(anims)

ANIMATION_LIST = get_animation_list()

async def run_named_animation(animation_name, max_runtime_s):
    # load and run a random animation for up to max_runtime_s seconds, interruptible
    # Returns True if animation ran successfully, False if it failed to load or had an error
    state.animation_active = True
    state.interrupt_event.clear()
    
    # Set max_runtime_s on state so animations can access it (especially for --duration override)
    state.max_runtime_s = max_runtime_s

    # fixes an animation to loop indefinitely when set. Used for onair.
    if state.next_animation:
        animation_name = state.next_animation

    module_path = f"animations.{animation_name}"
    log(f"Loading animation: {animation_name}", "INFO")
    
    if state.mqtt_service and state.mqtt_service.connected:
        state.mqtt_service.publish_status({
            "animation": animation_name
        })

    try:
        # lazy load the animation module
        mod = __import__(module_path, globals(), locals(), [animation_name], 0)
        anim_func = getattr(mod, "run")
    except Exception as e:
        log(f"Failed to load animation {animation_name}: {e}", "ERROR")
        state.animation_active = False
        return False

    success = True
    task = uasyncio.create_task(anim_func(graphics, gu, state, state.interrupt_event))
    try:
        await uasyncio.wait_for(task, timeout=max_runtime_s)
    except uasyncio.TimeoutError:
        log(f"Animation {animation_name} ended after {max_runtime_s}s", "INFO", uptime=True)
    except Exception as e:
        log(f"Animation {animation_name} error: {e}", "ERROR")
        success = False
    finally:
        state.animation_active = False
        state.interrupt_event.set()
        # unload module to free memory
        if module_path in sys.modules:
            del sys.modules[module_path]
        gc.collect()
    
    return success

async def run_random_animation(max_runtime_s):
    animation_name = random.choice(ANIMATION_LIST)
    await run_named_animation(animation_name, max_runtime_s)

def interrupt_animation():
    # signal a currently-running animation to stop
    state.interrupt_event.set()
