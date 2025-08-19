#!/bin/bash

# Lab Test LOINC Mapping Runner
# =============================
# This script runs the complete lab test to LOINC code mapping process

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo -e "${BLUE}🔧 Lab Test LOINC Mapping Runner${NC}"
echo "=================================="
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check environment
check_environment() {
    echo -e "${YELLOW}🔍 Checking environment...${NC}"
    
    # Check if we're in the right directory
    if [[ ! -f "$SCRIPT_DIR/loinc_embedder.py" ]]; then
        echo -e "${RED}❌ Error: loinc_embedder.py not found in $SCRIPT_DIR${NC}"
        exit 1
    fi
    
    # Check if Python is available
    if ! command_exists python3; then
        echo -e "${RED}❌ Error: python3 not found${NC}"
        exit 1
    fi
    
    # Check if required Python packages are available
    echo -e "${YELLOW}📦 Checking Python dependencies...${NC}"
    python3 -c "import sqlalchemy, openai, tqdm, pandas" 2>/dev/null || {
        echo -e "${RED}❌ Error: Missing required Python packages${NC}"
        echo "Please install: pip install sqlalchemy openai tqdm pandas"
        exit 1
    }
    
    # Check if OPENAI_API_KEY is set
    if [[ -z "$OPENAI_API_KEY" ]]; then
        echo -e "${YELLOW}⚠️  Warning: OPENAI_API_KEY not set${NC}"
        echo "Please set your OpenAI API key:"
        echo "export OPENAI_API_KEY='your-api-key-here'"
        echo ""
    fi
    
    echo -e "${GREEN}✅ Environment check passed${NC}"
    echo ""
}

# Function to setup database
setup_database() {
    echo -e "${BLUE}🗄️  Setting up database...${NC}"
    
    cd "$SCRIPT_DIR"
    
    if python3 add_loinc_column.py; then
        echo -e "${GREEN}✅ Database setup completed${NC}"
    else
        echo -e "${RED}❌ Database setup failed${NC}"
        exit 1
    fi
    
    echo ""
}

# Function to run LOINC mapping
run_mapping() {
    echo -e "${BLUE}🔍 Running LOINC mapping...${NC}"
    
    cd "$SCRIPT_DIR"
    
    # Check if user wants to limit the number of tests
    if [[ -n "$1" ]]; then
        echo -e "${YELLOW}📊 Limiting to $1 tests${NC}"
        python3 lab_test_loinc_mapper.py --map-tests --max-tests "$1"
    else
        python3 lab_test_loinc_mapper.py --map-tests
    fi
    
    echo ""
}

# Function to show statistics
show_stats() {
    echo -e "${BLUE}📊 Showing mapping statistics...${NC}"
    
    cd "$SCRIPT_DIR"
    python3 lab_test_loinc_mapper.py --stats
    
    echo ""
}

# Function to show help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --setup-only     Only setup the database (add LOINC column)"
    echo "  --map-only       Only run the LOINC mapping"
    echo "  --stats-only     Only show mapping statistics"
    echo "  --max-tests N    Limit mapping to N tests"
    echo "  --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run complete process"
    echo "  $0 --setup-only       # Only setup database"
    echo "  $0 --map-only         # Only run mapping"
    echo "  $0 --max-tests 10     # Map only 10 tests"
    echo ""
}

# Main execution
main() {
    # Parse command line arguments
    SETUP_ONLY=false
    MAP_ONLY=false
    STATS_ONLY=false
    MAX_TESTS=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --setup-only)
                SETUP_ONLY=true
                shift
                ;;
            --map-only)
                MAP_ONLY=true
                shift
                ;;
            --stats-only)
                STATS_ONLY=true
                shift
                ;;
            --max-tests)
                MAX_TESTS="$2"
                shift 2
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                echo -e "${RED}❌ Unknown option: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Check environment
    check_environment
    
    # Run based on options
    if [[ "$SETUP_ONLY" == true ]]; then
        setup_database
    elif [[ "$MAP_ONLY" == true ]]; then
        run_mapping "$MAX_TESTS"
    elif [[ "$STATS_ONLY" == true ]]; then
        show_stats
    else
        # Run complete process
        setup_database
        run_mapping "$MAX_TESTS"
        show_stats
    fi
    
    echo -e "${GREEN}🎉 Process completed successfully!${NC}"
}

# Run main function
main "$@" 