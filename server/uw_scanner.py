#!/usr/bin/env python3
import os
import time
import hashlib
import sqlite3
import signal
import threading
import re
from pathlib import Path
from PIL import Image, ImageSequence

GIF_DIR = os.environ.get("GIF_DIR", "./gifs")
DB_PATH = os.environ.get("STREAM_DB", "./streamserver.sqlite3")
SCAN_INTERVAL = int(os.environ.get("GIF_SCAN_INTERVAL_MINUTES", 5))
PID_PATH = os.environ.get("UW_SCANNER_PID_PATH", "./uw_scanner.pid")
CACHE_ROOT = os.environ.get("UW_CACHE_ROOT", "./cache")
CACHE_LIMIT = int(os.environ.get("UW_CACHE_LIMIT", 20))
STALE_SECONDS = 3600  # 1 hour

shutdown_event = threading.Event()
scan_now_event = threading.Event()

def gif_checksum(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def ensure_db():
    with sqlite3.connect(DB_PATH, timeout=30) as db:
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
        db.commit()

def write_pid():
    with open(PID_PATH, "w") as f:
        f.write(str(os.getpid()))

def ensure_cache_dirs(sizes):
    for w, h in sizes:
        Path(f"{CACHE_ROOT}/{w}x{h}").mkdir(parents=True, exist_ok=True)

def parse_size_from_filename(filename):
    m = re.search(r'_([0-9]+)x([0-9]+)\.gif$', filename)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None

def get_gif_id_by_name(db, name):
    row = db.execute("SELECT id FROM gifs WHERE name=?", (name,)).fetchone()
    return row[0] if row else None

def get_gif_name_by_id(db, gif_id):
    row = db.execute("SELECT name FROM gifs WHERE id=?", (gif_id,)).fetchone()
    return row[0] if row else None

def cache_gif_frames(db, gif_id, gif_path, width, height):
    cache_dir = Path(CACHE_ROOT) / f"{width}x{height}" / gif_path.stem
    cache_dir.mkdir(parents=True, exist_ok=True)
    frames = 0
    try:
        with Image.open(gif_path) as im:
            for idx, frame in enumerate(ImageSequence.Iterator(im)):
                frame = frame.convert("RGB").resize((width, height))
                data = bytearray(width * height * 2)
                i = 0
                for y in range(height):
                    for x in range(width):
                        r, g, b = frame.getpixel((x, y))
                        rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                        data[i] = (rgb565 >> 8) & 0xFF
                        data[i+1] = rgb565 & 0xFF
                        i += 2
                with open(cache_dir / f"frame_{idx:04d}.bin", "wb") as f:
                    f.write(data)
                frames += 1
    except Exception as e:
        print(f"Error caching {gif_path.name} at {width}x{height}: {e}")
        return
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    db.execute("""
    INSERT OR REPLACE INTO gif_caches (gif_id, width, height, cached_at, last_used, frame_count, play_count, avg_fps, scheduled_for_deletion, currently_playing)
    VALUES (?, ?, ?, ?, ?, ?, 0, NULL, 0, 0)
    """, (gif_id, width, height, now, None, frames))

def prune_caches(db, sizes):
    now = time.time()
    for w, h in sizes:
        # Get all available GIFs for this size
        gif_rows = db.execute("""
            SELECT id, name FROM gifs WHERE width=? AND height=?
        """, (w, h)).fetchall()
        available_gif_ids = set(row[0] for row in gif_rows)
        # Get all caches for this size, ordered by last_used/cached_at
        rows = db.execute("""
            SELECT id, gif_id, last_used, cached_at, frame_count, play_count, avg_fps, scheduled_for_deletion
            FROM gif_caches
            WHERE width=? AND height=?
            ORDER BY last_used DESC, cached_at DESC
        """, (w, h)).fetchall()
        # If number of available GIFs <= CACHE_LIMIT, do not schedule any for deletion
        if len(available_gif_ids) <= CACHE_LIMIT:
            for row in rows:
                cache_id = row[0]
                db.execute("UPDATE gif_caches SET scheduled_for_deletion=0 WHERE id=?", (cache_id,))
            continue
        # Otherwise, schedule for deletion if not in top N and played/stale
        keep = set()
        for i, row in enumerate(rows):
            cache_id, gif_id, last_used, cached_at, frame_count, play_count, avg_fps, scheduled = row
            scheduled = False
            if i < CACHE_LIMIT:
                keep.add(cache_id)
                db.execute("UPDATE gif_caches SET scheduled_for_deletion=0 WHERE id=?", (cache_id,))
                continue
            # Only prune if played at least once
            if play_count > 0:
                if last_used:
                    try:
                        last_used_ts = time.mktime(time.strptime(last_used, "%Y-%m-%d %H:%M:%S"))
                    except Exception:
                        last_used_ts = 0
                    if now - last_used_ts > STALE_SECONDS:
                        scheduled = True
                if avg_fps and frame_count and last_used:
                    try:
                        last_used_ts = time.mktime(time.strptime(last_used, "%Y-%m-%d %H:%M:%S"))
                    except Exception:
                        last_used_ts = 0
                    if now - last_used_ts > (3 * frame_count / avg_fps):
                        scheduled = True
            db.execute("UPDATE gif_caches SET scheduled_for_deletion=? WHERE id=?", (1 if scheduled else 0, cache_id))
        # Remove caches that are scheduled for deletion and not in the top N
        for row in rows[CACHE_LIMIT:]:
            cache_id, gif_id, *_ = row
            scheduled = db.execute("SELECT scheduled_for_deletion FROM gif_caches WHERE id=?", (cache_id,)).fetchone()[0]
            if scheduled:
                db.execute("DELETE FROM gif_caches WHERE id=?", (cache_id,))
                cache_dir = Path(CACHE_ROOT) / f"{w}x{h}" / get_gif_name_by_id(db, gif_id)
                if cache_dir.exists():
                    for f in cache_dir.glob("frame_*.bin"):
                        f.unlink()
                    try:
                        cache_dir.rmdir()
                    except Exception:
                        pass
                print(f"Pruned cache for gif_id={gif_id} at {w}x{h}")
    db.commit()

def scan_gifs():
    print(f"[{time.strftime('%H:%M:%S')}] Scanning GIF directory: {GIF_DIR}")
    gif_files = {p.name: p for p in Path(GIF_DIR).glob("*.gif")}
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        db_gifs = db.execute("SELECT name, filename, checksum FROM gifs").fetchall()
        db_filenames = set(filename for _, filename, _ in db_gifs)
        db_checksums = {name: checksum for name, _, checksum in db_gifs}
        for name, filename, _ in db_gifs:
            if filename not in gif_files:
                print(f"Removing stale DB entry: {filename}")
                db.execute("DELETE FROM gifs WHERE name=?", (name,))
        for filename, path in gif_files.items():
            name = path.stem
            checksum = gif_checksum(path)
            w, h = parse_size_from_filename(filename)
            try:
                with Image.open(path) as im:
                    width, height = im.size
                    n_frames = getattr(im, "n_frames", 1)
            except Exception as e:
                print(f"Error reading {filename}: {e}")
                continue
            if w and h:
                width, height = w, h
            row = db.execute("SELECT checksum FROM gifs WHERE name=?", (name,)).fetchone()
            if row is None:
                db.execute("""
                INSERT INTO gifs (name, filename, width, height, n_frames, checksum, first_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (name, filename, width, height, n_frames, checksum, now))
                print(f"Scanned: {filename} (added, {width}x{height}, {n_frames} frames, {checksum[:8]})")
            elif row[0] != checksum:
                db.execute("""
                UPDATE gifs SET filename=?, width=?, height=?, n_frames=?, checksum=?
                WHERE name=?
                """, (filename, width, height, n_frames, checksum, name))
                print(f"Scanned: {filename} (modified, {width}x{height}, {n_frames} frames, {checksum[:8]})")
        db.commit()

def get_all_sizes():
    sizes = set()
    for p in Path(GIF_DIR).glob("*.gif"):
        w, h = parse_size_from_filename(p.name)
        if w and h:
            sizes.add((w, h))
    return sorted(sizes)

def cache_management():
    sizes = get_all_sizes()
    ensure_cache_dirs(sizes)
    with sqlite3.connect(DB_PATH, timeout=30) as db:
        for w, h in sizes:
            # Get all available GIFs for this size
            gif_rows = db.execute("""
                SELECT id, name, filename FROM gifs WHERE width=? AND height=?
            """, (w, h)).fetchall()
            available_gif_ids = set(row[0] for row in gif_rows)
            # If number of available GIFs <= CACHE_LIMIT, ensure all are cached and not scheduled for deletion
            if len(available_gif_ids) <= CACHE_LIMIT:
                for gif_id, name, filename in gif_rows:
                    cache_dir = Path(CACHE_ROOT) / f"{w}x{h}" / name
                    cached = db.execute("""
                        SELECT id FROM gif_caches WHERE gif_id=? AND width=? AND height=?
                    """, (gif_id, w, h)).fetchone()
                    if not cached or not cache_dir.exists():
                        print(f"Caching: {filename} at {w}x{h}")
                        cache_gif_frames(db, gif_id, Path(GIF_DIR) / filename, w, h)
                    # Mark as not scheduled for deletion
                    db.execute("""
                        UPDATE gif_caches SET scheduled_for_deletion=0 WHERE gif_id=? AND width=? AND height=?
                    """, (gif_id, w, h))
                continue
            # Otherwise, cache up to CACHE_LIMIT and schedule for deletion as needed
            rows = db.execute("""
                SELECT id, name, filename FROM gifs
                WHERE width=? AND height=?
                ORDER BY play_count ASC, last_played ASC
                LIMIT ?
            """, (w, h, CACHE_LIMIT)).fetchall()
            for gif_id, name, filename in rows:
                cache_dir = Path(CACHE_ROOT) / f"{w}x{h}" / name
                cached = db.execute("""
                    SELECT id FROM gif_caches WHERE gif_id=? AND width=? AND height=?
                """, (gif_id, w, h)).fetchone()
                if not cached or not cache_dir.exists():
                    print(f"Caching: {filename} at {w}x{h}")
                    cache_gif_frames(db, gif_id, Path(GIF_DIR) / filename, w, h)
        prune_caches(db, get_all_sizes())

def handle_signal(signum, frame):
    if signum in (signal.SIGINT, signal.SIGTERM):
        print("\n[INFO] Shutting down uw_scanner gracefully.")
        shutdown_event.set()
    elif signum == signal.SIGUSR1:
        print("[INFO] Received SIGUSR1: scanning now.")
        scan_now_event.set()

def main():
    ensure_db()
    write_pid()
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, handle_signal)
    else:
        print("[WARN] SIGUSR1 not available on this platform.")
    while not shutdown_event.is_set():
        scan_gifs()
        cache_management()
        print(f"[{time.strftime('%H:%M:%S')}] Scan and cache complete. Sleeping {SCAN_INTERVAL} min.")
        for _ in range(SCAN_INTERVAL * 60):
            if shutdown_event.is_set():
                break
            if scan_now_event.is_set():
                scan_now_event.clear()
                break
            time.sleep(1)
    print("[INFO] uw_scanner stopped.")

if __name__ == "__main__":
    main()

