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
STATUS_CONNECTED_PENDING = "connected_pending"  # Connected but waiting for final confirmation

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
mqtt_ever_connected = False  # Track if MQTT has ever connected successfully
streaming_actually_working = False  # Track if streaming animations are actually working

def mqtt_status_callback(service_name, status_key):
    """Callback function for MQTT service to update status"""
    global startup_complete, mqtt_ever_connected
    if service_name == "mqtt":
        if status_key == "connected_pending":
            service_status["mqtt"] = STATUS_CONNECTED_PENDING
            mqtt_ever_connected = True  # Mark that MQTT has connected successfully
            if not startup_complete:
                draw_startup_grid()

def mark_streaming_working():
    """Called by animations to indicate streaming is actually working"""
    global streaming_actually_working
    if not streaming_actually_working:
        streaming_actually_working = True
        service_status["streaming"] = STATUS_ON
        log("Streaming confirmed working by animation - stopping background retries", "INFO")

def draw_startup_grid():
    WIDTH, HEIGHT = graphics.get_bounds()

    def get_colour(status):
        if status == STATUS_ON:
            return (0, 255, 0)  # Green
        elif status == STATUS_FAIL:
            return (255, 0, 0)  # Red
        elif status == STATUS_CONNECTING:
            return (255, 255, 0)  # Yellow
        elif status == STATUS_CONNECTED_PENDING:
            return (0, 255, 255)  # Cyan - connected but pending final confirmation
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
    global startup_complete, streaming_actually_working
    retry_interval = config.get(service_name, "retry_interval_s", 45)
    while True:
        # For streaming service, stop retrying if streaming is actually working
        if service_name == "streaming" and streaming_actually_working:
            log("Stopping streaming service retries - streaming confirmed working by animation", "INFO")
            break
            
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

    # --- Sequential service attempts during startup phase ---
    # Order: WiFi (already done), NTP, Streaming, then MQTT last
    
    # Start NTP sync
    if config.get("general", "ntp_enable", True):
        await _startup_ntp_sync()
        draw_startup_grid()
        await uasyncio.sleep_ms(100)  # Brief delay to show status
    
    # Start streaming connection check
    if config.get("streaming", "enable", False):
        await _startup_streaming_connect()
        draw_startup_grid()
        await uasyncio.sleep_ms(100)  # Brief delay to show status
    
    # Start MQTT connection last to avoid blocking other services
    if config.get("mqtt", "enable", False):
        log("Starting MQTT connection during startup", "DEBUG")
        await _startup_mqtt_connect()
        log("MQTT startup connection completed", "DEBUG")

    # Show final startup grid with all final statuses
    log("Drawing final startup grid", "DEBUG")
    draw_startup_grid()
    
    # Show final startup grid briefly to display final statuses (including green MQTT)
    elapsed = time.ticks_diff(time.ticks_ms(), start_time)
    remaining = max(0, min(300, 3000 - elapsed))  # Cap at 300ms max to avoid long delays
    final_display_time = max(150, min(remaining, 300))  # Ensure at least 150ms to see final status
    log(f"Startup elapsed: {elapsed}ms, showing final grid for {final_display_time}ms", "DEBUG")
    await uasyncio.sleep_ms(final_display_time)
    
    log("Setting startup_complete = True", "DEBUG")
    startup_complete = True
    
    # Clear the screen and proceed to animations
    log("Clearing screen and completing startup", "DEBUG")
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    gu.update(graphics)
    log("Startup sequence completed successfully", "INFO")

async def _background_wifi_connect():
    """Background WiFi connection with retries"""
    while not state.wifi_connected:
        try:
            if await connect_wifi():
                service_status["wifi"] = STATUS_ON
                state.wifi_connected = True
                log("WiFi connected in background", "INFO")
                
                # Now that WiFi is connected, start other background services
                await _trigger_background_services()
                break
        except Exception as e:
            log(f"Background WiFi connection failed: {e}", "WARN")
            
        service_status["wifi"] = STATUS_FAIL
        await uasyncio.sleep(45)  # Retry every 45 seconds

