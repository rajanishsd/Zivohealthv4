#!/bin/bash

# ZivoHealth Project Update Script
# This script updates the Xcode project file from project.yml configuration

set -e  # Exit on any error

echo "🔄 ZivoHealth Project Update Script"
echo "======================================"

# Ensure we run from the ZivohealthPlatform root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
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

# Check if we're in the project root
if [ ! -f "project.yml" ]; then
    print_error "project.yml not found. Please run this script from the project root."
    exit 1
fi

print_status "Checking for XcodeGen..."
if ! command -v xcodegen &> /dev/null; then
    print_warning "XcodeGen not found. Installing via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install xcodegen
    else
        print_error "Homebrew not found. Please install XcodeGen manually:"
        print_error "https://github.com/yonaskolb/XcodeGen"
        exit 1
    fi
fi

print_status "Backing up existing Xcode project..."
if [ -d "ZivoHealth.xcodeproj" ]; then
    rm -rf "ZivoHealth.xcodeproj.backup"
    cp -r "ZivoHealth.xcodeproj" "ZivoHealth.xcodeproj.backup"
    print_success "Backup created at ZivoHealth.xcodeproj.backup"
fi

print_status "Generating Xcode project from project.yml..."
xcodegen generate

if [ $? -eq 0 ]; then
    print_success "Xcode project generated successfully!"
else
    print_error "Failed to generate Xcode project"
    exit 1
fi

print_status "Updating Swift package dependencies..."
cd frontend
swift package update
if [ $? -eq 0 ]; then
    print_success "Swift package dependencies updated!"
else
    print_warning "Swift package update encountered issues"
fi
cd ..

print_status "Validating project structure..."
if [ -f "ZivoHealth.xcodeproj/project.pbxproj" ]; then
    print_success "Project file structure is valid"
else
    print_error "Generated project file is invalid"
    exit 1
fi

print_success "Project update completed successfully! 🎉"
print_status "You can now open ZivoHealth.xcodeproj in Xcode"

echo ""
echo "Next steps:"
echo "1. Open ZivoHealth.xcodeproj in Xcode"
echo "2. Set your development team in project settings"
echo "3. Build and run the project" 