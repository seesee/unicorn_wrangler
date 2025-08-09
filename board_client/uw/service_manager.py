import uasyncio
from uw.config import config
from uw.logger import log
from uw.hardware import graphics, gu
from uw.state import state
from uw.wifi_service import connect_wifi
from uw.time_service import set_rtc_from_ntp, periodic_ntp_sync
from uw.mqtt_service import MQTTService
import time

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

# Track startup phase to prevent grid updates during normal operation
startup_complete = False
mqtt_connection_attempted = False

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
    global startup_complete
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
                # Only update grid during startup phase
                if not startup_complete:
                    draw_startup_grid()
                break
            else:
                log(f"{service_name} connection failed. Retrying in {retry_interval}s.", "WARN")
                await uasyncio.sleep(retry_interval)
        except Exception as e:
            log(f"{service_name} connection failed: {e}. Retrying in {retry_interval}s.", "WARN")
            await uasyncio.sleep(retry_interval)

async def initialise_services():
    global startup_complete
    startup_complete = False
    start_time = time.ticks_ms()
    
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
    await uasyncio.sleep_ms(300)  # Brief initial display

    # --- WiFi with timeout ---
    wifi_success = False
    if config.get("wifi", "enable", False):
        service_status["wifi"] = STATUS_CONNECTING
        draw_startup_grid()
        
        try:
            # Give WiFi maximum 1.5 seconds during startup
            wifi_task = uasyncio.create_task(connect_wifi())
            wifi_success = await uasyncio.wait_for(wifi_task, 1.5)
            service_status["wifi"] = STATUS_ON
            state.wifi_connected = True
            log("WiFi connected during startup phase", "INFO")
        except uasyncio.TimeoutError:
            log("WiFi connection timeout during startup, moving to background", "INFO")
            service_status["wifi"] = STATUS_FAIL
            # Start background WiFi connection
            uasyncio.create_task(_background_wifi_connect())
        except Exception as e:
            log(f"WiFi connection failed during startup: {e}", "ERROR")
            service_status["wifi"] = STATUS_FAIL
            uasyncio.create_task(_background_wifi_connect())
            
        draw_startup_grid()
        await uasyncio.sleep_ms(200)  # Show WiFi result

    # --- Quick service attempts during startup phase ---
    services_to_start = []
    
    # Start all enabled services with startup attempts
    if config.get("general", "ntp_enable", True):
        services_to_start.append(_startup_ntp_sync())
    
    if config.get("mqtt", "enable", False):
        services_to_start.append(_startup_mqtt_connect())
    
    if config.get("streaming", "enable", False):
        services_to_start.append(_startup_streaming_connect())
    
    # Run all service startup attempts concurrently
    if services_to_start:
        await uasyncio.gather(*services_to_start, return_exceptions=True)
        draw_startup_grid()

    # Show final startup grid for remaining time
    elapsed = time.ticks_diff(time.ticks_ms(), start_time)
    remaining = max(0, 3000 - elapsed)
    if remaining > 0:
        await uasyncio.sleep_ms(remaining)
    
    startup_complete = True
    
    # Clear the screen and proceed to animations
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    gu.update(graphics)

async def _background_wifi_connect():
    """Background WiFi connection with retries"""
    while not state.wifi_connected:
        try:
            if await connect_wifi():
                service_status["wifi"] = STATUS_ON
                state.wifi_connected = True
                log("WiFi connected in background", "INFO")
                break
        except Exception as e:
            log(f"Background WiFi connection failed: {e}", "WARN")
            
        service_status["wifi"] = STATUS_FAIL
        await uasyncio.sleep(45)  # Retry every 45 seconds

async def _startup_ntp_sync():
    """NTP sync attempt during startup phase"""
    if not state.wifi_connected:
        service_status["ntp"] = STATUS_OFF
        return
    
    service_status["ntp"] = STATUS_CONNECTING
    draw_startup_grid()
    
    # Small delay to let network stack settle after WiFi connection
    await uasyncio.sleep_ms(200)
    
    try:
        if set_rtc_from_ntp(config.get("general", "ntp_host", "pool.ntp.org")):
            service_status["ntp"] = STATUS_ON
            uasyncio.create_task(periodic_ntp_sync())
            log("NTP sync successful during startup", "INFO")
        else:
            service_status["ntp"] = STATUS_FAIL
            log("NTP sync failed during startup", "WARN")
            # Start background retry
            uasyncio.create_task(_background_ntp_sync())
    except Exception as e:
        service_status["ntp"] = STATUS_FAIL
        log(f"NTP sync error during startup: {e}", "WARN")
        uasyncio.create_task(_background_ntp_sync())

