#!/bin/bash

# ZivoHealth Master Service Starter
# Starts all services: PostgreSQL, Redis, Backend, Dashboard

echo "🏥 ZivoHealth Master Service Starter"
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

# Function to check if a service is running
check_service() {
    local service=$1
    local port=$2
    local command=$3
    
    if [ ! -z "$port" ]; then
        if lsof -ti:$port > /dev/null 2>&1; then
            print_success "$service is already running on port $port"
            return 0
        fi
    elif [ ! -z "$command" ]; then
        if pgrep -f "$command" > /dev/null 2>&1; then
            print_success "$service is already running"
            return 0
        fi
    fi
    return 1
}

# Function to start PostgreSQL
start_postgresql() {
    print_status "Starting PostgreSQL database..."
    
    if check_service "PostgreSQL" "5432"; then
        return 0
    fi
    
    # Check if PostgreSQL is installed
    if ! command -v postgres &> /dev/null; then
        print_error "PostgreSQL is not installed. Please install it first:"
        print_error "brew install postgresql"
        return 1
    fi
    
    # Use local data directory (consistent with infrastructure script)
    POSTGRES_DATA_DIR="backend/data/postgres"
    
    # Check if data directory exists, create if not
    if [ ! -d "$POSTGRES_DATA_DIR" ]; then
        print_status "PostgreSQL data directory not found. Initializing..."
        mkdir -p backend/data
        initdb -D "$POSTGRES_DATA_DIR"
        print_success "PostgreSQL database initialized"
    fi
    
    # Start PostgreSQL with local data directory
    postgres -D "$POSTGRES_DATA_DIR" -p 5432 > backend/data/postgres.log 2>&1 &
    POSTGRES_PID=$!
    
    # Save PID for cleanup
    echo $POSTGRES_PID > backend/data/postgres.pid
    
    # Wait for PostgreSQL to start
    print_status "Waiting for PostgreSQL to start..."
    local attempts=0
    while [ $attempts -lt 30 ]; do
        if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
            print_success "PostgreSQL started successfully (PID: $POSTGRES_PID)"
            return 0
        fi
        sleep 1
        attempts=$((attempts + 1))
        echo -n "."
    done
    
    print_error "PostgreSQL failed to start within 30 seconds"
    return 1
}

# Function to start Redis
start_redis() {
    print_status "Starting Redis server..."
    
    if check_service "Redis" "6379"; then
        return 0
    fi
    
    # Use our custom Redis startup script
    if [ -f "backend/scripts/start-redis.sh" ]; then
        print_status "Using custom Redis configuration..."
        ./backend/scripts/start-redis.sh > /dev/null 2>&1 &
        sleep 3
        
        if check_service "Redis" "6379"; then
            print_success "Redis started with custom configuration"
            return 0
        fi
    fi
    
    # Fallback to standard Redis
    print_warning "Custom Redis script failed, trying standard Redis..."
    redis-server > /dev/null 2>&1 &
    sleep 2
    
    if check_service "Redis" "6379"; then
        print_success "Redis started successfully"
        return 0
    else
        print_error "Failed to start Redis"
        return 1
    fi
}

# Function to start Backend server
start_backend() {
    print_status "Starting FastAPI backend server..."
    
    if check_service "Backend" "8000"; then
        return 0
    fi
    
    # Use existing backend startup script
    if [ -f "backend/scripts/start_server.sh" ]; then
        print_status "Using existing backend startup script..."
        ./backend/scripts/start_server.sh > backend/server.log 2>&1 &
        
        # Wait for backend to start
        local attempts=0
        while [ $attempts -lt 30 ]; do
            if curl -s http://localhost:8000/health > /dev/null 2>&1; then
                print_success "Backend server started successfully"
                return 0
            fi
            sleep 2
            attempts=$((attempts + 1))
        done
        
        print_error "Backend server failed to start or health check failed"
        return 1
    else
        print_error "Backend startup script not found"
        return 1
    fi
}

# Function to build Password Reset App
build_password_reset_app() {
    print_status "Building password reset app..."
    
    # Check if password reset app directory exists
    if [ ! -d "backend/password-reset-app" ]; then
        print_warning "Password reset app directory not found, skipping build..."
        return 0
    fi
    
    # Use existing build script
    if [ -f "backend/scripts/build_password_reset_app.sh" ]; then
        print_status "Using password reset app build script..."
        if ./backend/scripts/build_password_reset_app.sh > /dev/null 2>&1; then
            print_success "Password reset app built successfully"
            return 0
        else
            print_warning "Password reset app build failed, continuing..."
            return 0  # Don't fail the entire startup process
        fi
    else
        print_warning "Password reset app build script not found, skipping..."
        return 0
    fi
}

# Function to start Dashboard
start_dashboard() {
    print_status "Starting React dashboard..."
    
    if check_service "Dashboard" "3000"; then
        return 0
    fi
    
    # Use existing dashboard startup script
    if [ -f "backend/scripts/start_dashboard.sh" ]; then
        print_status "Using existing dashboard startup script..."
        ./backend/scripts/start_dashboard.sh > backend/dashboard.log 2>&1 &
        
        # Wait for dashboard to start
        sleep 10
        local attempts=0
        while [ $attempts -lt 20 ]; do
            if curl -s http://localhost:3000 > /dev/null 2>&1; then
                print_success "Dashboard started successfully"
                return 0
            fi
            sleep 3
            attempts=$((attempts + 1))
        done
        
        print_warning "Dashboard may still be starting (check http://localhost:3000)"
        return 0
    else
        print_error "Dashboard startup script not found"
        return 1
    fi
}

