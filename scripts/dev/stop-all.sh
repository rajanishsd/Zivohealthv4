#!/bin/bash

# ZivoHealth Master Service Stopper
# Stops all services: Dashboard, Backend, Redis, PostgreSQL

echo "🛑 ZivoHealth Master Service Stopper"
echo "===================================="
echo ""

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

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

# Function to stop LiveKit (Docker container)
stop_livekit() {
    print_status "Stopping LiveKit media server..."
    local PID_FILE="backend/data/livekit.pid"

    # Try stopping binary if running
    if [ -f "$PID_FILE" ]; then
        local PID=$(cat "$PID_FILE" 2>/dev/null || true)
        if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null || true
            sleep 1
            if kill -0 "$PID" 2>/dev/null; then
                print_warning "Force killing LiveKit process (PID: $PID)..."
                kill -9 "$PID" 2>/dev/null || true
            fi
            rm -f "$PID_FILE" || true
            print_success "LiveKit (binary) stopped"
        else
            rm -f "$PID_FILE" || true
        fi
    fi

    # Also stop container if present
    if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q '^zivohealth-livekit$'; then
        docker rm -f zivohealth-livekit >/dev/null 2>&1 || true
        print_success "LiveKit container stopped"
    fi

    # Free port if still busy
    if lsof -ti:7880 >/dev/null 2>&1; then
        print_warning "LiveKit signaling port still busy; retrying kill..."
        kill $(lsof -ti:7880) 2>/dev/null || true
    fi
}

# Function to check if a service is running
check_service_running() {
    local service=$1
    local port=$2
    local command=$3
    
    if [ ! -z "$port" ]; then
        if lsof -ti:$port > /dev/null 2>&1; then
            return 0
        fi
    elif [ ! -z "$command" ]; then
        if pgrep -f "$command" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Function to kill processes on a port
kill_port() {
    local port=$1
    local service_name=$2
    
    local pids=$(lsof -ti:$port 2>/dev/null)
    if [ ! -z "$pids" ]; then
        print_status "Stopping $service_name on port $port..."
        kill $pids 2>/dev/null
        sleep 2
        
        # Force kill if still running
        pids=$(lsof -ti:$port 2>/dev/null)
        if [ ! -z "$pids" ]; then
            print_warning "Force killing $service_name processes..."
            kill -9 $pids 2>/dev/null
            sleep 1
        fi
        
        if ! check_service_running "$service_name" "$port"; then
            print_success "$service_name stopped successfully"
        else
            print_error "Failed to stop $service_name"
        fi
    else
        print_success "$service_name was not running"
    fi
}

# Function to stop Dashboard (React dev server)
stop_dashboard() {
    print_status "Stopping React dashboard..."
    
    # Use dedicated dashboard stop script if available
    if [ -f "backend/scripts/stop_dashboard.sh" ]; then
        print_status "Using dedicated dashboard stop script..."
        ./backend/scripts/stop_dashboard.sh
    else
        # Fallback to manual stop
        print_warning "Dashboard stop script not found, using manual stop..."
        
        # Kill React dev server processes
        pkill -f "react-scripts" 2>/dev/null || true
        pkill -f "webpack" 2>/dev/null || true
        
        # Kill any processes on port 3000
        kill_port "3000" "Dashboard"
    fi
}

# Function to stop Backend server
stop_backend() {
    print_status "Stopping FastAPI backend server..."
    
    # Use existing kill script if available
    if [ -f "backend/scripts/kill_servers.sh" ]; then
        print_status "Using existing backend kill script..."
        ./backend/scripts/kill_servers.sh > /dev/null 2>&1
    else
        # Manual cleanup
        pkill -f "uvicorn" 2>/dev/null || true
        pkill -f "app.main" 2>/dev/null || true
        kill_port "8000" "Backend"
    fi
}

# Function to stop Redis
stop_redis() {
    print_status "Stopping Redis server..."
    
    # Use our custom Redis stop script if available
    if [ -f "backend/scripts/stop-redis.sh" ]; then
        print_status "Using custom Redis stop script..."
        ./backend/scripts/stop-redis.sh > /dev/null 2>&1
    else
        # Manual Redis shutdown
        redis-cli shutdown 2>/dev/null || true
        sleep 1
        
        # Force kill Redis processes if still running
        pkill -f "redis-server" 2>/dev/null || true
        kill_port "6379" "Redis"
    fi
}

# Function to stop PostgreSQL
stop_postgresql() {
    print_status "Stopping PostgreSQL database..."
    
    # Use PID file if available (consistent with infrastructure script)
    if [ -f "backend/data/postgres.pid" ]; then
        local PID=$(cat backend/data/postgres.pid)
        if kill -0 $PID 2>/dev/null; then
            print_status "Stopping PostgreSQL process (PID: $PID)..."
            kill $PID 2>/dev/null || true
            sleep 2
            
            # Force kill if still running
            if kill -0 $PID 2>/dev/null; then
                print_warning "Force killing PostgreSQL process..."
                kill -9 $PID 2>/dev/null || true
            fi
        fi
        rm -f backend/data/postgres.pid
    fi
    
    # Try graceful shutdown with pg_ctl for local data directory
    if command -v pg_ctl &> /dev/null && [ -d "backend/data/postgres" ]; then
        pg_ctl -D backend/data/postgres stop -m fast 2>/dev/null || true
    fi
    
    # Force kill any remaining postgres processes
    pkill -f "postgres.*backend/data/postgres" 2>/dev/null || true
    kill_port "5432" "PostgreSQL"
    
    # Clean up any remaining files
    rm -f backend/data/postgres.pid 2>/dev/null || true
    
    if ! check_service_running "PostgreSQL" "5432"; then
        print_success "PostgreSQL stopped successfully"
    else
        print_warning "PostgreSQL may still be running"
    fi
}

# Function to stop RabbitMQ (Homebrew service)
stop_rabbitmq() {
    print_status "Stopping RabbitMQ broker..."
    if command -v brew >/dev/null 2>&1; then
        brew services stop rabbitmq >/dev/null 2>&1 || true
        sleep 1
        kill_port "5672" "RabbitMQ"
    else
        kill_port "5672" "RabbitMQ"
    fi
}

# Function to cleanup any remaining processes
cleanup_remaining() {
    print_status "Cleaning up any remaining processes..."
    
    # Kill any remaining Node.js processes (dashboard related)
    local node_pids=$(pgrep -f "node.*react" 2>/dev/null || true)
    if [ ! -z "$node_pids" ]; then
        print_status "Killing remaining Node.js processes..."
        kill $node_pids 2>/dev/null || true
    fi
    
    # Kill any remaining Python processes (backend related)
    local python_pids=$(pgrep -f "python.*uvicorn\|python.*app.main" 2>/dev/null || true)
    if [ ! -z "$python_pids" ]; then
        print_status "Killing remaining Python processes..."
        kill $python_pids 2>/dev/null || true
    fi
    
    sleep 1
    print_success "Cleanup complete"
}

# Function to stop Reminders service
stop_reminders() {
    print_status "Stopping Reminders service..."
    if [ -f "backend/scripts/stop_reminders.sh" ]; then
        ./backend/scripts/stop_reminders.sh > /dev/null 2>&1 || true
    else
        # Fallback: kill ports/processes (8085 for API; Celery worker/beat by PID files)
        kill_port "8085" "Reminders API"
        pkill -f "celery.*app.reminders.celery_app" 2>/dev/null || true
    fi
}

# Function to stop individual service
stop_service() {
    local service=$1
    
    case $service in
        "dashboard")
            stop_dashboard
            ;;
        "livekit")
            stop_livekit
            ;;
        "backend")
            stop_backend
            ;;
        "redis")
            stop_redis
            ;;
        "postgresql"|"postgres")
            stop_postgresql
            ;;
        "reminders")
            stop_reminders
            ;;
        *)
            print_error "Unknown service: $service"
            print_status "Available services: dashboard, backend, redis, postgresql, reminders, livekit"
            exit 1
            ;;
    esac
}

