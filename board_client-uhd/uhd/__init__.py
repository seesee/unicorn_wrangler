"""
Unicorn Wrangler Pi - UHD compatibility layer for running on Raspberry Pi
"""

# Set up MicroPython compatibility IMMEDIATELY when this module is imported
import sys
import asyncio
import json
import time
import array
import gc
import struct

# === MICROPYTHON COMPATIBILITY ALIASES ===
# Set these up immediately, not in a function

# Core async/json aliases
sys.modules['uasyncio'] = asyncio
sys.modules['ujson'] = json
sys.modules['ustruct'] = struct
sys.modules['uarray'] = array

# utime compatibility
class UTime:
    @staticmethod
    def ticks_ms():
        return int(time.time() * 1000)
    
    @staticmethod
    def ticks_diff(end, start):
        return end - start
    
    sleep = staticmethod(time.sleep)
    localtime = staticmethod(time.localtime)
    mktime = staticmethod(time.mktime)
    gmtime = staticmethod(time.gmtime)

sys.modules['utime'] = UTime()

# machine compatibility
class Machine:
    class RTC:
        @staticmethod
        def datetime():
            import datetime as dt
            now = dt.datetime.now()
            return (now.year, now.month, now.day, now.weekday(),
                   now.hour, now.minute, now.second, 0)
    
    @staticmethod
    def reset():
        print("Reset requested - exiting...")
        import sys
        sys.exit(0)

sys.modules['machine'] = Machine()

# micropython compatibility
class Micropython:
    @staticmethod
    def native(func):
        """@micropython.native decorator - no-op on Pi"""
        return func
    
    @staticmethod
    def const(value):
        """micropython.const() - just return value on Pi"""
        return value

sys.modules['micropython'] = Micropython()

print("MicroPython compatibility aliases loaded")

# Now import the rest of the compatibility wrappers
from .hardware_compat import graphics, gu, WIDTH, HEIGHT, MODEL, set_brightness
from .config_compat import config
from .mqtt_compat import MQTTServicePi
from .utils import log, StatePi

# Create global state instance
state = StatePi()

__all__ = [
    'graphics', 'gu', 'WIDTH', 'HEIGHT', 'MODEL', 'set_brightness',
    'config', 'state', 'MQTTServicePi', 'log'
]
