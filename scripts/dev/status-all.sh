#!/bin/bash

# ZivoHealth Master Service Status Checker
# Checks status of all services: PostgreSQL, Redis, Backend, Dashboard

echo "📊 ZivoHealth Service Status Monitor"
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
            return 0
        fi
    elif [ ! -z "$command" ]; then
        if pgrep -f "$command" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Function to get process info for a port
get_port_info() {
    local port=$1
    lsof -ti:$port 2>/dev/null | head -1
}

# Function to check PostgreSQL status
check_postgresql() {
    echo "🐘 PostgreSQL Database"
    echo "====================="
    
    if check_service "PostgreSQL" "5433"; then
        local pid=$(get_port_info "5433")
        echo "✅ Status: Running"
        echo "📍 Port: 5433"
        echo "🔢 PID: $pid"
        
        # Show data directory info (consistent with infrastructure script)
        local data_dir_status="System default"
        if [ -f "backend/data/postgres.pid" ]; then
            local stored_pid=$(cat backend/data/postgres.pid 2>/dev/null || echo "")
            # DEBUG: echo "DEBUG: stored_pid='$stored_pid' pid='$pid'"
            if [[ "$stored_pid" = "$pid" ]] && [[ -d "backend/data/postgres" ]]; then
                data_dir_status="backend/data/postgres (local)"
                echo "📁 Data Directory: $data_dir_status"
                echo "📋 PID File: backend/data/postgres.pid (PID: $stored_pid)"
            else
                echo "📁 Data Directory: $data_dir_status"
            fi
        else
            echo "📁 Data Directory: $data_dir_status"
        fi
        
        # Try to connect and get version
        if command -v psql &> /dev/null; then
            local version=$(psql -h localhost -p 5433 -U rajanishsd -d zivohealth -t -c "SELECT version();" 2>/dev/null | head -1 | xargs || echo "Unable to connect")
            echo "📋 Version: $version"
            
            # Get database info
            local db_size=$(psql -h localhost -p 5433 -U rajanishsd -d zivohealth -t -c "SELECT pg_size_pretty(pg_database_size('zivohealth'));" 2>/dev/null | xargs || echo "Unknown")
            echo "💾 Database Size: $db_size"
            
            local connections=$(psql -h localhost -p 5433 -U rajanishsd -d zivohealth -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null | xargs || echo "Unknown")
            echo "🔗 Active Connections: $connections"
        fi
    else
        echo "❌ Status: Not Running"
        echo "📍 Port: 5433 (not in use)"
        
        # Check if data directory exists
        if [ -d "backend/data/postgres" ]; then
            echo "📁 Data Directory: backend/data/postgres (initialized)"
        else
            echo "📁 Data Directory: Not initialized"
        fi
    fi
    echo ""
}

# Function to check Redis status
check_redis() {
    echo "🔴 Redis Cache Server"
    echo "===================="
    
    if check_service "Redis" "6379"; then
        local pid=$(get_port_info "6379")
        echo "✅ Status: Running"
        echo "📍 Port: 6379"
        echo "🔢 PID: $pid"
        
        # Get Redis info
        if command -v redis-cli &> /dev/null; then
            local redis_version=$(redis-cli info server 2>/dev/null | grep "redis_version" | cut -d: -f2 | tr -d '\r' || echo "Unknown")
            echo "📋 Version: $redis_version"
            
            local redis_memory=$(redis-cli info memory 2>/dev/null | grep "used_memory_human" | cut -d: -f2 | tr -d '\r' || echo "Unknown")
            echo "💾 Memory Usage: $redis_memory"
            
            local redis_keys=$(redis-cli dbsize 2>/dev/null || echo "Unknown")
            echo "🔑 Total Keys: $redis_keys"
            
            local redis_dir=$(redis-cli config get dir 2>/dev/null | tail -1 || echo "Unknown")
            echo "📁 Data Directory: $redis_dir"
        fi
    else
        echo "❌ Status: Not Running"
        echo "📍 Port: 6379 (not in use)"
    fi
    echo ""
}