# Main execution
main() {
    # Check for service-specific stop
    if [ ! -z "$1" ]; then
        print_status "Stopping $1 service..."
        echo ""
        stop_service "$1"
        echo ""
        print_success "🎉 $1 service stopped!"
        echo ""
        echo "💡 Tip: You can stop all services with:"
        echo "   ./scripts/stop-all.sh"
        return
    fi
    
    print_status "Stopping all ZivoHealth services..."
    echo ""
    
    # Stop services in reverse order (Dashboard first, PostgreSQL last)
    stop_dashboard
    echo ""
    
    stop_reminders
    echo ""
    
    stop_livekit
    echo ""

    stop_backend
    echo ""
    
    stop_redis
    echo ""
    
    stop_rabbitmq
    echo ""
    
    stop_postgresql
    echo ""
    
    cleanup_remaining
    echo ""
    
    # Final status check
    print_status "Final service status check..."
    echo ""
    
    local all_stopped=true
    
    if check_service_running "Dashboard" "3000"; then
        echo "❌ Dashboard: Still running on port 3000"
        all_stopped=false
    else
        echo "✅ Dashboard: Stopped"
    fi
    
    if check_service_running "Backend" "8000"; then
        echo "❌ Backend: Still running on port 8000"
        all_stopped=false
    else
        echo "✅ Backend: Stopped"
    fi

    # Reminders API status (port 8085)
    if check_service_running "Reminders API" "8085"; then
        echo "❌ Reminders: Still running on port 8085"
        all_stopped=false
    else
        echo "✅ Reminders: Stopped"
    fi
    
    if check_service_running "Redis" "6379"; then
        echo "❌ Redis: Still running on port 6379"
        all_stopped=false
    else
        echo "✅ Redis: Stopped"
    fi
    
    if check_service_running "PostgreSQL" "5432"; then
        echo "❌ PostgreSQL: Still running on port 5432"
        all_stopped=false
    else
        echo "✅ PostgreSQL: Stopped"
    fi

    # Password Reset App status (built assets presence)
    if [ -d "backend/www/reset-password" ] || [ -d "backend/password-reset-app/build" ]; then
        echo "ℹ️  Password Reset App: Built assets present"
    else
        echo "ℹ️  Password Reset App: No built assets"
    fi
    
    echo ""
    if $all_stopped; then
        print_success "🎉 All ZivoHealth services stopped successfully!"
    else
        print_warning "⚠️  Some services may still be running. Check manually if needed."
    fi
    
    echo ""
    echo "📝 To start all services: ./scripts/start-all.sh"
    echo "🔄 To restart all services: ./scripts/restart-all.sh"
    echo "💡 To stop individual services: ./scripts/stop-all.sh [service]"
    echo "   Available services: dashboard, backend, redis, postgresql"
}

# Run main function
main "$@" 