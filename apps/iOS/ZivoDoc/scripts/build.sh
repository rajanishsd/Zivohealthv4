#!/bin/bash

# ZivoHealth Build Script
# This script provides various build options for the ZivoHealth iOS app

set -e  # Exit on any error

echo "🔨 ZivoHealth Build Script"
echo "========================="

# Ensure we run from the ZivoDoc project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

# Default values
SCHEME="ZivoDoc"
CONFIGURATION="Debug"
DESTINATION="platform=iOS Simulator,name=iPhone 16,OS=latest"
CLEAN=false
ARCHIVE=false
LINT=true
UPDATE_PROJECT=false

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -c, --clean             Clean before building"
    echo "  -r, --release           Build for release (default: debug)"
    echo "  -a, --archive           Create archive for distribution"
    echo "  -d, --device DEVICE     Target device (default: iPhone 16)"
    echo "  -s, --scheme SCHEME     Build scheme (default: ZivoDoc)"
    echo "  --no-lint              Skip SwiftLint"
    echo "  --update-project       Update Xcode project before building"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Build debug for iPhone 16 simulator"
    echo "  $0 -c -r                             # Clean build for release"
    echo "  $0 -d \"iPhone 15 Pro\" -c           # Build for iPhone 15 Pro simulator"
    echo "  $0 -a                                # Create archive"
    echo "  $0 --update-project -c               # Update project and clean build"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--clean)
            CLEAN=true
            shift
            ;;
        -r|--release)
            CONFIGURATION="Release"
            shift
            ;;
        -a|--archive)
            ARCHIVE=true
            CONFIGURATION="Release"
            shift
            ;;
        -d|--device)
            DESTINATION="platform=iOS Simulator,name=$2,OS=latest"
            shift 2
            ;;
        -s|--scheme)
            SCHEME="$2"
            shift 2
            ;;
        --no-lint)
            LINT=false
            shift
            ;;
        --update-project)
            UPDATE_PROJECT=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Check if we're in the project root
if [ ! -f "project.yml" ] && [ ! -f "ZivoDoc.xcodeproj/project.pbxproj" ]; then
    print_error "No project configuration found. Please run this script from the ZivoDoc project root."
    exit 1
fi

print_status "Build Configuration:"
print_status "  Scheme: $SCHEME"
print_status "  Configuration: $CONFIGURATION"
print_status "  Destination: $DESTINATION"
print_status "  Clean: $CLEAN"
print_status "  Archive: $ARCHIVE"
print_status "  Lint: $LINT"
echo ""

# Update project if requested
if [ "$UPDATE_PROJECT" = true ]; then
    print_status "Updating Xcode project..."
    if [ -f "backend/scripts/update_project.sh" ]; then
    bash backend/scripts/update_project.sh
    else
        print_warning "update_project.sh not found, skipping project update"
    fi
fi

# Run SwiftLint if enabled
if [ "$LINT" = true ] && command -v swiftlint &> /dev/null; then
    print_status "Running SwiftLint..."
    if [ -f ".swiftlint.yml" ]; then
        swiftlint --config .swiftlint.yml
    else
        swiftlint frontend/Sources
    fi
    print_success "SwiftLint completed"
fi

# Build commands
BUILD_SETTINGS=(
    "DEVELOPMENT_TEAM=${DEVELOPMENT_TEAM:-}"
    "CODE_SIGN_IDENTITY=${CODE_SIGN_IDENTITY:-iPhone Developer}"
    "PROVISIONING_PROFILE_SPECIFIER=${PROVISIONING_PROFILE_SPECIFIER:-}"
)

if [ "$ARCHIVE" = true ]; then
    print_status "Creating archive for distribution..."
    
    ARCHIVE_PATH="./build/ZivoDoc_$(date +%Y%m%d_%H%M%S).xcarchive"
    
    xcodebuild archive \
        -scheme "$SCHEME" \
        -configuration "$CONFIGURATION" \
        -archivePath "$ARCHIVE_PATH" \
        -allowProvisioningUpdates \
        "${BUILD_SETTINGS[@]/#/-D }"
    
    if [ $? -eq 0 ]; then
        print_success "Archive created successfully at: $ARCHIVE_PATH"
        print_status "To export IPA, run:"
        print_status "xcodebuild -exportArchive -archivePath \"$ARCHIVE_PATH\" -exportPath ./build/ -exportOptionsPlist ExportOptions.plist"
    else
        print_error "Archive failed"
        exit 1
    fi
else
    # Regular build
    CLEAN_CMD=""
    if [ "$CLEAN" = true ]; then
        print_status "Cleaning build artifacts..."
        CLEAN_CMD="clean"
    fi
    
    print_status "Building $SCHEME ($CONFIGURATION)..."
    
    xcodebuild $CLEAN_CMD build \
        -scheme "$SCHEME" \
        -configuration "$CONFIGURATION" \
        -destination "$DESTINATION" \
        -allowProvisioningUpdates \
        "${BUILD_SETTINGS[@]/#/-D }"
    
    if [ $? -eq 0 ]; then
        print_success "Build completed successfully! 🎉"
        
        if [[ "$DESTINATION" == *"Simulator"* ]]; then
            print_status "You can now run the app in the iOS Simulator"
        else
            print_status "You can now run the app on your device"
        fi
    else
        print_error "Build failed"
        exit 1
    fi
fi

# Show build artifacts location
if [ -d "build" ]; then
    print_status "Build artifacts location: ./build/"
fi

echo ""
print_success "Build script completed! 🚀" 