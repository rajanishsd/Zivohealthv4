#!/bin/bash

echo "🛑 Stopping ZivoHealth background workers..."

# Kill Python processes related to our backend
echo "Finding Python processes in zivohealth/backend directory..."
BACKEND_PROCESSES=$(ps aux | grep -E "python.*zivohealth/backend" | grep -v grep | awk '{print $2}')

if [ -z "$BACKEND_PROCESSES" ]; then
    echo "No backend Python processes found."
else
    echo "Found processes: $BACKEND_PROCESSES"
    echo "Killing backend Python processes..."
    for pid in $BACKEND_PROCESSES; do
        echo "Killing process $pid"
        kill -9 $pid 2>/dev/null || echo "Process $pid already terminated"
    done
fi

# Kill any multiprocessing spawn processes
echo "Finding multiprocessing spawn processes..."
SPAWN_PROCESSES=$(ps aux | grep -E "multiprocessing.spawn" | grep -v grep | awk '{print $2}')

if [ -z "$SPAWN_PROCESSES" ]; then
    echo "No multiprocessing spawn processes found."
else
    echo "Found spawn processes: $SPAWN_PROCESSES"
    echo "Killing spawn processes..."
    for pid in $SPAWN_PROCESSES; do
        echo "Killing spawn process $pid"
        kill -9 $pid 2>/dev/null || echo "Process $pid already terminated"
    done
fi

# Kill any uvicorn processes
echo "Finding uvicorn processes..."
UVICORN_PROCESSES=$(ps aux | grep uvicorn | grep -v grep | awk '{print $2}')

if [ -z "$UVICORN_PROCESSES" ]; then
    echo "No uvicorn processes found."
else
    echo "Found uvicorn processes: $UVICORN_PROCESSES"
    echo "Killing uvicorn processes..."
    for pid in $UVICORN_PROCESSES; do
        echo "Killing uvicorn process $pid"
        kill -9 $pid 2>/dev/null || echo "Process $pid already terminated"
    done
fi

echo "✅ Background worker cleanup complete!"
echo ""
echo "Verifying no processes remain..."
REMAINING=$(ps aux | grep -E "(python.*zivohealth|uvicorn|multiprocessing)" | grep -v grep)
if [ -z "$REMAINING" ]; then
    echo "✅ All processes successfully terminated."
else
    echo "⚠️ Some processes may still be running:"
    echo "$REMAINING"
fi 