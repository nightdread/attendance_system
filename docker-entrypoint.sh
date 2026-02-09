#!/bin/bash
set -e

# Fix permissions for mounted volumes (logs and data directories)
# This is needed when volumes are mounted from host with root ownership
if [ -d /app/logs ]; then
    chown -R appuser:appuser /app/logs 2>/dev/null || true
    chmod -R 755 /app/logs 2>/dev/null || true
fi

if [ -d /app/data ]; then
    chown -R appuser:appuser /app/data 2>/dev/null || true
    chmod -R 755 /app/data 2>/dev/null || true
fi

# Switch to appuser and execute the main command
# Join all arguments into a single command string for su -c
CMD="$*"
exec su -s /bin/bash appuser -c "$CMD"
