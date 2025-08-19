#!/bin/bash

# RxNorm Embedder Runner Script
# =============================
#
# This script provides easy access to common RxNorm embedder operations
# including setup, processing, and testing.

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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

# Function to check if Python is available
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed or not in PATH"
        exit 1
    fi
    print_success "Python 3 found: $(python3 --version)"
}

# Function to check if required files exist
check_files() {
    local missing_files=()
    
    if [[ ! -f "rxnorm_embedder.py" ]]; then
        missing_files+=("rxnorm_embedder.py")
    fi
    
    if [[ ! -f "config.py" ]]; then
        missing_files+=("config.py")
    fi
    
    if [[ ! -f "requirements.txt" ]]; then
        missing_files+=("requirements.txt")
    fi
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        print_error "Missing required files: ${missing_files[*]}"
        exit 1
    fi
    
    print_success "All required files found"
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing dependencies..."
    
    if [[ -f "requirements.txt" ]]; then
        python3 -m pip install -r requirements.txt
        print_success "Dependencies installed successfully"
    else
        print_error "requirements.txt not found"
        exit 1
    fi
}

# Function to setup database
setup_database() {
    print_status "Setting up database tables..."
    python3 rxnorm_embedder.py --setup-db
    print_success "Database setup completed"
}

# Function to process RxNorm data
process_rxnorm() {
    local max_codes="$1"
    
    if [[ -n "$max_codes" ]]; then
        print_status "Processing RxNorm data (max: $max_codes codes)..."
        python3 rxnorm_embedder.py --process-rxnorm --max-codes "$max_codes"
    else
        print_status "Processing all RxNorm data..."
        python3 rxnorm_embedder.py --process-rxnorm
    fi
    
    print_success "RxNorm processing completed"
}

# Function to search RxNorm codes
search_rxnorm() {
    local query="$1"
    
    if [[ -z "$query" ]]; then
        print_error "Search query is required"
        echo "Usage: $0 search <query>"
        exit 1
    fi
    
    print_status "Searching for: $query"
    python3 rxnorm_embedder.py --search "$query"
}

# Function to show statistics
show_stats() {
    print_status "Showing RxNorm embedder statistics..."
    python3 rxnorm_embedder.py --stats
}

# Function to run tests
run_tests() {
    print_status "Running RxNorm embedder tests..."
    python3 test_rxnorm_embedder.py
}

# Function to show help
show_help() {
    echo "RxNorm Embedder Runner Script"
    echo "============================="
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  setup              - Setup database tables"
    echo "  install            - Install dependencies"
    echo "  test               - Run tests"
    echo "  process [max]      - Process RxNorm data (optional max codes)"
    echo "  search <query>     - Search for RxNorm codes"
    echo "  stats              - Show statistics"
    echo "  full-setup         - Complete setup (install + setup + test)"
    echo "  help               - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 setup"
    echo "  $0 process 10000"
    echo "  $0 search 'aspirin'"
    echo "  $0 full-setup"
}

# Main script logic
main() {
    local command="$1"
    local arg1="$2"
    local arg2="$3"
    
    # Check Python availability
    check_python
    
    # Check required files
    check_files
    
    case "$command" in
        "setup")
            setup_database
            ;;
        "install")
            install_dependencies
            ;;
        "test")
            run_tests
            ;;
        "process")
            process_rxnorm "$arg1"
            ;;
        "search")
            search_rxnorm "$arg1"
            ;;
        "stats")
            show_stats
            ;;
        "full-setup")
            print_status "Running full setup..."
            install_dependencies
            setup_database
            run_tests
            print_success "Full setup completed successfully"
            ;;
        "help"|"--help"|"-h"|"")
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@" 