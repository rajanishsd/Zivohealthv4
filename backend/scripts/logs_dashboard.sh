#!/bin/bash

# ZivoHealth Dashboard Logs Viewer
# Views the React dashboard logs

echo "📝 ZivoHealth Dashboard Logs"
echo "============================="

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/../logs/dashboard.log"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if log file exists
if [ -f "$LOG_FILE" ]; then
    print_status "Showing dashboard logs from: $LOG_FILE"
    echo ""
    echo "Press Ctrl+C to exit"
    echo "===================="
    tail -f "$LOG_FILE"
else
    print_error "Dashboard log file not found: $LOG_FILE"
    print_status "Make sure the dashboard is running first."
    exit 1
fi 