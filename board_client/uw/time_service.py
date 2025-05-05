import socket
import struct
import utime
import machine
import uasyncio

from uw.logger import log
from uw.config import config

def set_rtc_from_ntp(ntp_host="pool.ntp.org"):
    NTP_DELTA = 2208988800
    try:
        addr = socket.getaddrinfo(ntp_host, 123)[0][-1]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        msg = b'\x1b' + 47 * b'\0'
        s.sendto(msg, addr)
        msg = s.recv(48)
        s.close()
        val = struct.unpack("!I", msg[40:44])[0]
        t = val - NTP_DELTA

        tz_offset = config.get("general", "timezone_offset", 0)
        t += int(tz_offset * 3600)

        tm = utime.gmtime(t)
        machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6]+1, tm[3], tm[4], tm[5], 0))
        log("RTC set from NTP", "INFO")
        return True
    except Exception as e:
        log(f"NTP sync failed: {e}", "WARN")
        return False

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
        set_rtc_from_ntp()
