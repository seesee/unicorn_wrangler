"""
MicroPython compatibility layer for the simulator.
Sets up module aliases so MicroPython code runs unchanged.
"""

import sys
import asyncio
import json
import time as _rt
import array
import struct

# Only setup once
if not hasattr(sys, "_uw_sim_compat_setup"):
    # Core async/json aliases
    sys.modules['uasyncio'] = asyncio
    sys.modules['ujson'] = json
    sys.modules['ustruct'] = struct
    sys.modules['uarray'] = array

    # utime compatibility
    class UTime:
        @staticmethod
        def ticks_ms():
            return int(_rt.time() * 1000)
        
        @staticmethod
        def ticks_diff(end, start):
            return end - start
        
        @staticmethod
        def time():
            return int(_rt.time())
        
        sleep = staticmethod(_rt.sleep)
        localtime = staticmethod(_rt.localtime)
        mktime = staticmethod(_rt.mktime)
        gmtime = staticmethod(_rt.gmtime)
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
            return func
        @staticmethod
        def const(value):
            return value
    sys.modules['micropython'] = Micropython()

    sys._uw_sim_compat_setup = True
