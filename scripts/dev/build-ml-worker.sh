#!/usr/bin/env bash
set -euo pipefail

# Build ML Worker Image for Fargate
# This builds the ML worker that processes jobs from SQS

# Enable shell tracing when DEBUG=1
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

echo "🤖 Building ML Worker Image"
echo "============================"

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infra/terraform"
REGION="us-east-1"

: "${AWS_PROFILE:=zivohealth}"
BASE_IMAGE_TAG="${BASE_IMAGE_TAG:-latest}"

# Helper to run aws with the selected profile and region
aws_cmd() { aws --profile "$AWS_PROFILE" --region "$REGION" "$@"; }

echo "🔧 Validating Terraform outputs (ECR registry)..."
cd "$TF_DIR"
ECR_BACKEND_URL=$(terraform output -raw ecr_repository_url)
ECR_REGISTRY_HOST=${ECR_BACKEND_URL%%/*}
TAG="latest"

if [[ -z "$ECR_REGISTRY_HOST" ]]; then
  echo "❌ Could not read Terraform outputs. Ensure terraform apply completed."
  exit 1
fi

echo "📦 Variables:"
echo "  ECR_REGISTRY_HOST  = $ECR_REGISTRY_HOST"
echo "  TAG                = $TAG"
echo "  BASE_IMAGE_TAG     = $BASE_IMAGE_TAG"
echo "  REGION             = $REGION"

# Login to ECR to pull the base image
echo ""
echo "🔐 Logging into ECR..."
aws_cmd ecr get-login-password | docker login --username AWS --password-stdin "$ECR_REGISTRY_HOST"

# Pull the base image from ECR
echo ""
echo "📥 Pulling base image from ECR..."
BASE_IMAGE_URI="$ECR_REGISTRY_HOST/zivohealth-base:$BASE_IMAGE_TAG"
echo "   Base image: $BASE_IMAGE_URI"

if ! docker pull "$BASE_IMAGE_URI"; then
  echo ""
  echo "❌ Failed to pull base image from ECR!"
  echo "💡 You need to build the base image first:"
  echo "   Run: ./scripts/dev/build-ml-base-image.sh"
  echo ""
  exit 1
fi

echo ""
echo "✅ Base image pulled successfully!"

echo ""
echo "🧱 Ensuring docker buildx builder exists..."
docker buildx ls >/dev/null 2>&1 || docker buildx create --use --name zivo-builder >/dev/null 2>&1 || true
docker buildx use zivo-builder

echo ""
echo "🤖 Building ML worker image (linux/amd64)..."
echo "   This worker processes lab categorization jobs from SQS"
echo "   Using base: $BASE_IMAGE_URI"
docker buildx build --platform linux/amd64 \
  --build-arg BASE_IMAGE_REGISTRY="$ECR_REGISTRY_HOST/zivohealth-base" \
  --build-arg BASE_IMAGE_TAG="$BASE_IMAGE_TAG" \
  -f "$ROOT_DIR/backend/Dockerfile.worker" \
  -t "$ECR_REGISTRY_HOST/zivohealth-production-ml-worker:$TAG" \
  "$ROOT_DIR/backend" \
  --load

echo ""
echo "✅ ML worker image built successfully!"
echo ""
echo "📊 Image details:"
docker images | grep "zivohealth-production-ml-worker" | head -3

echo ""
echo "📝 Next step: Run ./scripts/dev/push-ml-worker.sh to push the image and deploy"


