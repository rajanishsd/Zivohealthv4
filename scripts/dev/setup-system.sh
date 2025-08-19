#!/bin/bash

# ZivoHealth System Dependencies Setup Script
# Installs all required system dependencies via Homebrew

echo "🏥 ZivoHealth System Dependencies Setup"
echo "======================================="
echo ""

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

# Check if Homebrew is installed
check_homebrew() {
    if ! command -v brew &> /dev/null; then
        print_error "Homebrew is not installed. Please install it first:"
        print_error "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    print_success "Homebrew is installed"
}

# Install system dependencies
install_dependencies() {
    print_status "Installing system dependencies..."
    
    # Array of packages to install
    packages=(
        "redis"      # Redis server for caching and session storage
        "python@3.11" # Python 3.11 for backend development
        "node"       # Node.js for React dashboard
        "postgresql" # PostgreSQL database (optional - can use Docker instead)
    )
    
    for package in "${packages[@]}"; do
        print_status "Checking $package..."
        
        if brew list "$package" &>/dev/null; then
            print_success "$package is already installed"
        else
            print_status "Installing $package..."
            if brew install "$package"; then
                print_success "$package installed successfully"
            else
                print_error "Failed to install $package"
                return 1
            fi
        fi
    done
    
    print_success "All system dependencies installed"
}

# Verify installations
verify_installations() {
    print_status "Verifying installations..."
    
    # Check Redis
    if command -v redis-server &> /dev/null; then
        print_success "Redis: $(redis-server --version | head -n1)"
    else
        print_error "Redis not found"
    fi
    
    # Check Python 3.11
    if command -v python3.11 &> /dev/null; then
        print_success "Python 3.11: $(python3.11 --version)"
    else
        print_error "Python 3.11 not found"
    fi
    
    # Check Node.js
    if command -v node &> /dev/null; then
        print_success "Node.js: $(node --version)"
    else
        print_error "Node.js not found"
    fi
    
    # Check npm
    if command -v npm &> /dev/null; then
        print_success "npm: $(npm --version)"
    else
        print_error "npm not found"
    fi
    
    # Check PostgreSQL (optional)
    if command -v postgres &> /dev/null; then
        print_success "PostgreSQL: $(postgres --version)"
    else
        print_warning "PostgreSQL not found (optional dependency)"
    fi
}

# Setup instructions
show_setup_instructions() {
    echo ""
    echo "📋 Next Steps:"
    echo "=============="
    echo "1. Create Python virtual environment:"
    echo "   python3.11 -m venv venv"
    echo ""
    echo "2. Activate virtual environment:"
    echo "   source venv/bin/activate"
    echo ""
    echo "3. Install Python dependencies:"
    echo "   pip install -r backend/requirements.txt"
    echo ""
    echo "4. Start all services:"
    echo "   ./scripts/start-all.sh"
    echo ""
    echo "🌐 Access URLs:"
    echo "  • Backend API: http://localhost:8000"
    echo "  • API Docs: http://localhost:8000/docs"
    echo "  • Dashboard: http://localhost:3000"
    echo ""
}

# Main execution
main() {
    echo "This script will install all required system dependencies for ZivoHealth."
    echo "Required packages: Redis, Python 3.11, Node.js, PostgreSQL"
    echo ""
    
    # Check if Homebrew is available
    check_homebrew
    
    # Install dependencies
    if install_dependencies; then
        print_success "System dependencies installation completed!"
        
        # Verify installations
        verify_installations
        
        # Show next steps
        show_setup_instructions
    else
        print_error "Failed to install some dependencies"
        exit 1
    fi
}

# Run main function
main "$@" 