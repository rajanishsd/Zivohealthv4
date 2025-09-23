#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

"$SCRIPT_DIR/stop_reminders.sh" || true
"$SCRIPT_DIR/start_reminders.sh"


