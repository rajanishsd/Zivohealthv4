#!/usr/bin/env bash
set -euo pipefail

# Push ML Worker Image and Update Fargate Service
# This pushes the ML worker image to ECR and triggers Fargate to pull the new version

# Enable shell tracing when DEBUG=1
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

echo "🚀 Deploying ML Worker to Fargate"
echo "=================================="

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infra/terraform"
REGION="us-east-1"

: "${AWS_PROFILE:=zivohealth}"

# Helper to run aws with the selected profile and region
aws_cmd() { aws --profile "$AWS_PROFILE" --region "$REGION" "$@"; }

echo "🔧 Validating Terraform outputs..."
cd "$TF_DIR"
ECR_BACKEND_URL=$(terraform output -raw ecr_repository_url)
ECR_REGISTRY_HOST=${ECR_BACKEND_URL%%/*}
TAG="latest"

# Get ML worker infrastructure outputs
ML_CLUSTER=$(terraform output -raw ml_worker_cluster_name 2>/dev/null || echo "")
ML_SERVICE=$(terraform output -raw ml_worker_service_name 2>/dev/null || echo "")

if [[ -z "$ECR_REGISTRY_HOST" ]]; then
  echo "❌ Could not read Terraform outputs. Ensure terraform apply completed."
  exit 1
fi

if [[ -z "$ML_CLUSTER" || -z "$ML_SERVICE" ]]; then
  echo "⚠️  ML Worker infrastructure not found in Terraform outputs."
  echo "💡 You may need to run 'terraform apply' to create the ML worker infrastructure."
  echo ""
  read -p "Continue with just pushing the image? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

echo "📦 Variables:"
echo "  ECR_REGISTRY_HOST  = $ECR_REGISTRY_HOST"
echo "  TAG                = $TAG"
echo "  REGION             = $REGION"
if [[ -n "$ML_CLUSTER" ]]; then
  echo "  ML_CLUSTER         = $ML_CLUSTER"
  echo "  ML_SERVICE         = $ML_SERVICE"
fi

echo ""
echo "🔐 Logging into ECR..."
aws_cmd ecr get-login-password | docker login --username AWS --password-stdin "$ECR_REGISTRY_HOST"

echo ""
echo "📤 Pushing ML worker image to ECR..."
docker push "$ECR_REGISTRY_HOST/zivohealth-production-ml-worker:$TAG"

echo ""
echo "✅ ML worker image pushed successfully!"

# If Fargate service exists, update it
if [[ -n "$ML_CLUSTER" && -n "$ML_SERVICE" ]]; then
  echo ""
  echo "🔄 Updating Fargate service to pull new image..."
  
  # Force new deployment (Fargate will pull the latest image)
  aws_cmd ecs update-service \
    --cluster "$ML_CLUSTER" \
    --service "$ML_SERVICE" \
    --force-new-deployment \
    --query 'service.{ServiceName:serviceName,Status:status,DesiredCount:desiredCount,RunningCount:runningCount}' \
    --output table
  
  echo ""
  echo "✅ Fargate service update initiated!"
  echo ""
  echo "📊 Monitor deployment status:"
  echo "aws --profile $AWS_PROFILE --region $REGION ecs describe-services --cluster $ML_CLUSTER --services $ML_SERVICE --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Deployments:deployments[*].{Status:status,DesiredCount:desiredCount,RunningCount:runningCount}}'"
  
  echo ""
  echo "📝 View ML worker logs:"
  echo "aws --profile $AWS_PROFILE --region $REGION logs tail /ecs/production-ml-worker --follow"
else
  echo ""
  echo "ℹ️  No Fargate service found. Image is pushed but not deployed."
  echo "💡 Run 'terraform apply' to create the ML worker infrastructure."
fi

echo ""
echo "✅ Deployment complete!"


