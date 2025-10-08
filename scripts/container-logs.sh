#!/usr/bin/env bash
set -euo pipefail

# ZivoHealth Container Logs Checker
# Comprehensive script to check all container logs including server.log and dashboard.log
# Usage: container-logs.sh [service] [options]

SERVICE="${1:-all}"
TAIL_LINES=50
FOLLOW=false
SHOW_SIZES=false
SHOW_ERRORS=false
QUICK=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tail) TAIL_LINES="$2"; shift 2 ;;
    --follow) FOLLOW=true; shift ;;
    --sizes) SHOW_SIZES=true; shift ;;
    --errors) SHOW_ERRORS=true; shift ;;
    --quick) QUICK=true; shift ;;
    -h|--help) 
      echo "ZivoHealth Container Logs Checker"
      echo "===================================="
      echo "Usage: $0 [service] [options]"
      echo ""
      echo "Services:"
      echo "  api              Main backend API"
      echo "  reminders        Reminders API"
      echo "  reminders-worker Reminders Celery worker"
      echo "  reminders-beat   Reminders Celery scheduler"
      echo "  dashboard        React dashboard"
      echo "  caddy           Reverse proxy"
      echo "  redis           Cache server"
      echo "  rabbitmq        Message broker"
      echo "  all             All services (default)"
      echo ""
      echo "Options:"
      echo "  --tail LINES     Number of lines to show (default: 50)"
      echo "  --follow         Follow logs in real-time"
      echo "  --sizes          Show log file sizes"
      echo "  --errors         Show only error lines"
      echo "  --quick          Quick overview only"
      echo "  -h, --help       Show this help"
      exit 0 ;;
    *) SERVICE="$1"; shift ;;
  esac
done

# Get instance ID from Terraform
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TERRAFORM_DIR="$ROOT_DIR/infra/terraform"

if command -v terraform >/dev/null 2>&1; then
  pushd "$TERRAFORM_DIR" >/dev/null
  INSTANCE_ID="$(AWS_PROFILE="zivohealth" AWS_REGION="us-east-1" terraform output -raw ec2_instance_id 2>/dev/null || echo "")"
  popd >/dev/null
fi

if [[ -z "$INSTANCE_ID" ]]; then
  echo "Error: Could not get instance ID from Terraform"
  exit 1
fi

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_section() {
    echo -e "${CYAN}📋 $1${NC}"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
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

# Execute SSM command
run_ssm() {
    local cmd="$1"
    aws ssm start-session \
        --profile "zivohealth" \
        --region "us-east-1" \
        --target "$INSTANCE_ID" \
        --document-name AWS-StartInteractiveCommand \
        --parameters "command=[\"$cmd\"]" 2>/dev/null || echo "Command failed"
}

# Show container status overview
show_container_status() {
    print_header "🐳 Container Status Overview"
    
    local status_command="sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
    run_ssm "$status_command"
    echo ""
}

# Show log file sizes
show_log_sizes() {
    print_header "📊 Log File Sizes"
    
    local sizes_command="sudo find /var/lib/docker/containers -name '*-json.log' -exec ls -lh {} \; | sort -k5 -hr"
    run_ssm "$sizes_command"
    echo ""
}

# Show Docker system info
show_docker_info() {
    print_header "🐳 Docker System Information"
    
    local info_command="sudo docker system df"
    run_ssm "$info_command"
    echo ""
}

# Check specific service logs
check_service_logs() {
    local service="$1"
    local container_name=""
    local app_log=""
    local service_display=""
    
    case "$service" in
        "api")
            container_name="zivohealth-api"
            app_log="/app/logs/server.log"
            service_display="Main Backend API"
            ;;
        "reminders")
            container_name="zivohealth-reminders"
            app_log="/app/logs/reminders-api.log"
            service_display="Reminders API"
            ;;
        "reminders-worker")
            container_name="zivohealth-reminders-worker"
            app_log="/app/logs/reminders-worker.log"
            service_display="Reminders Worker"
            ;;
        "reminders-beat")
            container_name="zivohealth-reminders-beat"
            app_log="/app/logs/reminders-beat.log"
            service_display="Reminders Beat Scheduler"
            ;;
        "dashboard")
            container_name="zivohealth-dashboard"
            app_log="/app/logs/dashboard.log"
            service_display="React Dashboard"
            ;;
        "caddy")
            container_name="zivohealth-caddy"
            service_display="Caddy Reverse Proxy"
            ;;
        "redis")
            container_name="zivohealth-redis"
            service_display="Redis Cache Server"
            ;;
        "rabbitmq")
            container_name="zivohealth-rabbitmq"
            service_display="RabbitMQ Message Broker"
            ;;
        *)
            print_error "Unknown service: $service"
            return 1
            ;;
    esac
    
    print_section "$service_display"
    
    # Show log file size if requested
    if [[ "$SHOW_SIZES" == "true" ]]; then
        print_info "Log file size:"
        run_ssm "sudo docker inspect $container_name | grep LogPath | cut -d'\"' -f4 | xargs sudo ls -lh"
        echo ""
    fi
    
    # Show container logs
    if [[ "$SHOW_ERRORS" == "true" ]]; then
        print_info "Error logs only:"
        run_ssm "sudo docker logs $container_name 2>&1 | grep -i error | tail -$TAIL_LINES"
    else
        print_info "Container logs (last $TAIL_LINES lines):"
        if [[ "$FOLLOW" == "true" ]]; then
            run_ssm "sudo docker logs -f --tail $TAIL_LINES $container_name"
        else
            run_ssm "sudo docker logs --tail $TAIL_LINES $container_name"
        fi
    fi
    
    # Show application logs if available
    if [[ -n "$app_log" ]]; then
        echo ""
        print_info "Application log ($app_log):"
        if [[ "$FOLLOW" == "true" ]]; then
            run_ssm "sudo docker exec $container_name tail -f -n $TAIL_LINES $app_log 2>/dev/null || echo 'Application log not found'"
        else
            run_ssm "sudo docker exec $container_name tail -n $TAIL_LINES $app_log 2>/dev/null || echo 'Application log not found'"
        fi
    fi
}

