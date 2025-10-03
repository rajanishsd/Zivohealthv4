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

docker build -f Dockerfile.dashboard -t $ECR_REPO_URL/zivohealth-dev-dashboard:$IMAGE_TAG .
docker push $ECR_REPO_URL/zivohealth-dev-dashboard:$IMAGE_TAG

echo "All images built and pushed successfully!"
