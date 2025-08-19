#!/bin/bash

# Medical Mappings Creator Runner
# ==============================
# This script creates and populates medical mapping tables:
# - vitals_mappings (with LOINC codes)
# - prescription_mappings (with RxNorm and SNOMED CT codes)
# - medical_images_mappings (with RadLex and SNOMED CT codes)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}🔧 Medical Mappings Creator Runner${NC}"
echo "====================================="
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check environment
check_environment() {
    echo -e "${YELLOW}🔍 Checking environment...${NC}"
    
    # Check if we're in the right directory
    if [[ ! -f "$SCRIPT_DIR/create_medical_mappings.py" ]]; then
        echo -e "${RED}❌ Error: create_medical_mappings.py not found in $SCRIPT_DIR${NC}"
        exit 1
    fi
    
    # Check if Python is available
    if ! command_exists python3; then
        echo -e "${RED}❌ Error: python3 not found${NC}"
        exit 1
    fi
    
    # Check if required Python packages are available
    echo -e "${YELLOW}📦 Checking Python dependencies...${NC}"
    python3 -c "import sqlalchemy" 2>/dev/null || {
        echo -e "${RED}❌ Error: Missing required Python packages${NC}"
        echo "Please install: pip install sqlalchemy"
        exit 1
    }
    
    echo -e "${GREEN}✅ Environment check passed${NC}"
    echo ""
}

# Function to create all mappings
create_all_mappings() {
    echo -e "${BLUE}🚀 Creating all medical mappings...${NC}"
    
    cd "$SCRIPT_DIR"
    
    if python3 create_medical_mappings.py --setup-all; then
        echo -e "${GREEN}✅ All medical mappings created successfully${NC}"
    else
        echo -e "${RED}❌ Failed to create medical mappings${NC}"
        exit 1
    fi
    
    echo ""
}

# Function to create vitals mappings
create_vitals_mappings() {
    echo -e "${BLUE}📊 Creating vitals mappings...${NC}"
    
    cd "$SCRIPT_DIR"
    
    if python3 create_medical_mappings.py --setup-vitals; then
        echo -e "${GREEN}✅ Vitals mappings created successfully${NC}"
    else
        echo -e "${RED}❌ Failed to create vitals mappings${NC}"
        exit 1
    fi
    
    echo ""
}

# Function to create prescription mappings
create_prescription_mappings() {
    echo -e "${BLUE}💊 Creating prescription mappings...${NC}"
    
    cd "$SCRIPT_DIR"
    
    if python3 create_medical_mappings.py --setup-prescriptions; then
        echo -e "${GREEN}✅ Prescription mappings created successfully${NC}"
    else
        echo -e "${RED}❌ Failed to create prescription mappings${NC}"
        exit 1
    fi
    
    echo ""
}

# Function to create medical images mappings
create_medical_images_mappings() {
    echo -e "${BLUE}🖼️  Creating medical images mappings...${NC}"
    
    cd "$SCRIPT_DIR"
    
    if python3 create_medical_mappings.py --setup-images; then
        echo -e "${GREEN}✅ Medical images mappings created successfully${NC}"
    else
        echo -e "${RED}❌ Failed to create medical images mappings${NC}"
        exit 1
    fi
    
    echo ""
}

# Function to show statistics
show_stats() {
    echo -e "${BLUE}📊 Showing mapping statistics...${NC}"
    
    cd "$SCRIPT_DIR"
    python3 create_medical_mappings.py --stats
    
    echo ""
}

# Function to show help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --all              Create all mapping tables"
    echo "  --vitals           Create only vitals_mappings table"
    echo "  --prescriptions    Create only prescription_mappings table"
    echo "  --images           Create only medical_images_mappings table"
    echo "  --stats            Show mapping statistics"
    echo "  --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --all              # Create all mapping tables"
    echo "  $0 --vitals           # Create only vitals mappings"
    echo "  $0 --prescriptions    # Create only prescription mappings"
    echo "  $0 --images           # Create only medical images mappings"
    echo "  $0 --stats            # Show statistics"
    echo ""
}

# Main execution
main() {
    # Parse command line arguments
    CREATE_ALL=false
    CREATE_VITALS=false
    CREATE_PRESCRIPTIONS=false
    CREATE_IMAGES=false
    SHOW_STATS=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --all)
                CREATE_ALL=true
                shift
                ;;
            --vitals)
                CREATE_VITALS=true
                shift
                ;;
            --prescriptions)
                CREATE_PRESCRIPTIONS=true
                shift
                ;;
            --images)
                CREATE_IMAGES=true
                shift
                ;;
            --stats)
                SHOW_STATS=true
                shift
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
    if [[ "$CREATE_ALL" == true ]]; then
        create_all_mappings
    else
        if [[ "$CREATE_VITALS" == true ]]; then
            create_vitals_mappings
        fi
        
        if [[ "$CREATE_PRESCRIPTIONS" == true ]]; then
            create_prescription_mappings
        fi
        
        if [[ "$CREATE_IMAGES" == true ]]; then
            create_medical_images_mappings
        fi
    fi
    
    if [[ "$SHOW_STATS" == true ]]; then
        show_stats
    fi
    
    echo -e "${GREEN}🎉 Process completed successfully!${NC}"
}

# Run main function
main "$@" 