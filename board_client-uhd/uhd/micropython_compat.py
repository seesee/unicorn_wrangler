"""
MicroPython compatibility layer
Sets up module aliases so MicroPython code runs unchanged
"""

import sys
import asyncio
import json
import time
import array
import gc
import struct

def setup_micropython_compat():
    """Setup all MicroPython compatibility aliases"""
    
    # Only setup once
    if hasattr(setup_micropython_compat, '_setup_done'):
        return
    
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
    
    # Mark as setup
    setup_micropython_compat._setup_done = True
    print("MicroPython compatibility layer loaded")
