#!/bin/bash
# Script to show initial credentials from container

echo "🔍 Checking for initial credentials..."
echo ""

CONTAINER_NAME="attendance_system-attendance_app-1"
CREDS_FILE="/app/data/initial_credentials.txt"

# Try to read from file
if docker exec "$CONTAINER_NAME" test -f "$CREDS_FILE" 2>/dev/null; then
    echo "✅ Found credentials file:"
    echo "=" 
    docker exec "$CONTAINER_NAME" cat "$CREDS_FILE"
else
    echo "❌ Credentials file not found (users may already exist or INIT hasn't run yet)"
    echo ""
    echo "To reset and regenerate credentials, run:"
    echo "  docker-compose -f docker-compose.no-angie.yml down -v"
    echo "  docker-compose -f docker-compose.no-angie.yml up -d"
fi

