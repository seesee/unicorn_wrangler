import uasyncio
import gc

from uw.state import state
from uw.logger import log
from uw.hardware import graphics, gu, WIDTH, HEIGHT, MODEL
from uw.config import config

FRAME_BUFFER_SIZE = WIDTH * HEIGHT * 2

async def display_rgb565_frame(data):
    idx = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if state.interrupt_event.is_set():
                return False
            val = (data[idx] << 8) | data[idx + 1]
            idx += 2
            r = ((val >> 11) & 0x1F) << 3
            g = ((val >> 5) & 0x3F) << 2
            b = (val & 0x1F) << 3
            graphics.set_pen(graphics.create_pen(r, g, b))
            graphics.pixel(x, y)
    gu.update(graphics)
    return True

async def run(
    graphics=graphics,
    gu=gu,
    state=state,
    interrupt_event=None,
    host=None,
    port=None,
    tz_offset=None
):
    if not MODEL == "cosmic":
        log("QR Clock only available on Cosmic Unicorn due to required display size")
        return

    enable_streaming = config.get("streaming", "enable", "false")
    if not enable_streaming:
        log("QR Clock requires streaming to be available to obtain QR code data (micropython/pico can't handle independent generation)")
        return

    if interrupt_event is None:
        interrupt_event = state.interrupt_event

    host = host or config.get("streaming", "host", "127.0.0.1")
    port = port or config.get("streaming", "port", 8766)
    tz_offset = tz_offset if tz_offset is not None else config.get("general", "timezone_offset", 0)

    state.streaming_active = True
    interrupt_event.clear()

    while not interrupt_event.is_set():
        try:
            log(f"Connecting to QRClock stream at {host}:{port} (tz_offset={tz_offset})", "INFO")
            reader, writer = await uasyncio.open_connection(host, port)
            cmd = f"QRCLOCK:{tz_offset}\n"
            writer.write(cmd.encode("utf-8"))
            await writer.drain()

            while not interrupt_event.is_set():
                # Read 4-byte frame size header
                header = await uasyncio.wait_for(reader.readexactly(4), timeout=5)
                frame_size = int.from_bytes(header, "big")
                if frame_size != FRAME_BUFFER_SIZE:
                    log(f"Unexpected frame size: {frame_size}", "ERROR")
                    break
                # Read frame data
                frame_data = await uasyncio.wait_for(reader.readexactly(frame_size), timeout=5)
                if not await display_rgb565_frame(frame_data):
                    log("Stream interrupted during display.", "DEBUG")
                    break
                await uasyncio.sleep(0)  # Yield to event loop

        except (uasyncio.TimeoutError, uasyncio.IncompleteReadError, OSError) as e:
            log(f"QRClock stream connection error: {e}", "WARN")
        except Exception as e:
            log(f"QRClock stream error: {e}", "ERROR")
        finally:
            try:
                writer.close()
            except Exception:
                pass
            try:
                reader.close()
            except Exception:
                pass
            gc.collect()
            if not interrupt_event.is_set():
                log("Reconnecting to QRClock stream in 2s...", "INFO")
                await uasyncio.sleep(2)

    state.streaming_active = False
    interrupt_event.set()