# Function to start individual service
start_service() {
    local service=$1
    
    case $service in
        "postgresql"|"postgres")
            start_postgresql
            ;;
        "redis")
            start_redis
            ;;
        "password-reset"|"reset-app")
            build_password_reset_app
            ;;
        "backend")
            build_password_reset_app  # Build reset app before backend
            start_backend
            ;;
        "dashboard")
            start_dashboard
            ;;
        *)
            print_error "Unknown service: $service"
            print_status "Available services: postgresql, redis, password-reset, backend, dashboard"
            exit 1
            ;;
    esac
}

# Function to set environment configuration
set_environment() {
    local env=${1:-development}
    
    print_status "Setting up $env environment configuration..."
    
    # Check if environment-specific config exists
    if [ -f "backend/.env.$env" ]; then
        cp "backend/.env.$env" "backend/.env"
        print_success "$env environment configuration activated"
    else
        print_warning "No .env.$env file found, using existing .env configuration"
    fi
}

# Main execution
main() {
    # Check for environment-specific start
    if [ "$1" = "dev" ] || [ "$1" = "development" ]; then
        set_environment "development"
        shift  # Remove the environment argument
    elif [ "$1" = "prod" ] || [ "$1" = "production" ]; then
        set_environment "production"
        shift  # Remove the environment argument
    fi
    
    # Check for service-specific start
    if [ ! -z "$1" ]; then
        print_status "Starting $1 service..."
        echo ""
        
        if start_service "$1"; then
            echo ""
            print_success "🎉 $1 service started successfully!"
            
            # Show service-specific info
            case $1 in
                "postgresql"|"postgres")
                    echo "🌐 PostgreSQL: localhost:5432"
                    ;;
                "redis")
                    echo "🌐 Redis: localhost:6379"
                    ;;
                "password-reset"|"reset-app")
                    echo "🌐 Password Reset App: Built and ready"
                    echo "🌐 Reset Page: https://zivohealth.ai/reset-password"
                    ;;
                "backend")
                    echo "🌐 Backend API: http://localhost:8000"
                    echo "🌐 API Docs: http://localhost:8000/docs"
                    echo "🌐 Password Reset App: Built and ready"
                    ;;
                "dashboard")
                    echo "🌐 Dashboard: http://localhost:3000"
                    ;;
            esac
        else
            print_error "❌ Failed to start $1 service!"
            exit 1
        fi
        
        echo ""
        echo "💡 Tip: You can start all services with:"
        echo "   ./scripts/start-all.sh"
        return
    fi
    
    print_status "Starting all ZivoHealth services in sequence..."
    echo ""
    
    # Step 1: Start PostgreSQL
    if ! start_postgresql; then
        print_error "Failed to start PostgreSQL, aborting..."
        exit 1
    fi
    echo ""
    
    # Step 2: Start Redis
    if ! start_redis; then
        print_error "Failed to start Redis, aborting..."
        exit 1
    fi
    echo ""
    
    # Step 3: Build Password Reset App
    build_password_reset_app
    echo ""
    
    # Step 4: Start Backend
    if ! start_backend; then
        print_error "Failed to start Backend, aborting..."
        exit 1
    fi
    echo ""
    
    # Step 5: Start Dashboard
    start_dashboard
    echo ""
    
    # Final status
    print_success "🎉 ZivoHealth services startup complete!"
    echo ""
    echo "Service Status:"
    echo "==============="
    
    # Check all services
    if check_service "PostgreSQL" "5432"; then
        echo "✅ PostgreSQL: Running on port 5432"
    else
        echo "❌ PostgreSQL: Not running"
    fi
    
    if check_service "Redis" "6379"; then
        echo "✅ Redis: Running on port 6379"
    else
        echo "❌ Redis: Not running"
    fi
    
    if check_service "Backend" "8000"; then
        echo "✅ Backend: Running on port 8000"
    else
        echo "❌ Backend: Not running"
    fi
    
    if check_service "Dashboard" "3000"; then
        echo "✅ Dashboard: Running on port 3000"
    else
        echo "⏳ Dashboard: Starting... (check http://localhost:3000)"
    fi
    
    echo ""
    echo "🌐 Access URLs:"
    echo "  • Backend API: http://localhost:8000"
    echo "  • API Docs: http://localhost:8000/docs"
    echo "  • Dashboard: http://localhost:3000"
    echo ""
    echo "📝 To stop all services: ./scripts/stop-all.sh"
    echo "🔄 To restart all services: ./scripts/restart-all.sh"
    echo "💡 To start with specific environment: ./scripts/start-all.sh [dev|prod]"
    echo "💡 To start individual services: ./scripts/start-all.sh [dev|prod] [service]"
    echo "   Available services: postgresql, redis, password-reset, backend, dashboard"
    echo "📊 To view dashboard logs: ./backend/scripts/logs_dashboard.sh"
}

# Run main function
main "$@" 