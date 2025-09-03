#!/usr/bin/env bash
set -euo pipefail

# Build and push the backend image to AWS ECR
# Usage:
#   build_ecr_backend.sh [-p AWS_PROFILE] [-r AWS_REGION] [-e ECR_REPOSITORY_URL] [-t TAG]
#                        [--multi-arch] [--no-latest] [--also-latest]
#                        [--set-ssm-tag] [-s SSM_PARAM_NAME]
# Defaults:
#   - AWS_PROFILE: zivohealth
#   - AWS_REGION: us-east-1
#   - TAG: current git short SHA
#   - ECR repository URL: from infra/terraform outputs if not provided

AWS_PROFILE_DEFAULT="zivohealth"
AWS_REGION_DEFAULT="us-east-1"
MULTI_ARCH=false
ALSO_LATEST=true
SET_SSM=false
SSM_PARAM_NAME=""

AWS_PROFILE="$AWS_PROFILE_DEFAULT"
AWS_REGION="$AWS_REGION_DEFAULT"
ECR_REPO_URL=""
TAG=""

print_usage() {
  echo "Build and push backend Docker image to AWS ECR"
  echo ""
  echo "Options:"
  echo "  -p AWS_PROFILE        AWS CLI profile (default: $AWS_PROFILE_DEFAULT)"
  echo "  -r AWS_REGION         AWS region (default: $AWS_REGION_DEFAULT)"
  echo "  -e ECR_REPO_URL       Full ECR repo URL (e.g., 123.dkr.ecr.us-east-1.amazonaws.com/repo)"
  echo "  -t TAG                Image tag (default: current git short SHA)"
  echo "  --multi-arch          Build linux/amd64 and linux/arm64 (default: amd64 only)"
  echo "  --no-latest           Do not also push ':latest' (default: push both TAG and latest)"
  echo "  --also-latest         Back-compat flag; has no effect since latest is default"
  echo "  --set-ssm-tag         Update the deploy watcher SSM parameter to TAG"
  echo "  -s SSM_PARAM_NAME     SSM parameter name for image tag (overrides TF output)"
  echo "  -h                    Show help"
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p)
      AWS_PROFILE="$2"; shift 2 ;;
    -r)
      AWS_REGION="$2"; shift 2 ;;
    -e)
      ECR_REPO_URL="$2"; shift 2 ;;
    -t)
      TAG="$2"; shift 2 ;;
    --multi-arch)
      MULTI_ARCH=true; shift ;;
    --no-latest)
      ALSO_LATEST=false; shift ;;
    --also-latest)
      ALSO_LATEST=true; shift ;;
    --set-ssm-tag)
      SET_SSM=true; shift ;;
    -s)
      SSM_PARAM_NAME="$2"; shift 2 ;;
    -h|--help)
      print_usage; exit 0 ;;
    *)
      echo "Unknown option: $1"; print_usage; exit 1 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
DOCKERFILE="$BACKEND_DIR/Dockerfile"
TERRAFORM_DIR="$ROOT_DIR/infra/terraform"

if [[ ! -f "$DOCKERFILE" ]]; then
  echo "Error: Dockerfile not found at $DOCKERFILE" >&2
  exit 1
fi

# Determine TAG if not provided
if [[ -z "$TAG" ]]; then
  if git -C "$ROOT_DIR" rev-parse --short HEAD >/dev/null 2>&1; then
    TAG="$(git -C "$ROOT_DIR" rev-parse --short HEAD)"
  else
    TAG="$(date +%Y%m%d%H%M%S)"
  fi
fi

echo "Using AWS_PROFILE=$AWS_PROFILE"
echo "Using AWS_REGION=$AWS_REGION"
echo "Using TAG=$TAG"

# Infer ECR repo URL from Terraform if not provided
if [[ -z "$ECR_REPO_URL" ]]; then
  if command -v terraform >/dev/null 2>&1 && [[ -d "$TERRAFORM_DIR" ]]; then
    echo "Attempting to read ECR repo URL from Terraform outputs..."
    pushd "$TERRAFORM_DIR" >/dev/null
    ECR_REPO_URL="$(AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" terraform output -raw ecr_repository_url)"
    popd >/dev/null
  fi
fi

if [[ -z "$ECR_REPO_URL" ]]; then
  echo "Error: ECR_REPO_URL not provided and could not be inferred from Terraform." >&2
  exit 1
fi

REGISTRY_HOST="${ECR_REPO_URL%%/*}"
echo "Using ECR_REPO_URL=$ECR_REPO_URL"
echo "Using REGISTRY_HOST=$REGISTRY_HOST"

# Checks
command -v aws >/dev/null 2>&1 || { echo "aws CLI is required" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }

# Login to ECR
aws --profile "$AWS_PROFILE" --region "$AWS_REGION" ecr get-login-password \
  | docker login --username AWS --password-stdin "$REGISTRY_HOST"

# Ensure buildx builder
if ! docker buildx ls | grep -q "\*"; then
  docker buildx create --use --name zivo-builder >/dev/null 2>&1 || docker buildx use zivo-builder
fi

# Build and push
PLATFORMS="linux/amd64"
if [[ "$MULTI_ARCH" == true ]]; then
  PLATFORMS="linux/amd64,linux/arm64"
fi

echo "Building platforms: $PLATFORMS"

if [[ "$ALSO_LATEST" == true ]]; then
  echo "Building and pushing tags: $TAG and latest"
  docker buildx build \
    --platform "$PLATFORMS" \
    -t "$ECR_REPO_URL:$TAG" \
    -t "$ECR_REPO_URL:latest" \
    -f "$DOCKERFILE" \
    "$BACKEND_DIR" \
    --push
  echo "Done. Pushed: $ECR_REPO_URL:$TAG and :latest"
else
  echo "Building and pushing tag: $TAG"
  docker buildx build \
    --platform "$PLATFORMS" \
    -t "$ECR_REPO_URL:$TAG" \
    -f "$DOCKERFILE" \
    "$BACKEND_DIR" \
    --push
  echo "Done. Pushed: $ECR_REPO_URL:$TAG"
fi

# Optionally update SSM parameter so the deploy watcher picks up new tag
if [[ "$SET_SSM" == true ]]; then
  if [[ -z "$SSM_PARAM_NAME" ]]; then
    echo "Inferring SSM parameter name from Terraform..."
    pushd "$TERRAFORM_DIR" >/dev/null
    SSM_PARAM_NAME="$(AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" terraform output -raw ssm_image_tag_param_name)"
    popd >/dev/null
  fi
  if [[ -n "$SSM_PARAM_NAME" ]]; then
    echo "Updating SSM parameter $SSM_PARAM_NAME to $TAG"
    aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
      ssm put-parameter --name "$SSM_PARAM_NAME" --type String --value "$TAG" --overwrite >/dev/null
    echo "SSM parameter updated. Deploy watcher should roll out the new image shortly."
  else
    echo "Warning: Could not determine SSM parameter name; skipping watcher update" >&2
  fi
fi
