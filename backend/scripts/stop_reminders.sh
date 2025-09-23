#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

API_PID_FILE="$BASE_DIR/tmp/reminders-api.pid"
WORKER_PID_FILE="$BASE_DIR/tmp/reminders-worker.pid"
BEAT_PID_FILE="$BASE_DIR/tmp/reminders-beat.pid"
CHILD_PID_FILE="$BASE_DIR/tmp/worker-child-pids.pid"

stop_pid() {
  local file="$1"
  local name="$2"
  if [ -f "$file" ]; then
    local pid
    pid=$(cat "$file")
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping $name (PID $pid) ..."
      kill "$pid" 2>/dev/null || true
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        echo "$name did not stop gracefully, killing -9 ..."
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
    rm -f "$file"
  else
    echo "$name not running (no PID file)"
  fi
}

# Function to kill tracked child workers
kill_child_workers() {
  if [ -f "$CHILD_PID_FILE" ]; then
    echo "Killing tracked child workers..."
    while IFS= read -r pid; do
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "Killing child worker PID $pid"
        kill -TERM "$pid" 2>/dev/null || true
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
          kill -9 "$pid" 2>/dev/null || true
        fi
      fi
    done < "$CHILD_PID_FILE"
    rm -f "$CHILD_PID_FILE"
  fi
}

# Function to kill all remaining Celery processes (fallback)
kill_all_celery() {
  echo "Killing all remaining Celery processes..."
  pkill -f "celery.*worker" 2>/dev/null || true
  pkill -f "celery.*beat" 2>/dev/null || true
  sleep 2
}

stop_pid "$API_PID_FILE" "Reminders API"
stop_pid "$WORKER_PID_FILE" "Reminders worker"
stop_pid "$BEAT_PID_FILE" "Reminders beat"

# Kill tracked child workers
kill_child_workers

# Fallback: kill all remaining Celery processes
kill_all_celery

# Verify cleanup
echo "Verifying cleanup..."
REMAINING_WORKERS=$(ps aux | grep "celery.*worker" | grep -v grep | wc -l)
REMAINING_BEAT=$(ps aux | grep "celery.*beat" | grep -v grep | wc -l)

if [ "$REMAINING_WORKERS" -gt 0 ] || [ "$REMAINING_BEAT" -gt 0 ]; then
  echo "Warning: $REMAINING_WORKERS workers and $REMAINING_BEAT beat processes still running"
  echo "Force killing all remaining Celery processes..."
  pkill -9 -f "celery" 2>/dev/null || true
  sleep 1
fi

echo "Reminders processes stopped."


