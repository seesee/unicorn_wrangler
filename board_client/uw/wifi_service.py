import network
import uasyncio

from uw.config import config
from uw.logger import log
from uw.state import state

wlan = network.WLAN(network.STA_IF)

async def connect_wifi():
    if not config.get("wifi", "enable", False):
        log("WiFi disabled in config.", "INFO")
        return False

    ssid = config.get("wifi", "ssid", "")
    password = config.get("wifi", "password", "")
    wlan.active(True)
    wlan.connect(ssid, password)
    log(f"Connecting to WiFi SSID: {ssid}", "INFO")
    for _ in range(20):  # try for up to 10 seconds
        if wlan.isconnected():
            state.wifi_connected = True
            log(f"WiFi connected, IP: {wlan.ifconfig()[0]}", "INFO")
            return True
        await uasyncio.sleep(0.5)
    state.wifi_connected = False
    log("WiFi connection failed.", "ERROR")
    raise RuntimeError("WiFi connection failed")

async def wifi_monitor():
    while True:
        if not wlan.isconnected():
            state.wifi_connected = False
            try:
                await connect_wifi()
            except RunTimeError:
                pass
        await uasyncio.sleep(10)
