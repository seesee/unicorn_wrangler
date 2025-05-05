#!/usr/bin/env python3
import socket
import struct
import threading
import os
import time
import sqlite3
import signal
import re
import qrcode
from pathlib import Path
from PIL import Image, ImageSequence, ImageOps
from datetime import datetime, timedelta, timezone

GIF_DIR = os.environ.get("GIF_DIR", "./gifs")
DB_PATH = os.environ.get("STREAM_DB", "./streamserver.sqlite3")
CACHE_ROOT = os.environ.get("UW_CACHE_ROOT", "./cache")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 8766))
GIF_STREAM_FPS = float(os.environ.get("GIF_STREAM_FPS", 15.0))

shutdown_event = threading.Event()

def ensure_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS gifs (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            filename TEXT,
            width INTEGER,
            height INTEGER,
            n_frames INTEGER,
            checksum TEXT,
            tags TEXT,
            first_seen TIMESTAMP,
            last_played TIMESTAMP,
            play_count INTEGER DEFAULT 0
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS gif_caches (
            id INTEGER PRIMARY KEY,
            gif_id INTEGER,
            width INTEGER,
            height INTEGER,
            cached_at TIMESTAMP,
            last_used TIMESTAMP,
            frame_count INTEGER,
            play_count INTEGER DEFAULT 0,
            avg_fps REAL,
            scheduled_for_deletion INTEGER DEFAULT 0,
            currently_playing INTEGER DEFAULT 0,
            UNIQUE(gif_id, width, height)
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS streams (
            id INTEGER PRIMARY KEY,
            time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            client_ip TEXT,
            gif_id INTEGER,
            request_cmd TEXT,
            frame_from INTEGER,
            frame_to INTEGER,
            width INTEGER,
            height INTEGER,
            frames_sent INTEGER,
            fps REAL
        )""")
        db.commit()

def parse_size_from_filename(filename):
    m = re.search(r'_([0-9]+)x([0-9]+)\.gif$', filename)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None

def select_gif_from_db(width, height):
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("""
            SELECT id, name, filename FROM gifs
            WHERE width=? AND height=?
            ORDER BY play_count ASC, last_played ASC NULLS FIRST
            LIMIT 1
        """, (width, height)).fetchone()
        if row:
            gif_id, name, filename = row
            return gif_id, name, Path(GIF_DIR) / filename
        return None, None, None

def get_gif_metadata_from_db(gifname):
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("""
            SELECT id, filename, width, height, n_frames FROM gifs WHERE name=?
        """, (gifname,)).fetchone()
        if row:
            gif_id, filename, width, height, n_frames = row
            return gif_id, Path(GIF_DIR) / filename, width, height, n_frames
        return None, None, None, None, None

def get_cached_frames(gif_id, width, height):
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("""
            SELECT id, frame_count FROM gif_caches
            WHERE gif_id=? AND width=? AND height=? AND scheduled_for_deletion=0
        """, (gif_id, width, height)).fetchone()
        if row:
            cache_id, frame_count = row
            cache_dir = Path(CACHE_ROOT) / f"{width}x{height}" / get_gif_name_by_id(gif_id)
            if cache_dir.exists():
                return cache_id, cache_dir, frame_count
        return None, None, None

def get_gif_name_by_id(gif_id):
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT name FROM gifs WHERE id=?", (gif_id,)).fetchone()
        return row[0] if row else None

def update_gif_played(gif_id):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
        UPDATE gifs SET last_played=?, play_count=play_count+1 WHERE id=?
        """, (now, gif_id))
        db.commit()

def log_stream(client_ip, gif_id, request_cmd, frame_from, frame_to, width, height, frames_sent=None, fps=None):
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
        INSERT INTO streams (client_ip, gif_id, request_cmd, frame_from, frame_to, width, height, frames_sent, fps)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (client_ip, gif_id, request_cmd, frame_from, frame_to, width, height, frames_sent, fps))
        db.commit()
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]

def update_stream_fps_and_frames(stream_id, frames_sent, fps):
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
        UPDATE streams SET frames_sent=?, fps=? WHERE id=?
        """, (frames_sent, fps, stream_id))
        db.commit()

def mark_cache_playing(cache_id, playing=True):
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
        UPDATE gif_caches SET currently_playing=? WHERE id=?
        """, (1 if playing else 0, cache_id))
        db.commit()

