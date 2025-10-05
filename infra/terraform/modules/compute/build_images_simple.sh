#!/bin/bash
set -e

# Configuration
AWS_REGION="us-east-1"
ECR_REPO_URL="474221740916.dkr.ecr.us-east-1.amazonaws.com"
IMAGE_TAG="latest"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO_URL

# Build and push Caddy image
echo "Building Caddy image..."
docker build -f Dockerfile.caddy -t $ECR_REPO_URL/zivohealth-dev-caddy:$IMAGE_TAG .
docker push $ECR_REPO_URL/zivohealth-dev-caddy:$IMAGE_TAG

# Build and push Dashboard image
echo "Building Dashboard image..."
cd ../../../../backend

# Check if environment variables are set
if [ -z "$REACT_APP_SECRET_KEY" ]; then
    echo "❌ Error: REACT_APP_SECRET_KEY environment variable not set"
    echo "💡 Set it before running this script:"
    echo "   export REACT_APP_SECRET_KEY='your-secret-key'"
    exit 1
fi

if [ -z "$REACT_APP_API_KEY" ]; then
    echo "❌ Error: REACT_APP_API_KEY environment variable not set"
    echo "💡 Set it before running this script:"
    echo "   export REACT_APP_API_KEY='your-api-key'"
    exit 1
fi

echo "🔑 Using SECRET_KEY: ${REACT_APP_SECRET_KEY:0:8}...${REACT_APP_SECRET_KEY: -4} (length: ${#REACT_APP_SECRET_KEY})"
echo "🔑 Using API_KEY: ${REACT_APP_API_KEY:0:8}...${REACT_APP_API_KEY: -4} (length: ${#REACT_APP_API_KEY})"

docker build -f Dockerfile.dashboard \
  --build-arg REACT_APP_SECRET_KEY="$REACT_APP_SECRET_KEY" \
  --build-arg REACT_APP_API_KEY="$REACT_APP_API_KEY" \
  -t $ECR_REPO_URL/zivohealth-dev-dashboard:$IMAGE_TAG .
docker push $ECR_REPO_URL/zivohealth-dev-dashboard:$IMAGE_TAG

echo "All images built and pushed successfully!"
