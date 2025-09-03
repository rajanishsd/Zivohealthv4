#!/bin/bash

# Worker Management Script for ZivoHealth Platform
# Handles stuck workers, multiple uploads, and worker monitoring

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="/opt/zivohealth/docker-compose.yml"
CONTAINER_NAME="api"

echo -e "${BLUE}=== ZivoHealth Worker Management Script ===${NC}"

# Function to check if we're running on EC2
check_environment() {
    if [ -f "$COMPOSE_FILE" ]; then
        echo -e "${GREEN}✓ Running on EC2 environment${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Running in local environment${NC}"
        COMPOSE_FILE="docker-compose.yml"
        return 1
    fi
}

# Function to check worker process status
check_worker_status() {
    echo -e "${BLUE}1. Checking worker process status...${NC}"
    
    # Check if worker process is running
    WORKER_PROCESSES=$(sudo docker compose -f "$COMPOSE_FILE" exec -T "$CONTAINER_NAME" ps aux | grep worker_process || true)
    
    if [ -n "$WORKER_PROCESSES" ]; then
        echo -e "${YELLOW}⚠ Found running worker processes:${NC}"
        echo "$WORKER_PROCESSES"
        return 1
    else
        echo -e "${GREEN}✓ No worker processes currently running${NC}"
        return 0
    fi
}

# Function to check worker logs
check_worker_logs() {
    echo -e "${BLUE}2. Checking worker logs...${NC}"
    
    # Check worker.log file
    if sudo docker compose -f "$COMPOSE_FILE" exec -T "$CONTAINER_NAME" test -f worker.log; then
        echo -e "${YELLOW}Recent worker.log entries:${NC}"
        sudo docker compose -f "$COMPOSE_FILE" exec -T "$CONTAINER_NAME" tail -n 20 worker.log
    else
        echo -e "${YELLOW}No worker.log file found${NC}"
    fi
    
    # Check API logs for worker activity
    echo -e "${YELLOW}Recent API logs with worker activity:${NC}"
    sudo docker compose -f "$COMPOSE_FILE" logs --tail 50 "$CONTAINER_NAME" | grep -E "(SmartWorker|Worker|Aggregation)" || echo "No worker activity found in recent logs"
}

# Function to check pending aggregation entries
check_pending_entries() {
    echo -e "${BLUE}3. Checking pending aggregation entries...${NC}"
    
    sudo docker compose -f "$COMPOSE_FILE" exec -T "$CONTAINER_NAME" python -c "
from app.db.session import SessionLocal
from app.crud.vitals import VitalsCRUD
from app.crud.nutrition import nutrition_data as NutritionCRUD
try:
    db = SessionLocal()
    vitals_pending = len(VitalsCRUD.get_pending_aggregation_entries(db, limit=1000))
    nutrition_pending = len(NutritionCRUD.get_pending_aggregation_entries(db, limit=1000))
    print(f'Vitals pending: {vitals_pending}')
    print(f'Nutrition pending: {nutrition_pending}')
    print(f'Total pending: {vitals_pending + nutrition_pending}')
    db.close()
except Exception as e:
    print(f'Error checking pending entries: {e}')
" || echo "Failed to check pending entries"
}

# Function to kill stuck worker processes
kill_stuck_workers() {
    echo -e "${BLUE}4. Killing stuck worker processes...${NC}"
    
    # Kill worker processes
    KILLED=$(sudo docker compose -f "$COMPOSE_FILE" exec -T "$CONTAINER_NAME" pkill -f worker_process || true)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Killed stuck worker processes${NC}"
    else
        echo -e "${YELLOW}No worker processes to kill${NC}"
    fi
    
    # Wait a moment for processes to terminate
    sleep 2
    
    # Verify they're gone
    REMAINING=$(sudo docker compose -f "$COMPOSE_FILE" exec -T "$CONTAINER_NAME" ps aux | grep worker_process || true)
    if [ -n "$REMAINING" ]; then
        echo -e "${RED}⚠ Some worker processes still running, force killing...${NC}"
        sudo docker compose -f "$COMPOSE_FILE" exec -T "$CONTAINER_NAME" pkill -9 -f worker_process || true
    fi
}

# Function to reset worker state
reset_worker_state() {
    echo -e "${BLUE}5. Resetting worker state...${NC}"
    
    # Kill any existing workers
    kill_stuck_workers
    
    # Clear worker log file
    sudo docker compose -f "$COMPOSE_FILE" exec -T "$CONTAINER_NAME" rm -f worker.log || true
    
    # Restart API container to clear any in-memory state
    echo -e "${YELLOW}Restarting API container to clear worker state...${NC}"
    sudo docker compose -f "$COMPOSE_FILE" restart "$CONTAINER_NAME"
    
    # Wait for container to be ready
    echo -e "${YELLOW}Waiting for API container to be ready...${NC}"
    sleep 10
    
    # Check if container is healthy
    HEALTH_STATUS=$(sudo docker compose -f "$COMPOSE_FILE" ps "$CONTAINER_NAME" --format "table {{.Status}}" | tail -n 1)
    echo -e "${GREEN}✓ API container status: $HEALTH_STATUS${NC}"
}

