#!/bin/bash
set -e

echo "🚀 Debug Railway deployment..."

# Check environment variables
echo "🔍 Environment variables:"
env | grep -E "(SECRET_KEY|DATABASE_URL|ALLOWED_HOSTS|PORT|DEBUG)" || echo "No matching env vars found"

# Start minimal health server first to pass health check
echo "🏥 Starting minimal health server for debugging..."
python minimal_health.py &
HEALTH_PID=$!

echo "Health server started with PID: $HEALTH_PID"

# Sleep to keep container running
sleep 3600