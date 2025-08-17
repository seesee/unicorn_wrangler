import uasyncio
import gc

from uw.state import state
from uw.logger import log
from uw.hardware import graphics, gu, WIDTH, HEIGHT
from uw.config import config
from uw.service_manager import mark_streaming_working

FRAME_BUFFER_SIZE = WIDTH * HEIGHT * 2
MAX_RETRIES = 10
BASE_TIMEOUT_MS = 3000
TIMEOUT_STEP_MS = 200

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

def make_request_cmd(width, height, frame_from=None, frame_to=None, gifname=None):
    frame_range = f"{frame_from if frame_from is not None else ''}-{frame_to if frame_to is not None else ''}" \
        if frame_from is not None or frame_to is not None else "-"
    cmd = f"STREAM:{width}:{height}:{frame_range}"
    if gifname:
        cmd += f":{gifname}"
    cmd += "\n"
    return cmd

async def connect_and_request_stream(host, port, request_cmd):
    if not state.wifi_connected:
        log("Stream Request: WiFi not available.", "WARN")
        return False, None, None, None, None, None, None, None, None
    try:
        reader, writer = await uasyncio.wait_for(
            uasyncio.open_connection(host, port), timeout=10.0
        )
        log("Stream connection established", "INFO")
        
        # Mark streaming as working to stop background service retries
        mark_streaming_working()
        
        writer.write(request_cmd.encode('utf-8'))
        await writer.drain()
        response_line = await uasyncio.wait_for(reader.readline(), timeout=5.0)
        if not response_line:
            log("No response from stream server.", "ERROR")
            return False, None, None, None, None, None, None, None, None
        response = response_line.decode().strip()
        log(f"Stream server response: {response}", "DEBUG")
        if response.startswith("INFO:"):
            parts = response.split(":")
            if len(parts) >= 6:
                width = int(parts[1])
                height = int(parts[2])
                frame_range = parts[3]
                gifname = parts[4]
                total_frames = int(parts[5])
                if "-" in frame_range:
                    frame_from, frame_to = frame_range.split("-")
                    frame_from = int(frame_from) if frame_from else 0
                    frame_to = int(frame_to) if frame_to else total_frames - 1
                else:
                    frame_from = 0
                    frame_to = total_frames - 1
                return True, reader, writer, gifname, total_frames, width, height, frame_from, frame_to
        log(f"Malformed or error response: {response}", "ERROR")
    except Exception as e:
        log(f"Error connecting/requesting stream: {e}", "ERROR")
    return False, None, None, None, None, None, None, None, None

async def run(
    graphics=graphics, gu=gu, state=state, interrupt_event=None,
    host=None, port=None, width=WIDTH, height=HEIGHT, gifname=None,
    frame_from=None, frame_to=None
):
    enable_streaming = config.get("streaming", "enable", "false")
    if not enable_streaming:
        return

    if interrupt_event is None:
        interrupt_event = state.interrupt_event

    host = host or config.get("streaming", "host", "127.0.0.1")
    port = port or config.get("streaming", "port", 8766)
    gifname = gifname or None
    frame_from = frame_from if frame_from is not None else None
    frame_to = frame_to if frame_to is not None else None

    state.streaming_active = True
    interrupt_event.clear()

    retries = 0
    last_frame_rendered = frame_from if frame_from is not None else 0
    stream_name = None
    total_frames = None

    while retries < MAX_RETRIES and not interrupt_event.is_set():
        reader = writer = None
        try:
            req = make_request_cmd(width, height, last_frame_rendered, frame_to, gifname)
            log(f"Attempting stream connection (try {retries+1}/{MAX_RETRIES}) from frame {last_frame_rendered}", "INFO")
            success, reader, writer, got_stream_name, got_total_frames, got_width, got_height, got_frame_from, got_frame_to = await connect_and_request_stream(host, port, req)
            if not success:
                raise Exception("Stream connect failed")

            if stream_name != got_stream_name:
                log(f"Stream GIF changed from '{stream_name}' to '{got_stream_name}', resetting frame to 0", "INFO")
                last_frame_rendered = 0
            stream_name = got_stream_name
            total_frames = got_total_frames
            width = got_width
            height = got_height
            frame_from = got_frame_from
            frame_to = got_frame_to

            log(f"Starting stream '{stream_name}' ({total_frames} frames) at {width}x{height} from frame {last_frame_rendered} to {frame_to}", "INFO")
            if state.mqtt_service and state.mqtt_service.connected:
                state.mqtt_service.publish_status({
                    "stream_name": stream_name,
                    "total_frames": total_frames,
                    "frames_displayed": last_frame_rendered
                })

            frames_displayed = last_frame_rendered
            # Linear timeout increase: 3000ms + 200ms * retries
            read_timeout = (BASE_TIMEOUT_MS + retries * TIMEOUT_STEP_MS) / 1000

            while not interrupt_event.is_set() and frames_displayed <= frame_to:
                header = await uasyncio.wait_for(reader.readexactly(4), timeout=read_timeout)
                frame_size = int.from_bytes(header, "big")
                if frame_size != FRAME_BUFFER_SIZE:
                    raise Exception(f"Unexpected frame size: {frame_size}")
                frame_data = await uasyncio.wait_for(reader.readexactly(frame_size), timeout=read_timeout)
                if not await display_rgb565_frame(frame_data):
                    raise Exception("Stream interrupted during display.")
                frames_displayed += 1
                state.stream_frames_rendered = frames_displayed
                last_frame_rendered = frames_displayed
                await uasyncio.sleep(0)
            break

        except Exception as e:
            log(f"Streaming error: {e}", "WARN")
            retries += 1
            gc.collect()
        finally:
            if writer:
                try: writer.close()
                except Exception: pass
            if reader:
                try: reader.close()
                except Exception: pass
            if state.mqtt_service and state.mqtt_service.connected:
                state.mqtt_service.publish_status({
                    "stream_name": stream_name,
                    "total_frames": total_frames,
                    "frames_displayed": last_frame_rendered
                })

    state.streaming_active = False
    interrupt_event.set()
    if retries >= MAX_RETRIES:
        log(f"Stream failed after {MAX_RETRIES} retries. Moving to next animation.", "WARN")

def interrupt_streaming():
    state.interrupt_event.set()