# Function to start worker process
start_worker() {
    echo -e "${BLUE}6. Starting worker process...${NC}"
    
    # Check if there's pending work first
    PENDING_COUNT=$(sudo docker compose -f "$COMPOSE_FILE" exec -T "$CONTAINER_NAME" python -c "
from app.db.session import SessionLocal
from app.crud.vitals import VitalsCRUD
from app.crud.nutrition import nutrition_data as NutritionCRUD
try:
    db = SessionLocal()
    vitals_pending = len(VitalsCRUD.get_pending_aggregation_entries(db, limit=1))
    nutrition_pending = len(NutritionCRUD.get_pending_aggregation_entries(db, limit=1))
    print(vitals_pending + nutrition_pending)
    db.close()
except:
    print(0)
" 2>/dev/null || echo "0")
    
    if [ "$PENDING_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}Found $PENDING_COUNT pending entries, starting worker...${NC}"
        
        # Start worker process in background
        sudo docker compose -f "$COMPOSE_FILE" exec -T "$CONTAINER_NAME" python aggregation/worker_process.py > /tmp/worker_output.log 2>&1 &
        WORKER_PID=$!
        
        echo -e "${GREEN}✓ Worker process started with PID: $WORKER_PID${NC}"
        echo -e "${YELLOW}Worker output will be logged to /tmp/worker_output.log${NC}"
        
        # Wait a moment and check if it's still running
        sleep 3
        if kill -0 $WORKER_PID 2>/dev/null; then
            echo -e "${GREEN}✓ Worker process is running successfully${NC}"
        else
            echo -e "${RED}⚠ Worker process failed to start${NC}"
            echo -e "${YELLOW}Checking worker output:${NC}"
            tail -n 20 /tmp/worker_output.log || true
        fi
    else
        echo -e "${GREEN}✓ No pending work found - worker not needed${NC}"
    fi
}

# Function to monitor worker in real-time
monitor_worker() {
    echo -e "${BLUE}7. Monitoring worker activity (Ctrl+C to stop)...${NC}"
    
    # Monitor API logs for worker activity
    sudo docker compose -f "$COMPOSE_FILE" logs -f "$CONTAINER_NAME" | grep -E "(SmartWorker|Worker|Aggregation)" || true
}

# Function to handle multiple uploads scenario
handle_multiple_uploads() {
    echo -e "${BLUE}8. Handling multiple uploads scenario...${NC}"
    
    # Kill any existing workers to prevent conflicts
    kill_stuck_workers
    
    # Check pending entries
    check_pending_entries
    
    # Start a fresh worker process
    start_worker
    
    # Monitor for a short period
    echo -e "${YELLOW}Monitoring worker for 30 seconds...${NC}"
    timeout 30s sudo docker compose -f "$COMPOSE_FILE" logs -f "$CONTAINER_NAME" | grep -E "(SmartWorker|Worker|Aggregation)" || true
    
    # Final status check
    echo -e "${BLUE}Final status check:${NC}"
    check_worker_status
    check_pending_entries
}

# Function to show database connection status
check_db_connections() {
    echo -e "${BLUE}9. Checking database connections...${NC}"
    
    sudo docker compose -f "$COMPOSE_FILE" exec -T "$CONTAINER_NAME" python -c "
from app.db.session import engine
try:
    print(f'Database pool size: {engine.pool.size()}')
    print(f'Database checked out: {engine.pool.checkedout()}')
    print(f'Database overflow: {engine.pool.overflow()}')
    print(f'Database invalid: {engine.pool.invalid()}')
except Exception as e:
    print(f'Error checking database connections: {e}')
" || echo "Failed to check database connections"
}

# Function to show comprehensive status
show_status() {
    echo -e "${BLUE}=== Comprehensive Worker Status ===${NC}"
    check_worker_status
    check_worker_logs
    check_pending_entries
    check_db_connections
}

# Function to show help
show_help() {
    echo -e "${BLUE}Usage: $0 [COMMAND]${NC}"
    echo ""
    echo "Commands:"
    echo "  status          - Show comprehensive worker status"
    echo "  check           - Check worker status and pending entries"
    echo "  kill            - Kill stuck worker processes"
    echo "  reset           - Reset worker state (restart API container)"
    echo "  start           - Start worker process"
    echo "  monitor         - Monitor worker activity in real-time"
    echo "  multiple        - Handle multiple uploads scenario"
    echo "  db-connections  - Check database connection status"
    echo "  help            - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 status       - Check current worker status"
    echo "  $0 multiple     - Handle stuck worker from multiple uploads"
    echo "  $0 reset        - Emergency reset of worker state"
}

# Main script logic
main() {
    check_environment
    
    case "${1:-help}" in
        "status")
            show_status
            ;;
        "check")
            check_worker_status
            check_pending_entries
            ;;
        "kill")
            kill_stuck_workers
            ;;
        "reset")
            reset_worker_state
            ;;
        "start")
            start_worker
            ;;
        "monitor")
            monitor_worker
            ;;
        "multiple")
            handle_multiple_uploads
            ;;
        "db-connections")
            check_db_connections
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Run main function with all arguments
main "$@"
