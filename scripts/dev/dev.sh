#!/bin/bash

# ZivoHealth Development Script
# Master script for common development workflows

set -e  # Exit on any error

echo "🚀 ZivoHealth Development Script"
echo "==============================="

# Ensure we run from the ZivohealthPlatform root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

print_header() {
    echo -e "${PURPLE}[TASK]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  setup           Initial project setup"
    echo "  update          Update Xcode project from project.yml"
    echo "  build           Build the app (default: debug)"
    echo "  release         Build for release"
    echo "  archive         Create archive for distribution"
    echo "  clean           Clean build artifacts"
    echo "  lint            Run SwiftLint"
    echo "  test            Run tests"
    echo "  dev             Full development workflow (update + build)"
    echo ""
    echo "Build Options (for build/release/archive commands):"
    echo "  -d, --device DEVICE     Target device (default: iPhone 16)"
    echo "  --no-lint              Skip SwiftLint"
    echo ""
    echo "Examples:"
    echo "  $0 setup                         # Initial setup"
    echo "  $0 dev                          # Update project and build"
    echo "  $0 build                        # Build debug"
    echo "  $0 release                      # Build release"
    echo "  $0 build -d \"iPhone 15 Pro\"   # Build for specific device"
    echo "  $0 archive                      # Create archive"
    echo "  $0 clean                        # Clean everything"
}

# Check if we're in the project root
if [ ! -f "project.yml" ]; then
    print_error "project.yml not found. Please run this script from the project root."
    exit 1
fi

# Parse command
COMMAND="${1:-help}"
shift || true

case $COMMAND in
    setup)
        print_header "🔧 Initial Project Setup"
        
        # Check for required tools
        print_status "Checking for required tools..."
        
        # Check for Homebrew
        if ! command -v brew &> /dev/null; then
            print_warning "Homebrew not found. Installing..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        
        # Check for XcodeGen
        if ! command -v xcodegen &> /dev/null; then
            print_status "Installing XcodeGen..."
            brew install xcodegen
        fi
        
        # Check for SwiftLint
        if ! command -v swiftlint &> /dev/null; then
            print_status "Installing SwiftLint..."
            brew install swiftlint
        fi
        
        # Make scripts executable
        print_status "Making scripts executable..."
        chmod +x scripts/*.sh
        
        # Initial project generation
        print_status "Generating initial Xcode project..."
        bash scripts/update_project.sh
        
        print_success "Setup completed! 🎉"
        print_status "Next steps:"
        print_status "1. Open ZivoHealth.xcodeproj in Xcode"
        print_status "2. Set your development team in project settings"
        print_status "3. Run: $0 dev"
        ;;
        
    update)
        print_header "🔄 Updating Xcode Project"
        bash scripts/update_project.sh
        ;;
        
    build)
        print_header "🔨 Building Debug"
        bash scripts/build.sh "$@"
        ;;
        
    release)
        print_header "🔨 Building Release"
        bash scripts/build.sh -r "$@"
        ;;
        
    archive)
        print_header "📦 Creating Archive"
        bash scripts/build.sh -a "$@"
        ;;
        
    clean)
        print_header "🧹 Cleaning Build Artifacts"
        
        # Clean Xcode build artifacts
        if [ -d "build" ]; then
            print_status "Removing build directory..."
            rm -rf build
        fi
        
        # Clean Swift package artifacts
        if [ -d "frontend/.build" ]; then
            print_status "Removing Swift package build artifacts..."
            rm -rf frontend/.build
        fi
        
        # Clean Xcode derived data (optional)
        read -p "Clean Xcode derived data? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Cleaning Xcode derived data..."
            rm -rf ~/Library/Developer/Xcode/DerivedData/ZivoHealth-*
        fi
        
        print_success "Clean completed!"
        ;;
        
    lint)
        print_header "🔍 Running SwiftLint"
        if command -v swiftlint &> /dev/null; then
            if [ -f ".swiftlint.yml" ]; then
                swiftlint --config .swiftlint.yml
            else
                swiftlint frontend/Sources
            fi
            print_success "SwiftLint completed"
        else
            print_error "SwiftLint not installed. Run: $0 setup"
            exit 1
        fi
        ;;
        
    test)
        print_header "🧪 Running Tests"
        # Add test running logic here when tests are available
        print_warning "Test running not yet implemented"
        ;;
        
    dev)
        print_header "🚀 Full Development Workflow"
        
        print_status "Step 1: Updating project..."
        bash scripts/update_project.sh
        
        print_status "Step 2: Building app..."
        bash scripts/build.sh -c "$@"  # Clean build
        
        print_success "Development workflow completed! 🎉"
        ;;
        
    help|--help|-h)
        show_usage
        ;;
        
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac 