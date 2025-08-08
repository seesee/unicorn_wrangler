import socket
import struct
import utime
import machine
import uasyncio

from uw.logger import log
from uw.config import config

def set_rtc_from_ntp(ntp_host="pool.ntp.org"):
    NTP_DELTA = 2208988800
    s = None
    try:
        log(f"Attempting NTP sync with {ntp_host}", "DEBUG")
        
        # DNS resolution with better error handling
        try:
            addr_info = socket.getaddrinfo(ntp_host, 123)
            if not addr_info:
                raise OSError("DNS resolution failed")
            addr = addr_info[0][-1]
            log(f"NTP server resolved to {addr[0]}", "DEBUG")
        except OSError as e:
            log(f"NTP DNS resolution failed: {e}", "WARN")
            return False
            
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(5)  # Increased timeout
        
        # NTP request packet
        msg = b'\x1b' + 47 * b'\0'
        
        log(f"Sending NTP request to {addr[0]}:123", "DEBUG")
        s.sendto(msg, addr)
        
        # Receive response with timeout
        msg = s.recv(48)
        if len(msg) != 48:
            raise OSError(f"Invalid NTP response length: {len(msg)}")
            
        # Extract timestamp from response
        val = struct.unpack("!I", msg[40:44])[0]
        if val == 0:
            raise OSError("Invalid NTP timestamp")
            
        t = val - NTP_DELTA
        
        # Apply timezone offset
        tz_offset = config.get("general", "timezone_offset", 0)
        t += int(tz_offset * 3600)

        # Set RTC
        tm = utime.gmtime(t)
        machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6]+1, tm[3], tm[4], tm[5], 0))
        
        log(f"RTC set from NTP: {tm[0]}-{tm[1]:02d}-{tm[2]:02d} {tm[3]:02d}:{tm[4]:02d}:{tm[5]:02d}", "INFO")
        return True
        
    except OSError as e:
        log(f"NTP sync network error: {e}", "WARN")
        return False
    except Exception as e:
        log(f"NTP sync failed: {e}", "WARN")
        return False
    finally:
        if s:
            try:
                s.close()
            except:
                pass

def apply_timezone_offset(dt_tuple, offset_hours):
    # dt_tuple: (year, month, mday, wday, hour, minute, second, subsecond)
    t = utime.mktime((dt_tuple[0], dt_tuple[1], dt_tuple[2], dt_tuple[4], dt_tuple[5], dt_tuple[6], 0, 0))
    t += offset_hours * 3600
    new_dt = utime.localtime(t)
    # return same tuple format as rtc
    return (new_dt[0], new_dt[1], new_dt[2], (new_dt[6]+1)%7, new_dt[3], new_dt[4], new_dt[5], 0)

async def periodic_ntp_sync(interval_hours=12):
    while True:
        await uasyncio.sleep(interval_hours * 3600)
        log("Performing periodic NTP sync", "INFO")
        if set_rtc_from_ntp(config.get("general", "ntp_host", "pool.ntp.org")):
            log("Periodic NTP sync successful", "INFO")
        else:
            log("Periodic NTP sync failed", "WARN")


class TimeService:
    def __init__(self, background_tasks):
        self.background_tasks = background_tasks

    def start(self):
        log("Starting TimeService", "INFO")
        # Initial NTP sync
        if not set_rtc_from_ntp():
            log("Initial NTP sync failed. Will retry in background.", "WARN")
        # Schedule periodic sync
        self.background_tasks.add_task(periodic_ntp_sync, 0, "ntp_sync")

    def get_current_time(self):
        return utime.localtime()

    def get_current_time_with_tz(self):
        tz_offset = config.get("general", "timezone_offset", 0)
        return apply_timezone_offset(utime.localtime(), tz_offset)
