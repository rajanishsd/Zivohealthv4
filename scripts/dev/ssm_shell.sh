#!/usr/bin/env bash
set -euo pipefail

# Open an SSM shell to the EC2 instance provisioned by Terraform
# Usage:
#   ssm_shell.sh [-p AWS_PROFILE] [-r AWS_REGION] [-i INSTANCE_ID]
# If INSTANCE_ID is not provided, it will be read from infra/terraform outputs.

AWS_PROFILE="zivohealth"
AWS_REGION="us-east-1"
INSTANCE_ID=""

print_usage() {
  echo "Open an SSM shell to the EC2 instance"
  echo "Options:"
  echo "  -p AWS_PROFILE   (default: zivohealth)"
  echo "  -r AWS_REGION    (default: us-east-1)"
  echo "  -i INSTANCE_ID   (optional; read from Terraform if omitted)"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p) AWS_PROFILE="$2"; shift 2 ;;
    -r) AWS_REGION="$2"; shift 2 ;;
    -i) INSTANCE_ID="$2"; shift 2 ;;
    -h|--help) print_usage; exit 0 ;;
    *) echo "Unknown option: $1"; print_usage; exit 1 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TERRAFORM_DIR="$ROOT_DIR/infra/terraform"

if [[ -z "$INSTANCE_ID" ]]; then
  if command -v terraform >/dev/null 2>&1; then
    pushd "$TERRAFORM_DIR" >/dev/null
    INSTANCE_ID="$(AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" terraform output -raw ec2_instance_id)"
    popd >/dev/null
  fi
fi

if [[ -z "$INSTANCE_ID" ]]; then
  echo "Error: INSTANCE_ID not provided and could not be inferred from Terraform." >&2
  exit 1
fi

echo "Starting SSM session to instance: $INSTANCE_ID"
aws ssm start-session --profile "$AWS_PROFILE" --region "$AWS_REGION" --target "$INSTANCE_ID"
