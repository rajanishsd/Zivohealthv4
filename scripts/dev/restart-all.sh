#!/bin/bash

# ZivoHealth Master Service Restarter
# Stops and then starts all services: PostgreSQL, Redis, Backend, Dashboard

echo "🔄 ZivoHealth Master Service Restarter"
echo "======================================"
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

# Function to restart individual service
restart_service() {
    local service=$1
    
    case $service in
        "dashboard")
            print_status "Restarting dashboard only..."
            if [ -f "backend/scripts/restart_dashboard.sh" ]; then
                ./backend/scripts/restart_dashboard.sh
            else
                print_error "Dashboard restart script not found!"
                exit 1
            fi
            ;;
        "postgresql"|"postgres"|"redis"|"backend")
            print_status "Restarting $service only..."
            # Stop the service
            if [ -f "./scripts/dev/stop-all.sh" ]; then
                ./scripts/dev/stop-all.sh "$service"
            else
                print_error "Stop script not found!"
                exit 1
            fi
            
            echo ""
            print_status "Waiting 3 seconds before restart..."
            sleep 3
            echo ""
            
            # Start the service
            if [ -f "./scripts/dev/start-all.sh" ]; then
                ./scripts/dev/start-all.sh "$service"
            else
                print_error "Start script not found!"
                exit 1
            fi
            ;;
        "password-reset"|"reset-app")
            print_status "Building password reset app..."
            if [ -f "./scripts/dev/start-all.sh" ]; then
                ./scripts/dev/start-all.sh "password-reset"
            else
                print_error "Start script not found!"
                exit 1
            fi
            ;;
        *)
            print_error "Unknown service: $service"
            print_status "Available services: postgresql, redis, password-reset, backend, dashboard"
            exit 1
            ;;
    esac
}

# Main execution
main() {
    # Check for service-specific restart
    if [ ! -z "$1" ]; then
        restart_service "$1"
        return
    fi
    
    print_status "Restarting all ZivoHealth services..."
    echo ""
    
    # Step 1: Stop all services
    print_status "Step 1: Stopping all services..."
    echo "----------------------------------------"
    if [ -f "./scripts/dev/stop-all.sh" ]; then
        ./scripts/dev/stop-all.sh
    else
        print_error "stop-all.sh script not found!"
        exit 1
    fi
    
    echo ""
    echo ""
    
    # Wait a moment for complete shutdown
    print_status "Waiting for services to fully stop..."
    sleep 5
    
    echo ""
    
    # Step 2: Start all services
    print_status "Step 2: Starting all services..."
    echo "----------------------------------------"
    if [ -f "./scripts/dev/start-all.sh" ]; then
        ./scripts/dev/start-all.sh
    else
        print_error "start-all.sh script not found!"
        exit 1
    fi
    
    echo ""
    print_success "🎉 ZivoHealth services restart complete!"
    echo ""
    echo "💡 Tip: You can restart individual services with:"
    echo "   ./scripts/dev/restart-all.sh [service]"
    echo "   Available services: postgresql, redis, password-reset, backend, dashboard"
}

# Run main function
main "$@" 