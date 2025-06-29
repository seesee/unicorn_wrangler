import uasyncio
import machine

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

def draw_startup_grid(graphics, gu, wifi_status, ntp_status, mqtt_status, streaming_status):
    WIDTH, HEIGHT = graphics.get_bounds()

    def get_colour(status):
        if status == "on":
            return (0, 255, 0)
        elif status == "fail":
            return (255, 0, 0)
        elif status == "connecting":
            return (255, 255, 0)
        else:
            return (0, 0, 255)

    grid_w, grid_h = 5, 5
    x0 = (WIDTH - grid_w) // 2
    y0 = (HEIGHT - grid_h) // 2

    quadrants = {
        "wifi":      [(0, 0), (1, 0), (0, 1), (1, 1)],
        "ntp":       [(3, 0), (4, 0), (3, 1), (4, 1)],
        "mqtt":      [(0, 3), (1, 3), (0, 4), (1, 4)],
        "streaming": [(3, 3), (4, 3), (3, 4), (4, 4)],
    }
    status_map = {
        "wifi": wifi_status,
        "ntp": ntp_status,
        "mqtt": mqtt_status,
        "streaming": streaming_status,
    }

    for key in quadrants:
        colour = get_colour(status_map[key])
        pen = graphics.create_pen(colour[0], colour[1], colour[2])
        graphics.set_pen(pen)
        for pos in quadrants[key]:
            graphics.pixel(x0 + pos[0], y0 + pos[1])

    graphics.set_pen(graphics.create_pen(200, 200, 200))
    graphics.pixel(x0 + 2, y0 + 2)

    gu.update(graphics)

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
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    gu.update(graphics)

    wifi_status = "off"
    if config.get("wifi", "enable", False):
        draw_startup_grid(graphics, gu, "connecting", "off", "off", "off")
        await uasyncio.sleep(0.1)
        wifi_ok = await connect_wifi()
        wifi_status = "on" if wifi_ok else "fail"
    draw_startup_grid(graphics, gu, wifi_status, "off", "off", "off")
    await uasyncio.sleep(0.1)

    ntp_status = "off"
    if config.get("general", "ntp_enable", True):
        draw_startup_grid(graphics, gu, wifi_status, "connecting", "off", "off")
        await uasyncio.sleep(0.1)
        ntp_ok = set_rtc_from_ntp(config.get("general", "ntp_host", "pool.ntp.org"))
        ntp_status = "on" if ntp_ok else "fail"
    draw_startup_grid(graphics, gu, wifi_status, ntp_status, "off", "off")
    await uasyncio.sleep(0.1)

    mqtt_service = None
    mqtt_status = "off"
    if config.get("mqtt", "enable", False):
        draw_startup_grid(graphics, gu, wifi_status, ntp_status, "connecting", "off")
        await uasyncio.sleep(0.1)
        mqtt_service = MQTTService()
        state.mqtt_service = mqtt_service
        mqtt_status = "connecting"
    draw_startup_grid(graphics, gu, wifi_status, ntp_status, mqtt_status, "off")
    await uasyncio.sleep(0.1)

    streaming_status = "on" if config.get("streaming", "enable", False) else "off"
    draw_startup_grid(graphics, gu, wifi_status, ntp_status, mqtt_status, streaming_status)
    await uasyncio.sleep(0.1)

    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    gu.update(graphics)

    # button monitoring task
    uasyncio.create_task(button_monitor())

    # debug mode task (regularly print state to serial)
    if config.get("general", "debug", False):
        uasyncio.create_task(debug_monitor())

    # handle mqtt messages task
    if mqtt_service:
        uasyncio.create_task(mqtt_service.loop())

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