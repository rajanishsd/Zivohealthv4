#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load only required variables from env files (avoid sourcing invalid lines)
load_env_subset() {
  local file="$1"
  if [ -f "$file" ]; then
    while IFS= read -r line; do
      case "$line" in
        REMINDER_*=*|POSTGRES_*=*|SQLALCHEMY_DATABASE_URI=*)
          export "$line" || true
          ;;
        *) ;;
      esac
    done < "$file"
  fi
}

load_env_subset "$BASE_DIR/.env"
load_env_subset "$BASE_DIR/../.env"

# Ensure Python can import the backend 'app' package
cd "$BASE_DIR"
export PYTHONPATH="$BASE_DIR:${PYTHONPATH:-}"

# Require service config from env (no defaults)
: "${REMINDER_SERVICE_HOST:?Error: set REMINDER_SERVICE_HOST}"
: "${REMINDER_SERVICE_PORT:?Error: set REMINDER_SERVICE_PORT}"
: "${REMINDER_WORKER_CONCURRENCY:?Error: set REMINDER_WORKER_CONCURRENCY}"

# Require DB config: either full URI or POSTGRES_* vars (app derives URI)
if [ -z "${SQLALCHEMY_DATABASE_URI:-}" ]; then
  : "${POSTGRES_SERVER:?Error: set SQLALCHEMY_DATABASE_URI or POSTGRES_SERVER}"
  : "${POSTGRES_PORT:?Error: set SQLALCHEMY_DATABASE_URI or POSTGRES_PORT}"
  : "${POSTGRES_USER:?Error: set SQLALCHEMY_DATABASE_URI or POSTGRES_USER}"
  : "${POSTGRES_DB:?Error: set SQLALCHEMY_DATABASE_URI or POSTGRES_DB}"
fi

# Choose python interpreter (mirror backend start script behavior)
if [ -f "$BASE_DIR/../venv/bin/python" ]; then
  PY_BIN="$BASE_DIR/../venv/bin/python"
elif [ -f "$BASE_DIR/venv/bin/python" ]; then
  PY_BIN="$BASE_DIR/venv/bin/python"
else
  PY_BIN="python3"
fi

mkdir -p "$BASE_DIR/tmp" "$BASE_DIR/logs"
API_PID_FILE="$BASE_DIR/tmp/reminders-api.pid"
WORKER_PID_FILE="$BASE_DIR/tmp/reminders-worker.pid"
BEAT_PID_FILE="$BASE_DIR/tmp/reminders-beat.pid"

# Start Uvicorn API
if [ -f "$API_PID_FILE" ] && kill -0 "$(cat "$API_PID_FILE")" 2>/dev/null; then
  echo "Reminders API already running (PID $(cat "$API_PID_FILE"))"
else
  echo "Starting Reminders API on http://${REMINDER_SERVICE_HOST}:${REMINDER_SERVICE_PORT} ..."
  nohup "$PY_BIN" -m uvicorn app.reminders.service:app \
    --host "${REMINDER_SERVICE_HOST}" \
    --port "${REMINDER_SERVICE_PORT}" \
    > "$BASE_DIR/logs/reminders-api.log" 2>&1 & echo $! > "$API_PID_FILE"
fi

# Start Celery worker
if [ -f "$WORKER_PID_FILE" ] && kill -0 "$(cat "$WORKER_PID_FILE")" 2>/dev/null; then
  echo "Reminders worker already running (PID $(cat "$WORKER_PID_FILE"))"
else
  echo "Starting Reminders Celery worker ..."
  nohup "$PY_BIN" -m celery -A app.reminders.celery_app:celery_app worker \
    --loglevel=INFO -Q reminders.input.v1,reminders.output.v1 \
    --concurrency="${REMINDER_WORKER_CONCURRENCY}" \
    > "$BASE_DIR/logs/reminders-worker.log" 2>&1 & echo $! > "$WORKER_PID_FILE"
fi

# Start Celery beat
if [ -f "$BEAT_PID_FILE" ] && kill -0 "$(cat "$BEAT_PID_FILE")" 2>/dev/null; then
  echo "Reminders beat already running (PID $(cat "$BEAT_PID_FILE"))"
else
  echo "Starting Reminders Celery beat ..."
  nohup "$PY_BIN" -m celery -A app.reminders.celery_app:celery_app beat \
    --loglevel=INFO \
    > "$BASE_DIR/logs/reminders-beat.log" 2>&1 & echo $! > "$BEAT_PID_FILE"
fi

echo "Reminders API logs:    $BASE_DIR/logs/reminders-api.log"
echo "Reminders worker logs: $BASE_DIR/logs/reminders-worker.log"
echo "Reminders beat logs:   $BASE_DIR/logs/reminders-beat.log"


