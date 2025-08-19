#!/bin/bash

# Start Redis with custom configuration for Zivohealth Dashboard
# This script ensures Redis uses the correct data directory

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REDIS_CONF="$PROJECT_ROOT/data/redis/redis.conf"
REDIS_DATA_DIR="$PROJECT_ROOT/data/redis"

echo "Starting Redis with custom configuration..."
echo "Project root: $PROJECT_ROOT"
echo "Redis config: $REDIS_CONF"
echo "Data directory: $REDIS_DATA_DIR"

# Ensure data directory exists
mkdir -p "$REDIS_DATA_DIR"

# Stop any existing Redis services
echo "Stopping existing Redis services..."
brew services stop redis 2>/dev/null || true
redis-cli shutdown 2>/dev/null || true

# Wait a moment for cleanup
sleep 2

# Start Redis with our configuration
echo "Starting Redis server..."
redis-server "$REDIS_CONF" &

# Wait for Redis to start
sleep 3

# Verify it's running
if redis-cli ping >/dev/null 2>&1; then
    echo "✅ Redis started successfully!"
    echo "📁 Data directory: $(redis-cli config get dir | tail -1)"
    echo "💾 Database file: $(redis-cli config get dbfilename | tail -1)"
    echo "📊 Current keys: $(redis-cli dbsize | tail -1)"
else
    echo "❌ Failed to start Redis"
    exit 1
fi 