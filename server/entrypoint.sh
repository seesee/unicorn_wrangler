#!/bin/sh
set -e

echo "Docker Entrypoint: Starting Diagnostics..."
echo "  - Timestamp: $(date)"
echo "  - Current User: $(whoami)"
echo "  - Working Directory: $(pwd)"

echo "Listing /app:"
ls -la /app

echo "Attempting to list GIF Directory (${GIF_DIR}):"
ls -la "${GIF_DIR}" || echo "Warning: GIF directory listing failed or directory not ready."

echo "Attempting to list Cache Directory (${CACHE_DIR}):"
ls -la "${CACHE_DIR}" || echo "Warning: Cache directory listing failed or directory not ready."

echo "Environment Variables:"
printenv | sort

echo "Python Version: $(python --version)"
echo "Docker Entrypoint: Diagnostics Complete"
echo "  - Executing CMD ($@)"

exec "$@"