def update_cache_after_play(cache_id, fps):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
        UPDATE gif_caches SET last_used=?, play_count=play_count+1, avg_fps=?, currently_playing=0 WHERE id=?
        """, (now, fps, cache_id))
        db.commit()

def load_and_resize_frames(gif_path, width, height):
    frames = []
    with Image.open(gif_path) as im:
        for frame in ImageSequence.Iterator(im):
            frame = frame.convert("RGB").resize((width, height))
            data = bytearray(width * height * 2)
            idx = 0
            for y in range(height):
                for x in range(width):
                    r, g, b = frame.getpixel((x, y))
                    rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                    data[idx] = (rgb565 >> 8) & 0xFF
                    data[idx+1] = rgb565 & 0xFF
                    idx += 2
            frames.append(data)
    return frames

def generate_qrclock_frame(offset_hours=0.0, size=32):
    now_utc = datetime.now(timezone.utc)
    local_time = now_utc + timedelta(hours=offset_hours)
    dt_str = local_time.strftime("%Y-%m-%d %H:%M:%S")
    # Generate QR code as a PIL image (mode '1' for 1-bit pixels)
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,  # 1 pixel per QR module
        border=0,    # We'll add our own border
    )
    qr.add_data(dt_str)
    qr.make(fit=True)
    qr_matrix = qr.get_matrix()
    qr_size = len(qr_matrix)  # Number of modules (pixels) per side

    # Calculate the largest QR code size that fits with a border
    max_qr_size = size - 2 * 2  # 2-pixel border on each side
    if qr_size > max_qr_size:
        raise ValueError(f"QR code too large ({qr_size}) for display size {size}")

    # Create a black 32x32 image
    img = Image.new("RGB", (size, size), (0, 0, 0))
    # Calculate top-left position to center the QR code
    offset = ((size - qr_size) // 2, (size - qr_size) // 2)
    # Draw the QR code pixels
    for y in range(qr_size):
        for x in range(qr_size):
            if qr_matrix[y][x]:
                img.putpixel((offset[0] + x, offset[1] + y), (255, 255, 255))
    # No need to invert; white modules are "on"
    # Convert to RGB565
    data = bytearray(size * size * 2)
    idx = 0
    for y in range(size):
        for x in range(size):
            r, g, b = img.getpixel((x, y))
            rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            data[idx] = (rgb565 >> 8) & 0xFF
            data[idx+1] = rgb565 & 0xFF
            idx += 2
    return data, dt_str


def parse_stream_cmd(cmd):
    parts = cmd.strip().split(":")
    if len(parts) < 4 or not parts[0] == "STREAM":
        return None, None, None, None, None
    try:
        width = int(parts[1])
        height = int(parts[2])
    except Exception:
        return None, None, None, None, None
    frame_from, frame_to = 0, None
    gifname = None
    range_part = parts[3]
    if "-" in range_part:
        ffrom, fto = range_part.split("-", 1)
        frame_from = int(ffrom) if ffrom.isdigit() else 0
        frame_to = int(fto) if fto.isdigit() else None
    elif range_part.isdigit():
        frame_from = int(range_part)
    if len(parts) > 4 and parts[4]:
        gifname = parts[4]
    return width, height, frame_from, frame_to, gifname

def stream_from_cache(conn, cache_id, cache_dir, frame_from, frame_to, frame_count, stream_id=None):
    mark_cache_playing(cache_id, True)
    frames_sent = 0
    t0 = time.time()
    try:
        for idx in range(frame_from, frame_to + 1):
            frame_file = cache_dir / f"frame_{idx:04d}.bin"
            if not frame_file.exists():
                print(f"Missing cached frame: {frame_file}")
                break
            with open(frame_file, "rb") as f:
                data = f.read()
            header = struct.pack(">I", len(data))
            try:
                conn.sendall(header)
                conn.sendall(data)
                frames_sent += 1
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                print(f"Disconnected during cached frame {idx}")
                break
            time.sleep(1.0 / GIF_STREAM_FPS)
    finally:
        t1 = time.time()
        elapsed = t1 - t0 if t1 > t0 else 1e-6
        fps = frames_sent / elapsed
        print(f"Streamed {frames_sent} cached frames in {elapsed:.2f}s ({fps:.2f} fps)")
        update_cache_after_play(cache_id, fps)
        if stream_id is not None:
            update_stream_fps_and_frames(stream_id, frames_sent, fps)
    return frames_sent, elapsed, fps

def handle_client(conn, addr):
    print(f"[{time.strftime('%H:%M:%S')}] New connection from {addr}")
    try:
        conn.settimeout(10)
        f = conn.makefile('r', encoding='utf-8', errors='ignore', buffering=1024)
        line = f.readline()
        if not line:
            print(f"[{time.strftime('%H:%M:%S')}] {addr} disconnected (no command)")
            conn.close()
            return

        cmd = line.strip()
        print(f"[{time.strftime('%H:%M:%S')}] Received command from {addr}: '{cmd}'")
        
        # support qrcode streaming
        if cmd.startswith("QRCLOCK"):
            # Parse offset if provided
            parts = cmd.strip().split(":")
            offset = 0.0
            if len(parts) > 1:
                try:
                    offset = float(parts[1])
                except Exception:
                    pass  # fallback to 0
            size = 32  # or make this configurable
            # Send one frame per second, e.g., for 10 seconds (or until client disconnects)
            try:
                for _ in range(60*60*24):  # up to 24h, or until client disconnects
                    frame, dt_str = generate_qrclock_frame(offset, size)
                    header = struct.pack(">I", len(frame))
                    conn.sendall(header)
                    conn.sendall(frame)
                    # Optionally, send the datetime string as info
                    # conn.sendall(dt_str.encode() + b"\n")
                    time.sleep(1)
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                print(f"[{time.strftime('%H:%M:%S')}] {addr} disconnected from QRCLOCK")
            finally:
                conn.close()
            return

        width, height, frame_from, frame_to, gifname = parse_stream_cmd(cmd)
        if not width or not height:
            conn.sendall(b"ERROR:Invalid command\n")
            print(f"[{time.strftime('%H:%M:%S')}] {addr} sent invalid command")
            conn.close()
            return

        # Find GIF
        if gifname:
            gif_id, gif_path, real_width, real_height, n_frames = get_gif_metadata_from_db(gifname)
            if not gif_path or not gif_path.exists():
                conn.sendall(f"ERROR:Animation '{gifname}' not found\n".encode())
                print(f"[{time.strftime('%H:%M:%S')}] {addr} requested missing gif '{gifname}'")
                conn.close()
                return
        else:
            gif_id, gifname, gif_path = select_gif_from_db(width, height)
            if not gif_path or not gif_path.exists():
                conn.sendall(b"ERROR:No suitable animations available\n")
                print(f"[{time.strftime('%H:%M:%S')}] {addr} no suitable gifs for {width}x{height}")
                conn.close()
                return
            _, _, real_width, real_height, n_frames = get_gif_metadata_from_db(gifname)

        if frame_to is None or frame_to >= n_frames:
            frame_to = n_frames - 1
        if frame_from < 0 or frame_from >= n_frames:
            frame_from = 0
        if frame_to < frame_from:
            frame_to = n_frames - 1

        info_msg = f"INFO:{width}:{height}:{frame_from}-{frame_to}:{gifname}:{n_frames}\n"
        conn.sendall(info_msg.encode())
        print(f"[{time.strftime('%H:%M:%S')}] {addr} INFO sent: {info_msg.strip()}")

        # Log the stream and get stream_id
        stream_id = log_stream(addr[0], gif_id, cmd, frame_from, frame_to, width, height)

        # Try to stream from cache
        cache_id, cache_dir, cached_frame_count = get_cached_frames(gif_id, width, height)
        if cache_id and cache_dir and cached_frame_count and cached_frame_count > frame_to:
            print(f"[{time.strftime('%H:%M:%S')}] {addr} streaming from cache: {cache_dir}")
            frames_sent, elapsed, fps = stream_from_cache(conn, cache_id, cache_dir, frame_from, frame_to, cached_frame_count, stream_id=stream_id)
        else:
            # Fallback: generate on the fly
            print(f"[{time.strftime('%H:%M:%S')}] {addr} streaming on the fly: {gif_path.name} at {width}x{height}")
            frames = load_and_resize_frames(gif_path, width, height)
            frames_sent = 0
            t0 = time.time()
            for idx in range(frame_from, frame_to + 1):
                frame = frames[idx]
                header = struct.pack(">I", len(frame))
                try:
                    conn.sendall(header)
                    conn.sendall(frame)
                    frames_sent += 1
                except (BrokenPipeError, ConnectionResetError, socket.timeout):
                    print(f"[{time.strftime('%H:%M:%S')}] {addr} disconnected during frame {idx}")
                    break
                time.sleep(1.0 / GIF_STREAM_FPS)
            t1 = time.time()
            elapsed = t1 - t0 if t1 > t0 else 1e-6
            fps = frames_sent / elapsed
            print(f"[{time.strftime('%H:%M:%S')}] {addr} streamed {frames_sent} on-the-fly frames in {elapsed:.2f}s ({fps:.2f} fps)")
            update_stream_fps_and_frames(stream_id, frames_sent, fps)
        update_gif_played(gif_id)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error handling client {addr}: {e}")
    finally:
        try: conn.close()
        except: pass

def graceful_exit(signum, frame):
    print("\n[INFO] Shutting down uw_streamserver gracefully.")
    shutdown_event.set()

def main():
    ensure_db()
    print(f"Starting uw_streamserver on {HOST}:{PORT}, GIF dir: {GIF_DIR}, Cache: {CACHE_ROOT}, FPS: {GIF_STREAM_FPS}")
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        while not shutdown_event.is_set():
            try:
                conn, addr = s.accept()
                threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
            except OSError:
                break
    print("[INFO] uw_streamserver stopped.")

if __name__ == "__main__":
    main()

