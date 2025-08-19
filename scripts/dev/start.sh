#!/bin/bash

# ZivoHealth Project Startup Wrapper
# This script provides easy access to backend services from the project root

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT/backend" && ./start_services.sh "$@"