#!/bin/bash

# Stop Redis server for Zivohealth Dashboard

echo "Stopping Redis server..."

# Try graceful shutdown first
if redis-cli ping >/dev/null 2>&1; then
    echo "Sending shutdown command to Redis..."
    redis-cli shutdown
    sleep 2
fi

# Stop brew service if running
echo "Stopping Redis brew service..."
brew services stop redis 2>/dev/null || true

# Kill any remaining Redis processes
REDIS_PIDS=$(ps aux | grep redis-server | grep -v grep | awk '{print $2}')
if [ ! -z "$REDIS_PIDS" ]; then
    echo "Killing remaining Redis processes: $REDIS_PIDS"
    kill $REDIS_PIDS 2>/dev/null || true
    sleep 1
fi

# Verify it's stopped
if redis-cli ping >/dev/null 2>&1; then
    echo "❌ Redis is still running"
    exit 1
else
    echo "✅ Redis stopped successfully"
fi 