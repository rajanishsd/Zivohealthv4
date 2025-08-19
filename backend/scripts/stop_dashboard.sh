#!/bin/bash

# ZivoHealth Dashboard Stopper
# Stops the React dashboard application

echo "🛑 Stopping ZivoHealth Dashboard..."

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

# Function to stop dashboard by port
stop_dashboard_by_port() {
    local port=3000
    print_status "Looking for dashboard process on port $port..."
    
    # Find process running on port 3000
    local pid=$(lsof -ti:$port 2>/dev/null)
    
    if [ -z "$pid" ]; then
        print_warning "No process found running on port $port"
        return 0
    fi
    
    print_status "Found dashboard process (PID: $pid), stopping..."
    
    # Try graceful shutdown first
    if kill -TERM $pid 2>/dev/null; then
        # Wait up to 10 seconds for graceful shutdown
        local attempts=0
        while [ $attempts -lt 10 ]; do
            if ! kill -0 $pid 2>/dev/null; then
                print_success "Dashboard stopped gracefully"
                return 0
            fi
            sleep 1
            attempts=$((attempts + 1))
        done
        
        # Force kill if graceful shutdown failed
        print_warning "Graceful shutdown timed out, force killing..."
        if kill -KILL $pid 2>/dev/null; then
            print_success "Dashboard force stopped"
            return 0
        fi
    fi
    
    print_error "Failed to stop dashboard process"
    return 1
}

# Function to stop dashboard by process name
stop_dashboard_by_name() {
    print_status "Looking for React development server processes..."
    
    # Look for react-scripts start processes
    local pids=$(pgrep -f "react-scripts start" 2>/dev/null)
    
    if [ -z "$pids" ]; then
        print_warning "No React development server processes found"
        return 0
    fi
    
    print_status "Found React processes, stopping..."
    echo "$pids" | while read pid; do
        if [ ! -z "$pid" ]; then
            print_status "Stopping React process (PID: $pid)..."
            kill -TERM $pid 2>/dev/null
        fi
    done
    
    # Wait a moment and check if any are still running
    sleep 2
    local remaining_pids=$(pgrep -f "react-scripts start" 2>/dev/null)
    
    if [ ! -z "$remaining_pids" ]; then
        print_warning "Some processes still running, force killing..."
        echo "$remaining_pids" | while read pid; do
            if [ ! -z "$pid" ]; then
                kill -KILL $pid 2>/dev/null
            fi
        done
    fi
    
    print_success "React processes stopped"
    return 0
}

# Main execution
main() {
    # Try stopping by port first (more precise)
    if ! stop_dashboard_by_port; then
        print_warning "Port-based stop failed, trying process name..."
        stop_dashboard_by_name
    fi
    
    # Clean up any dashboard log files if they exist
    local log_files=("backend/dashboard.log" "backend/scripts/dashboard.log")
    for log_file in "${log_files[@]}"; do
        if [ -f "$log_file" ]; then
            print_status "Cleaning up log file: $log_file"
            > "$log_file"  # Clear the log file instead of deleting it
        fi
    done
    
    print_success "Dashboard stop process completed"
}

# Run main function
main "$@" 