async def _background_ntp_sync():
    """Background NTP sync - waits for WiFi"""
    # Wait for WiFi connection
    while not state.wifi_connected:
        await uasyncio.sleep(1)
    
    # Retry NTP sync
    async def ntp_retry_wrapper():
        host = config.get("general", "ntp_host", "pool.ntp.org")
        return set_rtc_from_ntp(host)
    
    uasyncio.create_task(_retry_service("ntp", ntp_retry_wrapper))

async def _startup_mqtt_connect():
    """MQTT connection attempt during startup phase"""
    global mqtt_connection_attempted
    
    if not state.wifi_connected:
        service_status["mqtt"] = STATUS_OFF
        return
    
    # Only attempt MQTT connection once, ever
    if mqtt_connection_attempted:
        return
        
    service_status["mqtt"] = STATUS_CONNECTING
    draw_startup_grid()
    
    try:
        # Set flag only after we actually attempt the connection
        mqtt_connection_attempted = True
        mqtt_service = MQTTService()
        state.mqtt_service = mqtt_service
        
        # Start the MQTT service loop in background
        uasyncio.create_task(mqtt_service.loop())
        
        # Give it a shorter time during startup to show status quickly
        connected = False
        for _ in range(10):  # 1 second maximum during startup
            if mqtt_service.connected:
                connected = True
                break
            await uasyncio.sleep_ms(100)
        
        if connected:
            service_status["mqtt"] = STATUS_ON
            log("MQTT connected during startup - no further reconnection attempts", "INFO")
        else:
            service_status["mqtt"] = STATUS_CONNECTING  # Still trying in background
            log("MQTT still connecting in background", "INFO")
            # Continue trying in background
            uasyncio.create_task(_background_mqtt_finish())
            
    except Exception as e:
        log(f"MQTT setup failed during startup: {e}", "ERROR")
        service_status["mqtt"] = STATUS_FAIL
        state.mqtt_service = None

async def _background_mqtt_finish():
    """Finish MQTT connection attempt in background"""
    if not state.mqtt_service:
        return
        
    # Continue monitoring for connection for a bit longer
    connected = False
    for _ in range(20):  # Another 2 seconds in background
        if state.mqtt_service.connected:
            connected = True
            break
        await uasyncio.sleep_ms(100)
    
    if connected:
        service_status["mqtt"] = STATUS_ON
        log("MQTT connected in background - no further reconnection attempts", "INFO")
    else:
        service_status["mqtt"] = STATUS_FAIL
        log("MQTT connection failed - will not retry to avoid blocking", "WARN")
        state.mqtt_service = None

async def _background_mqtt_connect():
    """Legacy function - now handled by startup flow"""
    pass

async def _startup_streaming_connect():
    """Streaming connection check during startup phase"""
    if not state.wifi_connected:
        service_status["streaming"] = STATUS_OFF
        return
    
    host = config.get("streaming", "host", "127.0.0.1")
    port = config.get("streaming", "port", 8000)
    
    service_status["streaming"] = STATUS_CONNECTING
    draw_startup_grid()
    
    # Small delay to let network stack settle after WiFi connection
    await uasyncio.sleep_ms(100)
    
    try:
        # Slightly longer timeout to avoid race conditions
        reader, writer = await uasyncio.wait_for(
            uasyncio.open_connection(host, port), 1.2
        )
        writer.close()
        await writer.wait_closed()
        service_status["streaming"] = STATUS_ON
        log("Streaming server connected during startup", "INFO")
    except (OSError, uasyncio.TimeoutError) as e:
        service_status["streaming"] = STATUS_FAIL
        log(f"Streaming server not available during startup: {e}", "WARN")
        
        # Start background retry
        uasyncio.create_task(_background_streaming_connect())

async def _background_streaming_connect():
    """Background streaming connection check"""
    host = config.get("streaming", "host", "127.0.0.1")
    port = config.get("streaming", "port", 8000)
        
    # Retry streaming connection
    async def check_streaming():
        try:
            reader, writer = await uasyncio.wait_for(
                uasyncio.open_connection(host, port), 2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, uasyncio.TimeoutError):
            return False
    
    uasyncio.create_task(_retry_service("streaming", check_streaming))