# Function to check Backend status
check_backend() {
    echo "🚀 FastAPI Backend Server"
    echo "========================="
    
    if check_service "Backend" "8000"; then
        local pid=$(get_port_info "8000")
        echo "✅ Status: Running"
        echo "📍 Port: 8000"
        echo "🔢 PID: $pid"
        
        # Test health endpoint with timeout
        echo "🔍 Testing health endpoint (5s timeout)..."
        if timeout 5 curl -s --max-time 5 --connect-timeout 3 http://localhost:8000/health > /dev/null 2>&1; then
            echo "💚 Health Check: Passed"
            
            # Get API info with timeout
            local api_response=$(timeout 3 curl -s --max-time 3 --connect-timeout 2 http://localhost:8000/health 2>/dev/null || echo "{}")
            echo "🌐 API Endpoint: http://localhost:8000"
            echo "📚 Documentation: http://localhost:8000/docs"
            
            # Check if specific endpoints are responding with timeout
            echo "🔍 Testing system health API (3s timeout)..."
            if timeout 3 curl -s --max-time 3 --connect-timeout 2 http://localhost:8000/api/v1/performance/system/health > /dev/null 2>&1; then
                echo "📊 System Health API: ✅ Available"
            else
                echo "📊 System Health API: ❌ Not responding or timeout"
            fi
            
            echo "🔍 Testing performance API (3s timeout)..."
            if timeout 3 curl -s --max-time 3 --connect-timeout 2 http://localhost:8000/api/v1/performance/http/overview > /dev/null 2>&1; then
                echo "📈 Performance API: ✅ Available"
            else
                echo "📈 Performance API: ❌ Not responding or timeout"
            fi
        else
            echo "💔 Health Check: Failed or timeout (server may be hung)"
            echo "⚠️  Backend process is running but not responding"
        fi
    else
        echo "❌ Status: Not Running"
        echo "📍 Port: 8000 (not in use)"
    fi
    echo ""
}

# Function to check Dashboard status
check_dashboard() {
    echo "📊 React Dashboard"
    echo "=================="
    
    if check_service "Dashboard" "3000"; then
        local pid=$(get_port_info "3000")
        echo "✅ Status: Running"
        echo "📍 Port: 3000"
        echo "🔢 PID: $pid"
        
        # Test dashboard endpoint with timeout
        echo "🔍 Testing dashboard endpoint (5s timeout)..."
        if timeout 5 curl -s --max-time 5 --connect-timeout 3 http://localhost:3000 > /dev/null 2>&1; then
            echo "💚 Health Check: Passed"
            echo "🌐 Dashboard URL: http://localhost:3000"
            
            # Check if it's actually serving React content with timeout
            local response=$(timeout 3 curl -s --max-time 3 --connect-timeout 2 http://localhost:3000 2>/dev/null || echo "")
            if echo "$response" | grep -q "react\|React" > /dev/null 2>&1; then
                echo "⚛️  React App: ✅ Active"
            else
                echo "⚛️  React App: ❓ Status unclear"
            fi
        else
            echo "💔 Health Check: Failed or timeout (may still be starting or hung)"
        fi
    else
        echo "❌ Status: Not Running"
        echo "📍 Port: 3000 (not in use)"
    fi
    echo ""
}

# Function to show overall system status
show_overall_status() {
    echo "🎯 Overall System Status"
    echo "========================"
    
    local services_running=0
    local total_services=4
    
    if check_service "PostgreSQL" "5433"; then
        echo "✅ PostgreSQL"
        services_running=$((services_running + 1))
    else
        echo "❌ PostgreSQL"
    fi
    
    if check_service "Redis" "6379"; then
        echo "✅ Redis"
        services_running=$((services_running + 1))
    else
        echo "❌ Redis"
    fi
    
    if check_service "Backend" "8000"; then
        echo "✅ Backend"
        services_running=$((services_running + 1))
    else
        echo "❌ Backend"
    fi
    
    if check_service "Dashboard" "3000"; then
        echo "✅ Dashboard"
        services_running=$((services_running + 1))
    else
        echo "❌ Dashboard"
    fi
    
    echo ""
    echo "📈 Services: $services_running/$total_services running"
    
    if [ $services_running -eq $total_services ]; then
        print_success "🎉 All services are running!"
    elif [ $services_running -eq 0 ]; then
        print_error "💀 No services are running"
    else
        print_warning "⚠️  Some services are not running"
    fi
    
    echo ""
    echo "🛠️  Available Commands:"
echo "  • Start all: ./scripts/start-all.sh"
echo "  • Stop all: ./scripts/stop-all.sh"
echo "  • Restart all: ./scripts/restart-all.sh"
echo "  • Check status: ./scripts/status-all.sh"
}

# Main execution
main() {
    local start_time=$(date +%s)
    
    check_postgresql
    check_redis
    check_backend
    check_dashboard
    show_overall_status
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo ""
    echo "⏱️  Status check completed in ${duration}s"
    echo "🕐 Last updated: $(date)"
}

# Run main function
main "$@" 