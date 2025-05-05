#!/usr/bin/env python3
import os
import sqlite3
import signal
import sys
import re
import shutil
import time
import uuid
from datetime import datetime, timedelta
from flask import (
    Flask,
    request,
    render_template_string,
    send_file,
    redirect,
    url_for,
    flash,
)
from pathlib import Path
from werkzeug.utils import secure_filename
from urllib.parse import urlencode

GIF_DIR = os.environ.get("GIF_DIR", "./gifs")
DB_PATH = os.environ.get("STREAM_DB", "./streamserver.sqlite3")
GIFS_PER_PAGE = int(os.environ.get("GIFS_PER_PAGE", 20))
UW_SCANNER_PID_PATH = os.environ.get("UW_SCANNER_PID_PATH", "./uw_scanner.pid")
CACHE_ROOT = os.environ.get("UW_CACHE_ROOT", "./cache")
CACHE_LIMIT = int(os.environ.get("UW_CACHE_LIMIT", 20))
WEBAPP_PORT = os.environ.get("WEBAPP_PORT", 5000)
HOST = os.environ.get("HOST", "0.0.0.0")
LED_ENCODER_ASPECTS = os.environ.get("LED_ENCODER_ASPECTS", "32x32,53x11,16x16")
LED_ENCODER_PATH = os.environ.get("LED_ENCODER_PATH", "./uw_encoder.py")

ALLOWED_EXTENSIONS = {"gif", "mp4", "jpg", "jpeg", "png", "webp"}

app = Flask(__name__)
app.secret_key = "unicorns"

# --- Utility Functions ---

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_gif(filename):
    # don't special case gifs, just process anyway. TODO: remove 
    return False
    #return filename.lower().endswith('.gif')

def get_db():
    return sqlite3.connect(DB_PATH)

def parse_size_from_filename(filename):
    m = re.search(r'_([0-9]+)x([0-9]+)\.gif$', filename)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None

def human_size(num):
    try:
        num = int(num)
    except Exception:
        return "?"
    for unit in ['bytes','KB','MB','GB']:
        if num < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"

def get_conversion_tmpdir():
    tmp_base = Path(CACHE_ROOT)
    for d in tmp_base.glob("tmp_upload_*"):
        if d.is_dir():
            return d
    return None

def get_conversion_pid(tmpdir):
    pidfile = tmpdir / "pid"
    if pidfile.exists():
        try:
            with open(pidfile) as f:
                return int(f.read().strip())
        except Exception:
            return None
    return None

def kill_conversion(tmpdir):
    pid = get_conversion_pid(tmpdir)
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
        except Exception:
            pass
    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass

def move_gifs_and_cleanup(tmpdir, gif_dir):
    out_dir = tmpdir / "out"
    if out_dir.exists():
        for gif in out_dir.glob("*.gif"):
            dest = Path(gif_dir) / gif.name
            try:
                shutil.move(str(gif), str(dest))
            except Exception as e:
                print(f"[ERROR] Failed to move {gif} to {dest}: {e}", file=sys.stderr)
    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass

def conversion_in_progress():
    tmpdir = get_conversion_tmpdir()
    if not tmpdir:
        return False
    pid = get_conversion_pid(tmpdir)
    if pid is None:
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        move_gifs_and_cleanup(tmpdir, GIF_DIR)
        return False

# --- GIFs Table Backend ---

GIFS_SORTABLE_COLUMNS = {
    "name": "name",
    "frames": "n_frames",
    "size": "file_size",
    "dimensions": "width",
    "cache": "cache_state",
    "first_seen": "first_seen",
    "last_played": "last_played",
    "play_count": "play_count",
}

