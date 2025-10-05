#!/bin/bash

# Script to run diagnostic inside Docker container
# Usage: ./run_docker_diagnostic.sh [container_name]

set -e

CONTAINER_NAME=${1:-"zivohealth-api"}

echo "🐳 Running Diagnostic in Docker Container: $CONTAINER_NAME"
echo "=================================================="

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Container '$CONTAINER_NAME' is not running"
    echo "Available containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}"
    exit 1
fi

echo "✅ Container '$CONTAINER_NAME' is running"

echo ""
echo "🔍 Running Diagnostic Script..."
echo "=============================="

# Run the diagnostic script inside the container
docker exec -it "$CONTAINER_NAME" /bin/bash -c "
    echo '🐳 Docker Container Diagnostic'
    echo '=============================='
    echo 'Container: $CONTAINER_NAME'
    echo 'Timestamp: \$(date)'
    echo ''
    
    # Make the script executable and run it
    chmod +x /app/scripts/docker_diagnostic.sh
    /app/scripts/docker_diagnostic.sh
"

echo ""
echo "🏁 Diagnostic Complete"
echo "===================="
echo ""
echo "💡 Next Steps:"
echo "1. If you see ❌ items, those are the missing environment variables"
echo "2. Set the missing variables in your Docker environment"
echo "3. Restart the container: docker restart $CONTAINER_NAME"
echo "4. Check the logs: docker logs $CONTAINER_NAME"
