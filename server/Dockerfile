FROM python:3.9-slim

# Install ffmpeg and ffprobe
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script and config
COPY . .
COPY supervisord.conf /etc/supervisord.conf

RUN chmod +x entrypoint.sh

# Create default directories
RUN mkdir -p /app/gifs /app/cache

# Create unicorn user and apply permissions
RUN groupadd -r unicorn && useradd -r -g unicorn unicorn \
    && chown -R unicorn:unicorn /app /app/gifs /app/cache

# Set default environment variables
ENV HOST=0.0.0.0
ENV PORT=8766
ENV WEBAPP_PORT=5000
ENV GIF_DIR=/app/gifs
ENV CACHE_DIR=/app/cache
ENV STREAM_DB=/app/cache/streamserver.sqlite3

# Run python in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Expose the streaming port
EXPOSE 8766

# Expose web port
EXPOSE 5000

# Switch to unicorn user
USER unicorn

# Entrypoint script to print out actual env variables 
ENTRYPOINT ["/app/entrypoint.sh"]

# Start the server
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