def get_gif_metadata_with_cache_status(
    search=None, page=1, per_page=GIFS_PER_PAGE, sort="name", order="asc"
):
    db = get_db()
    q = """
        SELECT id, name, filename, width, height, n_frames, checksum, tags, first_seen, last_played, play_count
        FROM gifs
    """
    params = []
    where = []
    if search:
        where.append("name LIKE ?")
        params.append(f"%{search}%")
    if where:
        q += " WHERE " + " AND ".join(where)
    sort_col = GIFS_SORTABLE_COLUMNS.get(sort, "name")
    if sort_col in ("file_size", "cache_state"):
        q += " ORDER BY name ASC"
    else:
        q += f" ORDER BY {sort_col} {'ASC' if order == 'asc' else 'DESC'}, name ASC"
    db_gifs = db.execute(q, params).fetchall()
    db.close()

    db_filenames = set(g[2] for g in db_gifs)
    all_files = {p.name: p for p in Path(GIF_DIR).glob("*.gif")}
    placeholders = []
    for filename, path in all_files.items():
        name = path.stem
        if filename not in db_filenames:
            if search and search.lower() not in name.lower():
                continue
            w, h = parse_size_from_filename(filename)
            placeholders.append(
                (
                    None,
                    name,
                    filename,
                    w,
                    h,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    True,
                )
            )

    all_gifs = list(db_gifs) + placeholders

    db = get_db()
    gif_cache_state = {}
    for gif in all_gifs:
        gif_id = gif[0]
        width = gif[3]
        height = gif[4]
        state = "none"
        if gif_id is not None and width and height:
            row = db.execute(
                """
                SELECT play_count, currently_playing, scheduled_for_deletion
                FROM gif_caches
                WHERE gif_id=? AND width=? AND height=?
            """,
                (gif_id, width, height),
            ).fetchone()
            if row:
                play_count, currently_playing, scheduled_for_deletion = row
                if currently_playing:
                    state = "playing"
                elif scheduled_for_deletion:
                    state = "scheduled"
                elif play_count == 0:
                    state = "cached_not_played"
                else:
                    state = "cached"
        gif_cache_state[gif[1]] = state
    db.close()

    if sort == "size":
        def get_size(g):
            gif_path = Path(GIF_DIR) / g[2]
            try:
                return gif_path.stat().st_size
            except Exception:
                return 0
        all_gifs.sort(
            key=lambda g: (
                get_size(g) if order == "asc" else -get_size(g),
                g[1].lower(),
            )
        )
    elif sort == "frames":
        all_gifs.sort(
            key=lambda g: (
                (g[5] if g[5] is not None else -1) if order == "asc" else -(g[5] if g[5] is not None else -1),
                g[1].lower(),
            )
        )
    elif sort == "dimensions":
        all_gifs.sort(
            key=lambda g: (
                (g[3] or 0) * 10000 + (g[4] or 0) if order == "asc" else -((g[3] or 0) * 10000 + (g[4] or 0)),
                g[1].lower(),
            )
        )
    elif sort == "cache":
        cache_order = {
            "playing": 0,
            "cached": 1,
            "cached_not_played": 2,
            "scheduled": 3,
            "none": 4,
        }
        all_gifs.sort(
            key=lambda g: (
                cache_order.get(gif_cache_state.get(g[1], "none"), 99)
                if order == "asc"
                else -cache_order.get(gif_cache_state.get(g[1], "none"), 99),
                g[1].lower(),
            )
        )
    total = len(all_gifs)
    total_pages = (total + per_page - 1) // per_page
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    paged_gifs = all_gifs[start:end]

    return paged_gifs, total, gif_cache_state, total_pages

# --- Sparkline Filter ---

@app.template_filter('sparkline_svg')
def sparkline_svg(spark, width=120, height=20):
    if not spark or not any(spark):
        return ""
    import math
    n = len(spark)
    if n == width:
        norm = spark
    else:
        norm = []
        for i in range(width):
            orig_idx = i * n / width
            left = int(math.floor(orig_idx))
            right = min(left + 1, n - 1)
            frac = orig_idx - left
            val = (1 - frac) * spark[left] + frac * spark[right]
            norm.append(val)
    maxval = max(norm) or 1
    points = []
    for i, val in enumerate(norm):
        y = height - int((val / maxval) * (height - 2)) if maxval else height
        points.append(f"{i},{y}")
    svg = f'<svg width="{width}" height="{height}" style="vertical-align:middle">'
    svg += f'<polyline fill="none" stroke="#0d6efd" stroke-width="2" points="{" ".join(points)}"/>'
    svg += '</svg>'
    return svg

# --- Recent Streams Backend ---

STREAMS_SORTABLE_COLUMNS = {
    "client_ip": "client_ip",
    "gif": "gif",
    "dimensions": "dimensions",
    "frames": "frame_from",
    "reconnects": "n_reconnects",
    "last_played": "last_played",
}