async def _trigger_background_services():
    """Trigger background services when WiFi connects late"""
    global streaming_actually_working
    log("Triggering background services after late WiFi connection", "INFO")
    
    # Start NTP sync if enabled and not already running
    if config.get("general", "ntp_enable", True) and service_status["ntp"] != STATUS_ON:
        log("Starting background NTP sync", "INFO")
        uasyncio.create_task(_background_ntp_sync())
    
    # Start streaming check if enabled, not already running, and not confirmed working
    if (config.get("streaming", "enable", False) and 
        service_status["streaming"] != STATUS_ON and 
        not streaming_actually_working):
        log("Starting background streaming check", "INFO")
        uasyncio.create_task(_background_streaming_connect())
    
    # Start MQTT if enabled and not already attempted
    if config.get("mqtt", "enable", False) and not mqtt_connection_attempted:
        log("Starting background MQTT connection", "INFO")
        uasyncio.create_task(_background_mqtt_connect_late())

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
        
    service_status["mqtt"] = STATUS_CONNECTING
    draw_startup_grid()
    
    try:
        log("Creating MQTT service", "DEBUG")
        mqtt_connection_attempted = True
        mqtt_service = MQTTService(status_callback=mqtt_status_callback)
        state.mqtt_service = mqtt_service
        
        # Try to connect once during startup
        log("Attempting MQTT connection", "DEBUG")
        connected = mqtt_service.connect()
        log(f"MQTT connection result: {connected}", "DEBUG")
        
        if connected:
            log("MQTT connected, setting status to ON", "DEBUG")
            service_status["mqtt"] = STATUS_ON
            mqtt_ever_connected = True  # Mark that MQTT has connected successfully
            log("MQTT connected during startup", "INFO")
            # Start the MQTT service loop for message handling
            log("Starting MQTT message loop", "DEBUG")
            uasyncio.create_task(mqtt_service.loop())
            log("MQTT startup success path completed", "DEBUG")
        else:
            log("MQTT connection failed, setting status to FAIL", "DEBUG")
            service_status["mqtt"] = STATUS_FAIL
            log("MQTT failed during startup, will retry in background", "INFO")
            # Start background retry task
            service_status["mqtt"] = STATUS_CONNECTING  # Change back to connecting for background
            uasyncio.create_task(_background_mqtt_retry())
            log("MQTT failure path completed", "DEBUG")
            
    except Exception as e:
        log(f"MQTT setup failed during startup: {e}", "ERROR")
        service_status["mqtt"] = STATUS_FAIL
        # Start background retry task
        service_status["mqtt"] = STATUS_CONNECTING  # Change back to connecting for background
        uasyncio.create_task(_background_mqtt_retry())
        log("MQTT exception path completed", "DEBUG")

async def _background_mqtt_retry():
    """Background MQTT retry until first successful connection"""
    global mqtt_ever_connected
    retry_interval = 10  # Retry every 10 seconds
    
    while not mqtt_ever_connected:
        # Wait for WiFi if not connected
        if not state.wifi_connected:
            await uasyncio.sleep(1)
            continue
            
        log("Retrying MQTT connection...", "INFO")
        service_status["mqtt"] = STATUS_CONNECTING
        
        try:
            # Create new MQTT service if needed
            if not state.mqtt_service:
                mqtt_service = MQTTService(status_callback=mqtt_status_callback)
                state.mqtt_service = mqtt_service
            
            # Try to connect
            connected = state.mqtt_service.connect()
            
            if connected:
                service_status["mqtt"] = STATUS_ON
                mqtt_ever_connected = True  # Set the flag to stop retries
                log("MQTT connected successfully - no further reconnection attempts will be made", "INFO")
                # Start the MQTT service loop for message handling
                uasyncio.create_task(state.mqtt_service.loop())
                break
            else:
                service_status["mqtt"] = STATUS_FAIL
                log(f"MQTT connection failed. Retrying in {retry_interval}s.", "WARN")
                await uasyncio.sleep(retry_interval)
                
        except Exception as e:
            service_status["mqtt"] = STATUS_FAIL
            log(f"MQTT connection error: {e}. Retrying in {retry_interval}s.", "WARN")
            await uasyncio.sleep(retry_interval)
    
    log("MQTT retry loop ended - connection was successful", "INFO")

async def _background_mqtt_connect():
    """Legacy function - now handled by startup flow"""
    pass

async def _background_mqtt_connect_late():
    """MQTT connection when WiFi connects after startup"""
    global mqtt_connection_attempted, mqtt_ever_connected
    
    # Only start if MQTT has never connected and we haven't started trying yet
    if mqtt_connection_attempted or mqtt_ever_connected:
        return
        
    log("Starting MQTT connection attempts after late WiFi connection", "INFO")
    mqtt_connection_attempted = True
    uasyncio.create_task(_background_mqtt_retry())

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

