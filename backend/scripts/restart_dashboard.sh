#!/bin/bash

# ZivoHealth Dashboard Restarter
# Restarts the React dashboard application

echo "🔄 Restarting ZivoHealth Dashboard..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Main execution
main() {
    print_status "Step 1: Stopping dashboard..."
    echo ""
    
    # Stop the dashboard
    if [ -f "$SCRIPT_DIR/stop_dashboard.sh" ]; then
        "$SCRIPT_DIR/stop_dashboard.sh"
    else
        print_error "stop_dashboard.sh script not found"
        exit 1
    fi
    
    echo ""
    print_status "Step 2: Waiting a moment before restart..."
    sleep 3
    
    echo ""
    print_status "Step 3: Starting dashboard..."
    
    # Start the dashboard
    if [ -f "$SCRIPT_DIR/start_dashboard.sh" ]; then
        "$SCRIPT_DIR/start_dashboard.sh"
        if [ $? -eq 0 ]; then
            print_success "🎉 Dashboard restarted successfully!"
        else
            print_error "Failed to restart dashboard"
            exit 1
        fi
    else
        print_error "start_dashboard.sh script not found"
        exit 1
    fi
}

# Run main function
main "$@" 