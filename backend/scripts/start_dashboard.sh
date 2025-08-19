#!/bin/bash

# ZivoHealth Dashboard Starter
# Starts the React dashboard application

echo "🚀 Starting ZivoHealth Dashboard..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_DIR="$SCRIPT_DIR/../backend-dashboard"

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

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if dashboard directory exists
if [ ! -d "$DASHBOARD_DIR" ]; then
    print_error "Dashboard directory not found: $DASHBOARD_DIR"
    exit 1
fi

# Change to dashboard directory
cd "$DASHBOARD_DIR"

# Check if node_modules exists, if not run npm install
if [ ! -d "node_modules" ]; then
    print_status "Installing dashboard dependencies..."
    if ! npm install; then
        print_error "Failed to install dependencies"
        exit 1
    fi
    print_success "Dependencies installed successfully"
fi

# Start the dashboard
print_status "Starting React development server..."
npm start > dashboard.log 2>&1 &
DASHBOARD_PID=$!

# Wait a moment to check if it started successfully
sleep 3

# Check if the process is still running
if kill -0 $DASHBOARD_PID 2>/dev/null; then
    print_success "Dashboard started successfully (PID: $DASHBOARD_PID)"
    print_status "Dashboard is running at: http://localhost:3000"
    print_status "Logs are being written to: $(pwd)/dashboard.log"
else
    print_error "Dashboard failed to start"
    exit 1
fi 