import uasyncio
from uw.config import config
from uw.logger import log
from uw.hardware import graphics, gu
from uw.state import state
from uw.wifi_service import connect_wifi
from uw.time_service import set_rtc_from_ntp, periodic_ntp_sync
from uw.mqtt_service import MQTTService

# Service status constants
STATUS_OFF = "off"
STATUS_CONNECTING = "connecting"
STATUS_ON = "on"
STATUS_FAIL = "fail"
STATUS_ENABLED = "enabled"

# Keep track of service status
service_status = {
    "wifi": STATUS_OFF,
    "ntp": STATUS_OFF,
    "mqtt": STATUS_OFF,
    "streaming": STATUS_OFF,
}

def draw_startup_grid():
    WIDTH, HEIGHT = graphics.get_bounds()

    def get_colour(status):
        if status == STATUS_ON:
            return (0, 255, 0)  # Green
        elif status == STATUS_FAIL:
            return (255, 0, 0)  # Red
        elif status == STATUS_CONNECTING:
            return (255, 255, 0)  # Yellow
        elif status == STATUS_ENABLED:
            return (0, 0, 255)  # Blue
        else:  # off
            return (128, 128, 128)  # Grey

    grid_w, grid_h = 5, 5
    x0 = (WIDTH - grid_w) // 2
    y0 = (HEIGHT - grid_h) // 2

    quadrants = {
        "wifi":      [(0, 0), (1, 0), (0, 1), (1, 1)],
        "ntp":       [(3, 0), (4, 0), (3, 1), (4, 1)],
        "mqtt":      [(0, 3), (1, 3), (0, 4), (1, 4)],
        "streaming": [(3, 3), (4, 3), (3, 4), (4, 4)],
    }

    for key, status in service_status.items():
        colour = get_colour(status)
        pen = graphics.create_pen(colour[0], colour[1], colour[2])
        graphics.set_pen(pen)
        for pos in quadrants[key]:
            graphics.pixel(x0 + pos[0], y0 + pos[1])

    graphics.set_pen(graphics.create_pen(200, 200, 200))
    graphics.pixel(x0 + 2, y0 + 2)

    gu.update(graphics)

async def _retry_service(service_name, connect_func, *args):
    retry_interval = config.get(service_name, "retry_interval_s", 45)
    while True:
        log(f"Retrying {service_name} connection...", "INFO")
        try:
            result = await connect_func(*args)
            # Handle both True return and successful completion without exception
            if result is None or result:
                service_status[service_name] = STATUS_ON
                log(f"{service_name} connected successfully.", "INFO")
                if service_name == "ntp":
                    uasyncio.create_task(periodic_ntp_sync())
                break
            else:
                log(f"{service_name} connection failed. Retrying in {retry_interval}s.", "WARN")
                await uasyncio.sleep(retry_interval)
        except Exception as e:
            log(f"{service_name} connection failed: {e}. Retrying in {retry_interval}s.", "WARN")
            await uasyncio.sleep(retry_interval)

async def initialise_services():
    # Clear the screen initially
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()

    # Set initial status based on config
    if config.get("wifi", "enable", False):
        service_status["wifi"] = STATUS_ENABLED
    if config.get("general", "ntp_enable", True):
        service_status["ntp"] = STATUS_ENABLED
    if config.get("mqtt", "enable", False):
        service_status["mqtt"] = STATUS_ENABLED
    if config.get("streaming", "enable", False):
        service_status["streaming"] = STATUS_ENABLED
    
    draw_startup_grid()
    await uasyncio.sleep(1) # Show initial state

    # --- WiFi ---
    if config.get("wifi", "enable", False):
        service_status["wifi"] = STATUS_CONNECTING
        draw_startup_grid()
        if await connect_wifi():
            service_status["wifi"] = STATUS_ON
            state.wifi_connected = True
        else:
            service_status["wifi"] = STATUS_FAIL
            uasyncio.create_task(_retry_service("wifi", connect_wifi))
        draw_startup_grid()

    # --- NTP ---
    if config.get("general", "ntp_enable", True):
        if state.wifi_connected:
            service_status["ntp"] = STATUS_CONNECTING
            draw_startup_grid()
            if set_rtc_from_ntp(config.get("general", "ntp_host", "pool.ntp.org")):
                service_status["ntp"] = STATUS_ON
                uasyncio.create_task(periodic_ntp_sync())
            else:
                service_status["ntp"] = STATUS_FAIL

                async def ntp_retry_wrapper():
                    # This wrapper makes the synchronous function compatible
                    # with the async retry mechanism.
                    host = config.get("general", "ntp_host", "pool.ntp.org")
                    return set_rtc_from_ntp(host)

                uasyncio.create_task(_retry_service("ntp", ntp_retry_wrapper))
        else:
            service_status["ntp"] = STATUS_OFF # No wifi, so can't even try
        draw_startup_grid()

    # --- MQTT ---
    if config.get("mqtt", "enable", False):
        if state.wifi_connected:
            service_status["mqtt"] = STATUS_CONNECTING
            draw_startup_grid()
            mqtt_service = MQTTService()
            state.mqtt_service = mqtt_service
            uasyncio.create_task(mqtt_service.loop())
            
            # Wait for connection with a timeout
            connected = False
            for _ in range(15):
                if mqtt_service.connected:
                    connected = True
                    break
                await uasyncio.sleep(1)

            if connected:
                service_status["mqtt"] = STATUS_ON
            else:
                service_status["mqtt"] = STATUS_FAIL
                # MQTTService handles its own retries, so we don't use _retry_service here
        else:
            service_status["mqtt"] = STATUS_OFF
        draw_startup_grid()

    # --- Streaming ---
    if config.get("streaming", "enable", False):
        if state.wifi_connected:
            service_status["streaming"] = STATUS_CONNECTING
            draw_startup_grid()
            host = config.get("streaming", "host", "127.0.0.1")
            port = config.get("streaming", "port", 8000)
            try:
                # Simple check to see if we can open a connection
                reader, writer = await uasyncio.open_connection(host, port)
                writer.close()
                await writer.wait_closed()
                service_status["streaming"] = STATUS_ON
            except OSError:
                service_status["streaming"] = STATUS_FAIL
                # We can create a simple lambda to pass to the retry service
                async def check_streaming():
                    try:
                        reader, writer = await uasyncio.open_connection(host, port)
                        writer.close()
                        await writer.wait_closed()
                        return True
                    except OSError:
                        return False
                uasyncio.create_task(_retry_service("streaming", check_streaming))
        else:
            service_status["streaming"] = STATUS_OFF
        draw_startup_grid()

    # Short delay to show the final grid status
    await uasyncio.sleep(2)
    
    # Clear the screen and proceed to animations
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    gu.update(graphics)
