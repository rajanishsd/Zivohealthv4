#!/usr/bin/env bash
set -euo pipefail

# tf-apply.sh — Initialize, plan, and apply Terraform for infra/terraform
# Compatible with macOS Bash 3.2

usage() {
  cat <<EOF
Usage:
  $(basename "$0") [--profile PROFILE] [--region REGION] [--image-tag TAG]
                     [--auto-approve] [--plan-only] [--skip-init]
                     [--var key=value ...] [--var-file FILE]

Examples:
  $(basename "$0") --profile zivohealth --region us-east-1 --image-tag latest --auto-approve
  $(basename "$0") --plan-only --profile zivohealth --region us-east-1 --image-tag latest
  $(basename "$0") --var-file dev.tfvars --auto-approve
EOF
}

PROFILE="${AWS_PROFILE:-}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
IMAGE_TAG="latest"
AUTO_APPROVE="false"
PLAN_ONLY="false"
SKIP_INIT="false"
VAR_FILE=""
EXTRA_VARS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2;;
    --region) REGION="$2"; shift 2;;
    --image-tag) IMAGE_TAG="$2"; shift 2;;
    --auto-approve) AUTO_APPROVE="true"; shift;;
    --plan-only) PLAN_ONLY="true"; shift;;
    --skip-init) SKIP_INIT="true"; shift;;
    --var) EXTRA_VARS+=("-var" "$2"); shift 2;;
    --var-file) VAR_FILE="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

if ! command -v terraform >/dev/null 2>&1; then
  echo "Error: terraform not found. Install Terraform >= 1.5." >&2
  exit 2
fi

# Resolve repo root and terraform dir
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/infra/terraform"

if [[ ! -d "$TF_DIR" ]]; then
  echo "Error: Terraform directory not found at $TF_DIR" >&2
  exit 2
fi

# Region required because provider uses var.aws_region
if [[ -z "$REGION" ]]; then
  echo "Error: AWS region not set. Use --region or export AWS_REGION." >&2
  exit 2
fi

# Export profile to env for provider/auth
if [[ -n "$PROFILE" ]]; then
  export AWS_PROFILE="$PROFILE"
fi
export AWS_REGION="$REGION"

echo "Terraform dir: $TF_DIR"
echo "AWS profile: ${PROFILE:-default}"
echo "AWS region: $REGION"
echo "Image tag: $IMAGE_TAG"

TF_BASE=(terraform -chdir="$TF_DIR")

if [[ "$SKIP_INIT" != "true" ]]; then
  echo "Running terraform init ..."
  "${TF_BASE[@]}" init -input=false -upgrade
fi

PLAN_ARGS=(-input=false -detailed-exitcode -out=tfplan -var "image_tag=$IMAGE_TAG" -var "aws_region=$REGION")
if [[ -n "$VAR_FILE" ]]; then
  PLAN_ARGS+=("-var-file" "$VAR_FILE")
fi
if [[ ${#EXTRA_VARS[@]} -gt 0 ]]; then
  PLAN_ARGS+=("${EXTRA_VARS[@]}")
fi

echo "Creating plan ..."
set +e
"${TF_BASE[@]}" plan "${PLAN_ARGS[@]}"
PLAN_RC=$?
set -e

case "$PLAN_RC" in
  0)
    echo "No changes to apply."
    exit 0
    ;;
  2)
    echo "Changes detected."
    ;;
  *)
    echo "Plan failed with exit code $PLAN_RC." >&2
    exit $PLAN_RC
    ;;
esac

if [[ "$PLAN_ONLY" == "true" ]]; then
  echo "Plan-only mode; not applying."
  exit 0
fi

APPLY_ARGS=("tfplan")
if [[ "$AUTO_APPROVE" == "true" ]]; then
  APPLY_ARGS=("-auto-approve" "tfplan")
fi

echo "Applying ..."
"${TF_BASE[@]}" apply -input=false "${APPLY_ARGS[@]}"
echo "Done."


