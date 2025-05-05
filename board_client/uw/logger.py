import utime
import machine

_debug_enabled = False
_start_time = utime.ticks_ms()

def setup_logging(debug_enabled):
    global _debug_enabled
    _debug_enabled = debug_enabled

def log(msg, level="INFO", uptime=False):
    if level == "DEBUG" and not _debug_enabled:
        return

    timestamp = get_log_timestamp()
    
    if uptime:
        elapsed = format_uptime(utime.ticks_diff(utime.ticks_ms(), _start_time))
        print(f"[{timestamp}][{level}] {msg} (elapsed: {elapsed})")
    else:
        print(f"[{timestamp}][{level}] {msg}")

def format_uptime(ms):
    seconds = ms // 1000
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)

def get_log_timestamp():
    try:
        rtc = machine.RTC()
        dt = rtc.datetime()
        # if year is 2024 or earlier, rtc probably not set is a reasonable guess
        if dt[0] < 2025:
            raise ValueError
        # format as ISO8601 UTC
        # apply timezone offset
        return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
            dt[0], dt[1], dt[2], dt[4], dt[5], dt[6]
        )
    except Exception:
        # fallback = elapsed seconds since boot
        elapsed = (utime.ticks_ms() - _start_time) // 1000
        return f"+{elapsed:05d}s"
