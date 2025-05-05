Unicorn Wrangler Manager (uw_manager)
=====================================

A web-based management and streaming server for LED matrix animations, with automatic conversion and caching. Upload GIFs, videos, or images and stream them to your Unicorn display.

Features
--------
- Upload GIF, MP4, JPG, PNG, WEBP files (all are auto-converted to versions suitable for Unicorn devices)
- Automatic conversion to multiple aspect ratios using uw_encoder.py
- Web UI for browsing, searching, sorting, and managing GIFs
- Stream server for Unicorn clients
- Recent stream activity and cache status
- Docker and Docker Compose support

Quick Start (Docker Compose)
----------------------------

1. Clone this repository and cd into it.

2. Create a VERSION file (optional, for versioned builds):
   echo "1.0.0" > VERSION

3. Edit docker_compose.yaml if you want to change volumes or ports.

4. Start the stack:
   docker compose up -d

5. Access the web UI:
   http://localhost:5766

6. Upload GIFs, MP4s, JPGs, PNGs, or WEBPs via the web UI.
   All files are converted to run as well as possible on Unicorn device displays.

Equivalent docker run Command
----------------------------

If you prefer not to use Docker Compose, you can run the service directly:

   docker run -d \
     --name unicorn-wrangler \
     -p 5766:5000 \
     -p 8766:8766 \
     -e GIF_DIR=/app/gifs \
     -e UW_CACHE_ROOT=/app/cache \
     -e STREAM_DB=/app/cache/streamserver.sqlite3 \
     -e WEBAPP_PORT=5776 \
     -e HOST=0.0.0.0 \
     -e PORT=8766 \
     -e UW_SCANNER_PID_PATH=/app/cache/uw_scanner.pid \
     -e UW_CACHE_LIMIT=20 \
     -e GIFS_PER_PAGE=20 \
     -e LED_ENCODER_ASPECTS="32x32,53x11,16x16" \
     -v $(pwd)/cache:/app/cache \
     -v $(pwd)/gifs:/app/gifs \
     ghcr.io/seesee/unicorn-wrangler:latest

- Adjust the image name, ports, and volume paths as needed.

Environment Variables
---------------------

- GIF_DIR — Directory for GIFs (default: /app/gifs)
- UW_CACHE_ROOT — Directory for cache and temp files (default: /app/cache)
- STREAM_DB — SQLite DB location (default: /app/cache/streamserver.sqlite3)
- WEBAPP_PORT — Web UI port (default: 5766)
- PORT — Streamserver port (default: 8766)
- LED_ENCODER_ASPECTS — Comma-separated list of display resolutions for your Unicorn devices (default: 32x32,53x11,16x16)
- LED_ENCODER_PATH — Path to the encoder script (default: ./led_encoder.py)

Volumes
-------

- /gifs — Stores all GIFs available for streaming
- /cache — Stores cache, temp files, and the SQLite database

You can use Docker named volumes or bind mounts for persistent storage.

Troubleshooting
---------------

- Conversion in progress?
  The upload form is disabled while a conversion is running. You can reload or kill the conversion from the UI.
- Permissions issues?
  Make sure your cache and gifs directories are writable by the container.
- FFmpeg not found?
  The Docker image must include ffmpeg and ffprobe.

License
-------

MIT (or your chosen license)

Credits
-------

- Pimoroni Unicorn HAT (https://shop.pimoroni.com/products/unicorn-hat)
- Flask (https://flask.palletsprojects.com/)
- FFmpeg (https://ffmpeg.org/)
- Pillow (https://python-pillow.org/)


