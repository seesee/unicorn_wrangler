import uasyncio
from uw.config import config
from uw.logger import setup_logging, log
from uw.hardware import graphics, gu, set_brightness
from uw.state import state
from uw.wifi_service import connect_wifi, wifi_monitor
from uw.animation_service import run_random_animation, run_named_animation, get_animation_list
from uw.background_tasks import button_monitor, debug_monitor
from uw.transitions import melt_off, countdown
from uw.mqtt_service import MQTTService
from uw.time_service import set_rtc_from_ntp, periodic_ntp_sync

# conveyer belt
def rotate_sequence(seq):
    item = seq.pop(0)
    seq.append(item)
    return item

# todo: refactor and handle as normal interrupt?
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
    # setup logging, default brightness and hardware
    setup_logging(config.get("general", "debug", False))
    set_brightness(config.get("general", "brightness", 0.75))
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    gu.update(graphics)

    # explicitly wait for wifi before starting anything else
    if config.get("wifi", "enable", False):
        log("Attempting initial WiFi connection and NTP sync...", "INFO")
        await connect_wifi()
        uasyncio.create_task(wifi_monitor())
        if config.get("general", "ntp_enable", True):
            set_rtc_from_ntp(config.get("general", "ntp_host", "pool.ntp.org"))
            uasyncio.create_task(periodic_ntp_sync(config.get("general", "ntp_periodic_update_hours", 12)))
    else:
        log("WiFi disabled.", "INFO")

    # button monitoring task
    uasyncio.create_task(button_monitor())

    # debug mode task (regularly print state to serial)
    if config.get("general", "debug", False):
        uasyncio.create_task(debug_monitor())

    # handle mqtt messages task
    if config.get("mqtt", "enable", False):
        mqtt_service = MQTTService()
        state.mqtt_service = mqtt_service
        uasyncio.create_task(mqtt_service.loop())

    # set animation sequence
    sequence = list(config.get("general", "sequence", ["streaming", "*"]))
    animation_list = get_animation_list()

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

        # job sequence is an oraboros
        job = rotate_sequence(sequence)

        if job == "*" or job == "animation":
            await run_random_animation(config.get("general", "max_runtime_s", 120))
        elif job in animation_list:
            await run_named_animation(job, config.get("general", "max_runtime_s", 120))
        else:
            log(f"Unknown sequence job: {job}", "WARN")

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
        import machine
        machine.reset()

