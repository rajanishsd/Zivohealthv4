#!/bin/bash

echo "🚀 Starting ZivoHealth backend WITHOUT background aggregation worker..."

# Stop any existing processes first
./scripts/stop_workers.sh

echo ""
echo "Starting backend with background worker disabled..."

# Set environment variable to disable background worker and start server
DISABLE_BACKGROUND_WORKER=true uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 