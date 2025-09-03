#!/bin/bash

# Test script for worker management
# This script tests the worker management functionality

echo "=== Testing Worker Management Script ==="

# Test 1: Check if script exists and is executable
if [ -x "scripts/dev/worker_management.sh" ]; then
    echo "✓ Worker management script exists and is executable"
else
    echo "✗ Worker management script not found or not executable"
    exit 1
fi

# Test 2: Show help
echo ""
echo "=== Testing help command ==="
./scripts/dev/worker_management.sh help

# Test 3: Check status (this should work even if not on EC2)
echo ""
echo "=== Testing status command ==="
./scripts/dev/worker_management.sh status

# Test 4: Test check command
echo ""
echo "=== Testing check command ==="
./scripts/dev/worker_management.sh check

echo ""
echo "=== Worker Management Script Tests Complete ==="
echo ""
echo "To use on EC2, run:"
echo "  ./scripts/dev/worker_management.sh status"
echo "  ./scripts/dev/worker_management.sh multiple"
echo "  ./scripts/dev/worker_management.sh reset"
