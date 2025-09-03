#!/bin/bash

# ZivoHealth Backend Services Startup Script
# This script checks and starts PostgreSQL and the FastAPI backend server

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
POSTGRES_PORT=5432
BACKEND_PORT=8000
POSTGRES_DATA_DIR="./data/postgres"
BACKEND_HOST="0.0.0.0"

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

# Function to check if PostgreSQL is running
check_postgres() {
    if pg_isready -h localhost -p $POSTGRES_PORT >/dev/null 2>&1; then
        return 0  # PostgreSQL is running
    else
        return 1  # PostgreSQL is not running
    fi
}

# Function to check if backend is running
check_backend() {
    if curl -s http://localhost:$BACKEND_PORT/docs >/dev/null 2>&1; then
        return 0  # Backend is running
    else
        return 1  # Backend is not running
    fi
}

# Function to start PostgreSQL
start_postgres() {
    print_status "Starting PostgreSQL server..."
    
    # Check if data directory exists
    if [ ! -d "$POSTGRES_DATA_DIR" ]; then
        print_error "PostgreSQL data directory not found: $POSTGRES_DATA_DIR"
        print_status "Initializing new PostgreSQL database..."
        initdb -D "$POSTGRES_DATA_DIR"
        print_success "PostgreSQL database initialized"
    fi
    
    # Start PostgreSQL in background
    postgres -D "$POSTGRES_DATA_DIR" -p $POSTGRES_PORT > ./data/postgres.log 2>&1 &
    POSTGRES_PID=$!
    
    print_status "Waiting for PostgreSQL to start..."
    
    # Wait up to 30 seconds for PostgreSQL to start
    for i in {1..30}; do
        if check_postgres; then
            print_success "PostgreSQL is running on port $POSTGRES_PORT (PID: $POSTGRES_PID)"
            echo $POSTGRES_PID > ./data/postgres.pid
            return 0
        fi
        sleep 1
        echo -n "."
    done
    
    print_error "PostgreSQL failed to start within 30 seconds"
    return 1
}

# Function to stop PostgreSQL
stop_postgres() {
    print_status "Stopping PostgreSQL..."
    if [ -f "./data/postgres.pid" ]; then
        PID=$(cat ./data/postgres.pid)
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            print_success "PostgreSQL stopped"
        fi
        rm -f ./data/postgres.pid
    fi
}

# Function to start backend server
start_backend() {
    print_status "Starting FastAPI backend server..."
    
    # Check if port is already in use
    if lsof -i :$BACKEND_PORT >/dev/null 2>&1; then
        print_warning "Port $BACKEND_PORT is already in use"
        print_status "Attempting to stop existing server..."
        pkill -f "uvicorn.*app.main:app" || true
        sleep 2
    fi
    
    # Start backend server
    python -m uvicorn app.main:app --reload --host $BACKEND_HOST --port $BACKEND_PORT &
    BACKEND_PID=$!
    
    print_status "Waiting for backend server to start..."
    
    # Wait up to 15 seconds for backend to start
    for i in {1..15}; do
        if check_backend; then
            print_success "Backend server is running on http://localhost:$BACKEND_PORT (PID: $BACKEND_PID)"
            echo $BACKEND_PID > ./backend.pid
            return 0
        fi
        sleep 1
        echo -n "."
    done
    
    print_error "Backend server failed to start within 15 seconds"
    return 1
}

# Function to stop backend server
stop_backend() {
    print_status "Stopping backend server..."
    if [ -f "./backend.pid" ]; then
        PID=$(cat ./backend.pid)
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            print_success "Backend server stopped"
        fi
        rm -f ./backend.pid
    fi
    # Also kill any remaining uvicorn processes
    pkill -f "uvicorn.*app.main:app" || true
}

# Function to show service status
show_status() {
    echo -e "\n${BLUE}=== ZivoHealth Services Status ===${NC}"
    
    if check_postgres; then
        print_success "PostgreSQL: Running on port $POSTGRES_PORT"
    else
        print_error "PostgreSQL: Not running"
    fi
    
    if check_backend; then
        print_success "Backend API: Running on http://localhost:$BACKEND_PORT"
        echo -e "               Docs: http://localhost:$BACKEND_PORT/docs"
    else
        print_error "Backend API: Not running"
    fi
    echo ""
}

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Received interrupt signal. Cleaning up...${NC}"
    stop_backend
    stop_postgres
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main script logic
case "${1:-start}" in
    "start")
        echo -e "${BLUE}=== Starting ZivoHealth Backend Services ===${NC}"
        
        # Check and start PostgreSQL
        if check_postgres; then
            print_success "PostgreSQL is already running on port $POSTGRES_PORT"
        else
            start_postgres || exit 1
        fi
        
        # Check and start backend
        if check_backend; then
            print_success "Backend server is already running on port $BACKEND_PORT"
        else
            start_backend || exit 1
        fi
        
        show_status
        
        print_success "All services started successfully!"
        print_status "Press Ctrl+C to stop all services"
        
        # Keep script running to monitor services
        while true; do
            sleep 10
            # Check if services are still running
            if ! check_postgres; then
                print_error "PostgreSQL stopped unexpectedly!"
                break
            fi
            if ! check_backend; then
                print_error "Backend server stopped unexpectedly!"
                break
            fi
        done
        ;;
        
    "stop")
        echo -e "${BLUE}=== Stopping ZivoHealth Backend Services ===${NC}"
        stop_backend
        stop_postgres
        print_success "All services stopped"
        ;;
        
    "restart")
        echo -e "${BLUE}=== Restarting ZivoHealth Backend Services ===${NC}"
        stop_backend
        stop_postgres
        sleep 2
        start_postgres || exit 1
        start_backend || exit 1
        show_status
        print_success "All services restarted successfully!"
        ;;
        
    "status")
        show_status
        ;;
        
    "logs")
        if [ -f "./data/postgres.log" ]; then
            echo -e "${BLUE}=== PostgreSQL Logs ===${NC}"
            tail -f ./data/postgres.log
        else
            print_error "PostgreSQL log file not found"
        fi
        ;;
        
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start PostgreSQL and backend services"
        echo "  stop    - Stop all services"
        echo "  restart - Restart all services"
        echo "  status  - Show service status"
        echo "  logs    - Show PostgreSQL logs"
        exit 1
        ;;
esac 