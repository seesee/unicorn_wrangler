"""
Utility functions and classes for Pi compatibility
"""

import time
import asyncio

def log(message, level="INFO", uptime=False):
    """Logging function that matches MicroPython interface"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Simple uptime calculation if requested
    if uptime:
        # For simplicity, just add current time - could be enhanced
        uptime_str = f" (uptime: {int(time.time())}s)"
        print(f"[{timestamp}][{level}] {message}{uptime_str}")
    else:
        print(f"[{timestamp}][{level}] {message}")

def setup_logging(debug_enabled):
    """Setup logging (matches MicroPython interface)"""
    # On Pi, we just use print statements
    # Could be enhanced to use Python logging module
    if debug_enabled:
        print("Debug logging enabled")
    else:
        print("Standard logging enabled")

class StatePi:
    """Pi-compatible state class that matches MicroPython interface"""
    
    def __init__(self):
        self.animation_active = False
        self.streaming_active = False
        self.display_on = True
        self.interrupt_event = asyncio.Event()
        self.text_message = None
        self.text_repeat_count = 1
        self.text_scrolling_active = False
        self.transition_mode = None
        self.wifi_connected = True  # Assume Pi has network
        self.mqtt_connected = False
        self.mqtt_service = None
        self.next_animation = None
        
        # Streaming-related state
        self.stream_frames_rendered = 0
        self.stream_current_name = None
        self.stream_total_frames = 0

# Animation utility functions that work on Pi
def hsv_to_rgb(h, s, v):
    """HSV to RGB conversion (matches animations/utils.py)"""
    if s == 0.0:
        v_int = int(v * 255.0 + 0.5)
        v_int = max(0, min(255, v_int))
        return v_int, v_int, v_int

    i = int(h * 6.0)
    f = (h * 6.0) - i
    p = int((v * (1.0 - s)) * 255.0 + 0.5)
    q = int((v * (1.0 - s * f)) * 255.0 + 0.5)
    t = int((v * (1.0 - s * (1.0 - f))) * 255.0 + 0.5)
    v_int = int(v * 255.0 + 0.5)

    # Clamp values
    p = max(0, min(255, p))
    q = max(0, min(255, q))
    t = max(0, min(255, t))
    v_int = max(0, min(255, v_int))

    i %= 6
    if i == 0: return v_int, t, p
    if i == 1: return q, v_int, p
    if i == 2: return p, v_int, t
    if i == 3: return p, q, v_int
    if i == 4: return t, p, v_int
    return v_int, p, q

# Fast trig functions (on Pi we can afford full precision)
import math

def fast_sin(angle):
    """Fast sine function (on Pi, just use math.sin)"""
    return math.sin(angle)

def fast_cos(angle):
    """Fast cosine function (on Pi, just use math.cos)"""
    return math.cos(angle)