def get_condensed_streams(
    limit=50, page=1, per_page=20, sort="last_played", order="desc", search=None
):
    db = get_db()
    q = """
        SELECT s.time, s.client_ip, g.name, s.width, s.height, s.frame_from, s.frame_to,
               g.play_count, g.last_played, s.request_cmd, s.frames_sent, s.fps, g.n_frames, s.gif_id
        FROM streams s
        LEFT JOIN gifs g ON s.gif_id = g.id
    """
    params = []
    where = []
    if search:
        where.append("g.name LIKE ?")
        params.append(f"%{search}%")
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY s.time DESC LIMIT ?"
    params.append(limit * 10)
    rows = db.execute(q, params).fetchall()
    db.close()
    from collections import defaultdict

    groups = defaultdict(list)
    for row in rows:
        key = (row[1], row[2], row[3], row[4])
        groups[key].append(row)

    condensed = []
    for key, entries in groups.items():
        entries = sorted(entries, key=lambda r: r[0])
        sessions = []
        session = []
        last_frame_to = None
        for row in entries:
            frame_from = row[5] if row[5] is not None else 0
            if not session or frame_from == 0 or (last_frame_to is not None and frame_from <= last_frame_to):
                if session:
                    sessions.append(session)
                session = []
            session.append(row)
            last_frame_to = row[6] if row[6] is not None else last_frame_to
        if session:
            sessions.append(session)
        for sess in sessions:
            times = [r[0] for r in sess]
            rows_ = sess
            client_ip, gif, width, height = rows_[0][1:5]
            frame_from = min(r[5] for r in rows_ if r[5] is not None)
            frame_to = max(r[6] for r in rows_ if r[6] is not None)
            play_count, last_played = rows_[0][7:9]
            n_frames = int(rows_[0][12] or 0)
            gif_id = rows_[0][13]
            requests = []
            expected = (
                (frame_to - frame_from + 1)
                if frame_from is not None and frame_to is not None
                else None
            )
            spark = [0] * n_frames
            for row in rows_:
                req_from = row[5]
                frames_sent = row[10]
                if req_from is None or frames_sent is None:
                    continue
                for i in range(req_from, min(req_from + frames_sent, n_frames)):
                    spark[i] += 1
            for i, row in enumerate(rows_):
                frames_sent = row[10]
                fps = row[11]
                if expected and frames_sent == expected:
                    status = "success"
                elif i == len(rows_) - 1:
                    status = "active"
                else:
                    status = "error"
                requests.append(
                    {
                        "time": row[0],
                        "frames_sent": frames_sent,
                        "fps": fps,
                        "status": status,
                        "frame_from": row[5],
                        "frame_to": row[6],
                        "request_cmd": row[9],
                    }
                )
            condensed.append(
                {
                    "client_ip": client_ip,
                    "gif": gif,
                    "width": width,
                    "height": height,
                    "frame_from": frame_from,
                    "frame_to": frame_to,
                    "play_count": play_count,
                    "last_played": last_played,
                    "requests": requests,
                    "n_reconnects": len(requests) - 1,
                    "spark": spark,
                    "n_frames": n_frames,
                }
            )

    def get_sort_key(stream):
        if sort == "client_ip":
            return (stream["client_ip"].lower() if stream["client_ip"] else "", stream["gif"] or "")
        elif sort == "gif":
            return (stream["gif"].lower() if stream["gif"] else "", stream["client_ip"] or "")
        elif sort == "dimensions":
            return (stream["width"] * 10000 + stream["height"], stream["gif"] or "")
        elif sort == "frames":
            return (stream["frame_from"], stream["gif"] or "")
        elif sort == "reconnects":
            return (stream["n_reconnects"], stream["gif"] or "")
        elif sort == "last_played":
            try:
                dt = datetime.strptime(stream["last_played"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = datetime.min
            return (dt, stream["gif"] or "")
        else:
            return (stream["gif"] or "", stream["client_ip"] or "")

    condensed.sort(
        key=get_sort_key, reverse=(order == "desc")
    )

    total = len(condensed)
    total_pages = (total + per_page - 1) // per_page
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    paged_streams = condensed[start:end]
    return paged_streams, total, total_pages

# --- Flask Filters ---

@app.template_filter('file_exists')
def file_exists_filter(path):
    return Path(path).exists()

@app.template_filter('file_size')
def file_size_filter(path):
    try:
        return os.stat(path).st_size
    except Exception:
        return 0

# --- URL Helper for Pagination/Sorting ---

@app.context_processor
def utility_processor():
    def url_for_page(section, page):
        args = request.args.to_dict()
        if section == "gifs":
            args["gif_page"] = page
        elif section == "streams":
            args["stream_page"] = page
        return url_for("index") + "?" + urlencode(args)
    return dict(url_for_page=url_for_page, LED_ENCODER_ASPECTS=LED_ENCODER_ASPECTS)

# --- Flask Routes ---

@app.route("/", methods=["GET", "POST"])
def index():
    search = request.args.get("search", "")
    gif_page = int(request.args.get("gif_page", 1))
    gif_sort = request.args.get("gif_sort", "name")
    gif_order = request.args.get("gif_order", "asc")
    stream_page = int(request.args.get("stream_page", 1))
    stream_sort = request.args.get("stream_sort", "last_played")
    stream_order = request.args.get("stream_order", "desc")
    gifs_per_page = int(request.args.get("gpp", GIFS_PER_PAGE))
    streams_per_page = int(request.args.get("spp", 20))

    if request.method == "POST":
        # Kill conversion
        if "kill_conversion" in request.form:
            tmpdir = get_conversion_tmpdir()
            if tmpdir:
                kill_conversion(tmpdir)
                flash("Conversion process killed and temp files cleaned up.", "warning")
            return redirect(url_for("index"))

        # Upload
        if "file" in request.files:
            if conversion_in_progress():
                flash("A conversion is already in progress. Please wait.", "danger")
                return redirect(url_for("index"))
            file = request.files["file"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                ext = filename.rsplit('.', 1)[1].lower()
                if is_gif(filename):
                    try:
                        file.save(str(Path(GIF_DIR) / filename))
                        flash(f"Uploaded {filename}", "success")
                    except Exception as e:
                        flash(f"Error uploading {filename}: {e}", "danger")
                    return redirect(url_for("index"))
                else:
                    unique_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
                    tmpdir = Path(CACHE_ROOT) / f"tmp_upload_{unique_id}"
                    in_dir = tmpdir / "in"
                    out_dir = tmpdir / "out"
                    in_dir.mkdir(parents=True, exist_ok=True)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    in_file = in_dir / filename
                    file.save(str(in_file))
                    aspects = [a.strip() for a in LED_ENCODER_ASPECTS.split(",") if "x" in a]
                    pidfile = tmpdir / "pid"
                    def run_conversion():
                        import sys
                        import subprocess
                        import shutil
                        import os
                        for aspect in aspects:
                            try:
                                w, h = map(int, aspect.lower().split("x"))
                            except Exception:
                                continue
                            cmd = [
                                sys.executable, LED_ENCODER_PATH,
                                str(in_dir), str(out_dir),
                                "--target-width", str(w),
                                "--target-height", str(h),
                                "--overwrite"
                            ]
                            try:
                                subprocess.run(cmd, check=True)
                            except Exception:
                                continue
                        for gif in out_dir.glob("*.gif"):
                            dest = Path(GIF_DIR) / gif.name
                            try:
                                shutil.move(str(gif), str(dest))
                            except Exception as e:
                                print(f"[ERROR] Failed to move {gif} to {dest}: {e}", file=sys.stderr)
                        try:
                            shutil.rmtree(tmpdir)
                        except Exception:
                            print(f"[ERROR] Failed to remove {tmpdir}: {e}", file=sys.stderr)
                            pass
                    import multiprocessing
                    p = multiprocessing.Process(target=run_conversion, daemon=True)
                    p.start()
                    with open(pidfile, "w") as f:
                        f.write(str(p.pid))
                    flash(f"Started conversion for {filename}. Uploads are disabled until complete.", "info")
                    return redirect(url_for("index"))
            else:
                flash("Invalid file type. Only GIF, MP4, JPG, JPEG, PNG, WEBP are allowed.", "danger")
                return redirect(url_for("index"))
        # Remove
        if "remove" in request.form:
            name = request.form["remove"]
            gif_path = Path(GIF_DIR) / (name + ".gif")
            try:
                if gif_path.exists():
                    gif_path.unlink()
                    flash(f"Removed {name}.gif", "success")
                else:
                    flash(f"File {name}.gif not found.", "danger")
            except Exception as e:
                flash(f"Error removing {name}.gif: {e}", "danger")
            return redirect(url_for("index"))
        # Tag
        if "tag" in request.form and "gif_id" in request.form:
            gif_id = request.form["gif_id"]
            tag_val = request.form["tag"].strip()
            try:
                db = get_db()
                db.execute("UPDATE gifs SET tags=? WHERE id=?", (tag_val, gif_id))
                db.commit()
                db.close()
                flash(f"Updated tags for GIF ID {gif_id}", "success")
            except Exception as e:
                flash(f"Error updating tags: {e}", "danger")
            return redirect(url_for("index"))

    gifs, total_gifs, gif_cache_state, gif_total_pages = get_gif_metadata_with_cache_status(
        search=search, page=gif_page, per_page=gifs_per_page, sort=gif_sort, order=gif_order
    )
    condensed_streams, total_streams, stream_total_pages = get_condensed_streams(
        page=stream_page, per_page=streams_per_page, sort=stream_sort, order=stream_order, search=search
    )

    gif_page_range = range(max(1, gif_page-2), min(gif_total_pages+1, gif_page+3))
    stream_page_range = range(max(1, stream_page-2), min(stream_total_pages+1, stream_page+3))

    tmpdir = get_conversion_tmpdir()
    conversion_running = conversion_in_progress()
    converting_filename = None
    if tmpdir:
        in_dir = tmpdir / "in"
        files = list(in_dir.glob("*"))
        if files:
            converting_filename = files[0].name

    return render_template_string(
        TEMPLATE,
        gifs=gifs,
        total_gifs=total_gifs,
        gif_page=gif_page,
        gif_total_pages=gif_total_pages,
        gif_sort=gif_sort,
        gif_order=gif_order,
        gifs_per_page=gifs_per_page,
        gif_cache_state=gif_cache_state,
        gif_dir=GIF_DIR,
        human_size=human_size,
        condensed_streams=condensed_streams,
        total_streams=total_streams,
        stream_page=stream_page,
        stream_total_pages=stream_total_pages,
        stream_sort=stream_sort,
        stream_order=stream_order,
        streams_per_page=streams_per_page,
        request=request,
        gif_page_range=gif_page_range,
        stream_page_range=stream_page_range,
        conversion_running=conversion_running,
        converting_filename=converting_filename,
        max=max,
        min=min,
        LED_ENCODER_ASPECTS=LED_ENCODER_ASPECTS,
    )

@app.route("/trigger_scan", methods=["POST"])
def trigger_scan():
    try:
        with open(UW_SCANNER_PID_PATH) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGUSR1)
        flash("Triggered immediate GIF scan.", "success")
    except Exception as e:
        flash(f"Failed to trigger scan: {e}", "danger")
    return ('', 204)

@app.route("/gif/<name>")
def preview_gif(name):
    gif_path = Path(GIF_DIR) / (name + ".gif")
    if gif_path.exists():
        return send_file(str(gif_path), mimetype="image/gif")
    return "Not found", 404

def graceful_exit(signum, frame):
    print("\n[INFO] Shutting down uw_manager gracefully.")
    sys.exit(0)

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Unicorn Wrangler Management</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <style>
        .gif-thumb { width: 64px; height: 64px; object-fit: contain; }
        .table td, .table th { vertical-align: middle; }
        .tag-input { width: 100px; }
        .placeholder-thumb { width: 64px; height: 64px; background: repeating-linear-gradient(45deg, #eee, #eee 10px, #ccc 10px, #ccc 20px); display: inline-block; border: 1px solid #bbb; }
        .cache-dot { font-size: 1.5em; }
        .cache-cached { color: #0d6efd; }
        .cache-playing { color: #28a745; }
        .cache-scheduled { color: #fd7e14; }
        .cache-none { color: #bbb; }
        .sparkline-cell { min-width: 120px; }
        .expand-row { cursor: pointer; }
        .details-row { display: none; }
        .sortable { cursor: pointer; }
        .sort-arrow { font-size: 0.8em; }
        .pagination-dropdown { width: auto; display: inline-block; }
    </style>
    <script>
        function reloadPage() {
            window.location.reload();
        }
        function triggerScanNow() {
            fetch("{{ url_for('trigger_scan') }}", {method: "POST"})
                .then(() => reloadPage());
        }
        function enableUploadButton() {
            var fileInput = document.getElementById("gif-file");
            var uploadBtn = document.getElementById("upload-btn");
            uploadBtn.disabled = !fileInput.value;
        }
        function confirmKillConversion() {
            if (confirm("Are you sure you want to kill the conversion process and delete temp files?")) {
                document.getElementById("kill-conversion-form").submit();
            }
        }
        function toggleDetails(rowId) {
            var row = document.getElementById(rowId);
            if (row.style.display === "none" || row.style.display === "") {
                row.style.display = "table-row";
            } else {
                row.style.display = "none";
            }
        }
        function jumpToPage(select, section) {
            var page = select.value;
            var params = new URLSearchParams(window.location.search);
            if (section === "gifs") {
                params.set("gif_page", page);
            } else if (section === "streams") {
                params.set("stream_page", page);
            }
            window.location.search = params.toString();
        }
        function sortTable(section, col) {
            var params = new URLSearchParams(window.location.search);
            var sortKey = section === "gifs" ? "gif_sort" : "stream_sort";
            var orderKey = section === "gifs" ? "gif_order" : "stream_order";
            var currentSort = params.get(sortKey) || (section === "gifs" ? "name" : "last_played");
            var currentOrder = params.get(orderKey) || (section === "gifs" ? "asc" : "desc");
            if (currentSort === col) {
                params.set(orderKey, currentOrder === "asc" ? "desc" : "asc");
            } else {
                params.set(sortKey, col);
                params.set(orderKey, section === "gifs" ? "asc" : "desc");
            }
            window.location.search = params.toString();
        }
    </script>
</head>
<body class="bg-light">
<div class="container py-4">
    <h1 class="mb-4">🦄 Unicorn Wrangler Management</h1>
    {% if conversion_running %}
        <div class="alert alert-info">
            <b>Conversion in progress:</b>
            {% if converting_filename %}
                {{ converting_filename }}
            {% else %}
                (unknown file)
            {% endif %}
            <form method="post" id="kill-conversion-form" style="display:inline;">
                <button type="button" class="btn btn-danger btn-sm ms-3" onclick="confirmKillConversion()">Kill Conversion</button>
                <input type="hidden" name="kill_conversion" value="1">
            </form>
            <button class="btn btn-outline-secondary btn-sm ms-2" type="button" onclick="reloadPage()">Reload</button>
        </div>
    {% else %}
        <form method="post" enctype="multipart/form-data" class="mb-3 d-inline" id="upload-form">
            <div class="input-group">
                <input type="file" name="file" accept=".gif,.mp4,.jpg,.jpeg,.png,.webp" class="form-control" id="gif-file" onchange="enableUploadButton()">
                <button class="btn btn-primary" type="submit" id="upload-btn" disabled>Upload GIF/Video/Image</button>
                <button class="btn btn-outline-secondary" type="button" onclick="reloadPage()">Reload</button>
                <button class="btn btn-outline-primary" type="button" onclick="triggerScanNow()">Scan Now</button>
            </div>
            <div class="form-text">
                Accepted: GIF, MP4, JPG, JPEG, PNG, WEBP. Uploads will be converted to the following Unicorn resolution(s): {{ LED_ENCODER_ASPECTS }}
            </div>
        </form>
    {% endif %}
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div class="mt-3">
        {% for category, message in messages %}
          <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
          </div>
        {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    <h2 class="mt-4">GIFs ({{ total_gifs }})</h2>
    <table class="table table-striped table-bordered align-middle">
        <thead class="table-light">
            <tr>
                <th class="sortable" onclick="sortTable('gifs', 'name')">
                    Name
                    {% if gif_sort == 'name' %}
                        <span class="sort-arrow">{{ '▲' if gif_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th>Preview</th>
                <th class="sortable" onclick="sortTable('gifs', 'frames')">
                    Frames
                    {% if gif_sort == 'frames' %}
                        <span class="sort-arrow">{{ '▲' if gif_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th class="sortable" onclick="sortTable('gifs', 'size')">
                    Size
                    {% if gif_sort == 'size' %}
                        <span class="sort-arrow">{{ '▲' if gif_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th class="sortable" onclick="sortTable('gifs', 'dimensions')">
                    Dimensions
                    {% if gif_sort == 'dimensions' %}
                        <span class="sort-arrow">{{ '▲' if gif_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th class="sortable" onclick="sortTable('gifs', 'cache')">
                    Cache State
                </th>
                <th>Tags</th>
                <th class="sortable" onclick="sortTable('gifs', 'first_seen')">
                    First Seen
                    {% if gif_sort == 'first_seen' %}
                        <span class="sort-arrow">{{ '▲' if gif_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th class="sortable" onclick="sortTable('gifs', 'last_played')">
                    Last Played
                    {% if gif_sort == 'last_played' %}
                        <span class="sort-arrow">{{ '▲' if gif_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th class="sortable" onclick="sortTable('gifs', 'play_count')">
                    Play Count
                    {% if gif_sort == 'play_count' %}
                        <span class="sort-arrow">{{ '▲' if gif_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th>Remove</th>
            </tr>
        </thead>
        <tbody>
        {% for gif in gifs %}
        <tr>
            <td>{{ gif[1] }}</td>
            <td>
                {% set gif_path = gif_dir ~ '/' ~ gif[2] %}
                {% if gif|length > 11 and gif[11] %}
                    <span class="placeholder-thumb" title="Pending scan"></span>
                {% elif (gif_path)|file_exists %}
                    <img src="{{ url_for('preview_gif', name=gif[1]) }}" class="gif-thumb border">
                {% else %}
                    <span class="placeholder-thumb"></span>
                {% endif %}
            </td>
            <td>
                {% if gif|length > 11 and gif[11] %}
                    <span class="text-muted">(pending scan)</span>
                {% else %}
                    {{ gif[5] }}
                {% endif %}
            </td>
            <td>
                {% if gif|length > 11 and gif[11] %}
                    <span class="text-muted">(pending scan)</span>
                {% elif (gif_path)|file_exists %}
                    {{ human_size((gif_path)|file_size) }}
                {% else %}
                    ?
                {% endif %}
            </td>
            <td>
                {% if gif|length > 11 and gif[11] %}
                    <span class="text-muted">(pending scan)</span>
                {% else %}
                    {{ gif[3] }}x{{ gif[4] }}
                {% endif %}
            </td>
            <td>
                {% set state = gif_cache_state[gif[1]] %}
                {% if state == "cached_not_played" %}
                    <span class="cache-dot cache-cached" title="Cached, not played">&#9679;</span>
                {% elif state == "playing" %}
                    <span class="cache-dot cache-playing" title="Playing">&#9679;</span>
                {% elif state == "scheduled" %}
                    <span class="cache-dot cache-scheduled" title="Scheduled for deletion">&#9888;</span>
                {% elif state == "cached" %}
                    <span class="cache-dot cache-cached" title="Cached">&#9679;</span>
                {% else %}
                    <span class="cache-dot cache-none" title="Not cached">&#9675;</span>
                {% endif %}
            </td>
            <td>
                {% if gif|length > 11 and gif[11] %}
                    <span class="text-muted">(pending scan)</span>
                {% else %}
                    <form method="post" class="d-flex align-items-center">
                        <input type="hidden" name="gif_id" value="{{ gif[0] }}">
                        <input type="text" name="tag" value="{{ gif[7] or '' }}" class="form-control tag-input me-2">
                        <button class="btn btn-sm btn-outline-primary" type="submit">Save</button>
                    </form>
                {% endif %}
            </td>
            <td>{{ gif[8] or "-" }}</td>
            <td>{{ gif[9] or "-" }}</td>
            <td>{{ gif[10] if gif|length < 12 or not gif[11] else "-" }}</td>
            <td>
                <form method="post" style="display:inline">
                    <button name="remove" value="{{ gif[1] }}" class="btn btn-sm btn-danger" onclick="return confirm('Remove {{ gif[1] }}?')">Remove</button>
                </form>
            </td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    <!-- GIFs Pagination controls -->
    <nav>
      <ul class="pagination">
        <li class="page-item {% if gif_page == 1 %}disabled{% endif %}">
            <a class="page-link" href="{{ url_for_page('gifs', 1) }}">First</a>
        </li>
        <li class="page-item {% if gif_page == 1 %}disabled{% endif %}">
            <a class="page-link" href="{{ url_for_page('gifs', gif_page-1 if gif_page > 1 else 1) }}">Prev</a>
        </li>
        {% for p in gif_page_range %}
          <li class="page-item {% if p == gif_page %}active{% endif %}">
            <a class="page-link" href="{{ url_for_page('gifs', p) }}">{{ p }}</a>
          </li>
        {% endfor %}
        <li class="page-item {% if gif_page == gif_total_pages %}disabled{% endif %}">
            <a class="page-link" href="{{ url_for_page('gifs', gif_page+1 if gif_page < gif_total_pages else gif_total_pages) }}">Next</a>
        </li>
        <li class="page-item {% if gif_page == gif_total_pages %}disabled{% endif %}">
            <a class="page-link" href="{{ url_for_page('gifs', gif_total_pages) }}">Last</a>
        </li>
        <li class="page-item pagination-dropdown">
            <select class="form-select form-select-sm" onchange="jumpToPage(this, 'gifs')">
                {% for p in range(1, gif_total_pages+1) %}
                    <option value="{{ p }}" {% if p == gif_page %}selected{% endif %}>Page {{ p }}</option>
                {% endfor %}
            </select>
        </li>
      </ul>
    </nav>
    <h2 class="mt-4">Recent Streams (Condensed)</h2>
    <table class="table table-bordered table-sm">
        <thead class="table-light">
            <tr>
                <th class="sortable" onclick="sortTable('streams', 'client_ip')">
                    Client IP
                    {% if stream_sort == 'client_ip' %}
                        <span class="sort-arrow">{{ '▲' if stream_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th class="sortable" onclick="sortTable('streams', 'gif')">
                    GIF
                    {% if stream_sort == 'gif' %}
                        <span class="sort-arrow">{{ '▲' if stream_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th class="sortable" onclick="sortTable('streams', 'dimensions')">
                    WxH
                    {% if stream_sort == 'dimensions' %}
                        <span class="sort-arrow">{{ '▲' if stream_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th class="sortable" onclick="sortTable('streams', 'frames')">
                    Frames
                    {% if stream_sort == 'frames' %}
                        <span class="sort-arrow">{{ '▲' if stream_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th>Sparkline</th>
                <th class="sortable" onclick="sortTable('streams', 'reconnects')">
                    Reconnects
                    {% if stream_sort == 'reconnects' %}
                        <span class="sort-arrow">{{ '▲' if stream_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
                <th class="sortable" onclick="sortTable('streams', 'last_played')">
                    Last Played
                    {% if stream_sort == 'last_played' %}
                        <span class="sort-arrow">{{ '▲' if stream_order == 'asc' else '▼' }}</span>
                    {% endif %}
                </th>
            </tr>
        </thead>
        <tbody>
        {% for stream in condensed_streams %}
        <tr class="expand-row" onclick="toggleDetails('details-{{ loop.index0 }}')">
            <td>{{ stream.client_ip }}</td>
            <td>{{ stream.gif or "(deleted)" }}</td>
            <td>{{ stream.width }}x{{ stream.height }}</td>
            <td>{{ stream.frame_from }}-{{ stream.frame_to }}</td>
            <td class="sparkline-cell">
                {% if stream.spark and stream.n_frames > 0 %}
                    {{ stream.spark|sparkline_svg(120, 20)|safe }}
                {% else %}
                    <span class="text-muted">(no data)</span>
                {% endif %}
            </td>
            <td>{{ stream.n_reconnects }}</td>
            <td>{{ stream.last_played or "-" }}</td>
        </tr>
        <tr class="details-row" id="details-{{ loop.index0 }}">
            <td colspan="7">
                <b>Requests:</b>
                <ul>
                {% for req in stream.requests %}
                    <li>
                        <b>{{ req.time }}</b> | Frames: {{ req.frames_sent }} | FPS: {{ req.fps|default('?') }} | Status: {{ req.status }} | Range: {{ req.frame_from }}-{{ req.frame_to }} | Cmd: {{ req.request_cmd }}
                    </li>
                {% endfor %}
                </ul>
            </td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    <!-- Streams Pagination controls -->
    <nav>
      <ul class="pagination">
        <li class="page-item {% if stream_page == 1 %}disabled{% endif %}">
            <a class="page-link" href="{{ url_for_page('streams', 1) }}">First</a>
        </li>
        <li class="page-item {% if stream_page == 1 %}disabled{% endif %}">
            <a class="page-link" href="{{ url_for_page('streams', stream_page-1 if stream_page > 1 else 1) }}">Prev</a>
        </li>
        {% for p in stream_page_range %}
          <li class="page-item {% if p == stream_page %}active{% endif %}">
            <a class="page-link" href="{{ url_for_page('streams', p) }}">{{ p }}</a>
          </li>
        {% endfor %}
        <li class="page-item {% if stream_page == stream_total_pages %}disabled{% endif %}">
            <a class="page-link" href="{{ url_for_page('streams', stream_page+1 if stream_page < stream_total_pages else stream_total_pages) }}">Next</a>
        </li>
        <li class="page-item {% if stream_page == stream_total_pages %}disabled{% endif %}">
            <a class="page-link" href="{{ url_for_page('streams', stream_total_pages) }}">Last</a>
        </li>
        <li class="page-item pagination-dropdown">
            <select class="form-select form-select-sm" onchange="jumpToPage(this, 'streams')">
                {% for p in range(1, stream_total_pages+1) %}
                    <option value="{{ p }}" {% if p == stream_page %}selected{% endif %}>Page {{ p }}</option>
                {% endfor %}
            </select>
        </li>
      </ul>
    </nav>
</div>
</body>
</html>
"""

if __name__ == "__main__":
    os.makedirs(GIF_DIR, exist_ok=True)
    os.makedirs(CACHE_ROOT, exist_ok=True)
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)
    app.run(host=HOST, port=WEBAPP_PORT, debug=True)