# Check Celery status for reminders services
check_celery_status() {
    print_section "Celery Task Queue Status"
    
    echo "📊 Active tasks:"
    run_ssm "sudo docker exec zivohealth-reminders-worker celery -A app.reminders.celery_app:celery_app inspect active 2>/dev/null || echo 'Cannot get active tasks'"
    echo ""
    
    echo "📊 Scheduled tasks:"
    run_ssm "sudo docker exec zivohealth-reminders-beat celery -A app.reminders.celery_app:celery_app inspect scheduled 2>/dev/null || echo 'Cannot get scheduled tasks'"
    echo ""
    
    echo "📊 Worker stats:"
    run_ssm "sudo docker exec zivohealth-reminders-worker celery -A app.reminders.celery_app:celery_app inspect stats 2>/dev/null || echo 'Cannot get worker stats'"
}

# Check RabbitMQ status
check_rabbitmq_status() {
    print_section "RabbitMQ Message Broker Status"
    
    echo "📊 RabbitMQ status:"
    run_ssm "sudo docker exec zivohealth-rabbitmq rabbitmqctl status 2>/dev/null || echo 'Cannot get RabbitMQ status'"
    echo ""
    
    echo "📊 Queue information:"
    run_ssm "sudo docker exec zivohealth-rabbitmq rabbitmqctl list_queues 2>/dev/null || echo 'Cannot get queue information'"
}

# Quick overview
show_quick_overview() {
    print_header "🚀 Quick Overview"
    
    show_container_status
    
    if [[ "$SHOW_SIZES" == "true" ]]; then
        show_log_sizes
    fi
    
    print_info "Key services status:"
    run_ssm "sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E '(api|reminders|dashboard)'"
}

# Check all services
check_all_services() {
    show_container_status
    
    if [[ "$SHOW_SIZES" == "true" ]]; then
        show_log_sizes
    fi
    
    if [[ "$QUICK" == "false" ]]; then
        show_docker_info
    fi
    
    # Check main services
    check_service_logs "api"
    check_service_logs "reminders"
    check_service_logs "reminders-worker"
    check_service_logs "reminders-beat"
    check_service_logs "dashboard"
    check_service_logs "caddy"
    check_service_logs "redis"
    check_service_logs "rabbitmq"
    
    # Show additional status for reminders services
    if [[ "$SHOW_ERRORS" == "false" && "$QUICK" == "false" ]]; then
        check_celery_status
        check_rabbitmq_status
    fi
}

# Main execution
main() {
    echo -e "${GREEN}🔍 ZivoHealth Container Logs Checker${NC}"
    echo "Instance: $INSTANCE_ID"
    echo "Service: $SERVICE"
    echo "Tail lines: $TAIL_LINES"
    echo "Follow: $FOLLOW"
    echo "Show sizes: $SHOW_SIZES"
    echo "Show errors only: $SHOW_ERRORS"
    echo "Quick mode: $QUICK"
    echo ""
    
    case "$SERVICE" in
        "all")
            if [[ "$QUICK" == "true" ]]; then
                show_quick_overview
            else
                check_all_services
            fi
            ;;
        "api"|"reminders"|"reminders-worker"|"reminders-beat"|"dashboard"|"caddy"|"redis"|"rabbitmq")
            check_service_logs "$SERVICE"
            ;;
        *)
            print_error "Unknown service: $SERVICE"
            print_info "Available services: api, reminders, reminders-worker, reminders-beat, dashboard, caddy, redis, rabbitmq, all"
            exit 1
            ;;
    esac
    
    print_success "Log check completed!"
    print_info "🕐 Completed at: $(date)"
}

# Run main function
main "$@"
