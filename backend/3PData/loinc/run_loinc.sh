#!/bin/bash

# LOINC Embedder Runner Script
# ============================
# 
# This script provides convenient commands for running the LOINC embedder
# with OpenAI text-embedding-3-large model.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to load environment variables from backend .env file
load_env_file() {
    # Look for .env file in backend directory (two levels up)
    local env_file="../../.env"
    
    if [[ -f "$env_file" ]]; then
        print_info "Loading environment variables from $env_file"
        
        # Source the .env file, but only export the OpenAI API key
        # Use grep to avoid issues with arrays and complex values
        if grep -q "OPENAI_API_KEY=" "$env_file"; then
            export OPENAI_API_KEY=$(grep "OPENAI_API_KEY=" "$env_file" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
            print_success "OpenAI API key loaded from .env file"
        fi
    else
        print_info "No .env file found at $env_file"
    fi
}

# Function to check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check if LOINC CSV file exists
    if [[ ! -f "../data/lonic/LoincTableCore.csv" ]]; then
        print_error "LoincTableCore.csv not found in ../data/lonic/ directory"
        print_info "Please ensure the LOINC CSV file is in the 3PData/data/lonic directory"
        exit 1
    fi
    
    # Check if Python dependencies are installed
    if ! python -c "import pandas, sqlalchemy, transformers, torch" 2>/dev/null; then
        print_error "Required Python packages not installed"
        print_info "Please install dependencies: pip install -r requirements.txt"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to setup database
setup_database() {
    print_info "Setting up database for LOINC embeddings..."
    python loinc_embedder.py --setup-db
    print_success "Database setup completed"
}

# Function to run tests
run_tests() {
    print_info "Running LOINC embedder tests..."
    python test_loinc_embedder.py
}

# Function to process LOINC codes
process_loinc() {
    local max_codes=$1
    
    if [[ -n "$max_codes" ]]; then
        print_info "Processing first $max_codes LOINC codes..."
        python loinc_embedder.py --process-loinc --max-codes "$max_codes"
    else
        print_warning "Processing ALL LOINC codes (~104K codes)"
        read -p "Are you sure you want to continue? (y/N): " confirm
        if [[ $confirm =~ ^[Yy]$ ]]; then
            python loinc_embedder.py --process-loinc
        else
            print_info "Processing cancelled"
            return 1
        fi
    fi
    
    print_success "LOINC processing completed"
}

# Function to search LOINC codes
search_loinc() {
    local query=$1
    
    if [[ -z "$query" ]]; then
        print_info "Starting interactive search mode..."
        python loinc_search.py --interactive
    else
        print_info "Searching for: '$query'"
        python loinc_search.py "$query"
    fi
}

# Function to show statistics
show_stats() {
    print_info "Showing database statistics..."
    python loinc_embedder.py --stats
}

# Function to show help
show_help() {
    echo "LOINC Embedder Runner Script"
    echo "============================"
    echo
    echo "Usage: $0 [command] [options]"
    echo
    echo "Commands:"
    echo "  setup           Setup database and create custom tables"
    echo "  test            Run test suite to verify installation"
    echo "  process [N]     Process LOINC codes (optionally specify max count)"
    echo "  search [query]  Search LOINC codes (interactive mode if no query)"
    echo "  stats           Show database statistics"
    echo "  help            Show this help message"
    echo
    echo "Examples:"
    echo "  $0 setup                    # Setup database"
    echo "  $0 test                     # Run tests"
    echo "  $0 process 100              # Process first 100 LOINC codes"
    echo "  $0 process                  # Process all LOINC codes (batches of 5000)"
    echo "  $0 search \"blood glucose\"   # Search for blood glucose"
    echo "  $0 search                   # Interactive search mode"
    echo "  $0 stats                    # Show statistics"
    echo
    echo "Prerequisites:"
    echo "  - Have LoincTableCore.csv in ../data/lonic/ directory"
    echo "  - Install Python dependencies: pip install -r requirements.txt"
    echo "  - PostgreSQL running on localhost:5433"
    echo "  - Sufficient disk space for local model (~1GB)"
}

# Function to show cost estimate
show_cost_estimate() {
    print_info "Cost Estimation for LOINC Processing"
    echo "===================================="
    echo
    echo "Model: sentence-transformers/all-MiniLM-L6-v2"
    echo "Cost: $0.00 (local HuggingFace embeddings)"
    echo "Estimated tokens per LOINC code: ~50"
    echo "Total LOINC codes: ~104,673"
    echo
    echo "Estimated total cost: $0.00"
    echo
    echo "Local processing - no API costs!"
}

# Main script logic
main() {
    # Always try to load environment variables first
    load_env_file
    
    case "$1" in
        "setup")
            check_prerequisites
            setup_database
            ;;
        "test")
            check_prerequisites
            run_tests
            ;;
        "process")
            check_prerequisites
            process_loinc "$2"
            ;;
        "search")
            search_loinc "$2"
            ;;
        "stats")
            show_stats
            ;;
        "cost")
            show_cost_estimate
            ;;
        "help" | "-h" | "--help")
            show_help
            ;;
        "")
            print_error "No command specified"
            show_help
            exit 1
            ;;
        *)
            print_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@" 