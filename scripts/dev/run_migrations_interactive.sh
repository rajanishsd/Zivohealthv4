#!/usr/bin/env bash
set -euo pipefail

# Run database migrations interactively on AWS RDS through SSM session
# Usage:
#   run_migrations_interactive.sh [-p AWS_PROFILE] [-r AWS_REGION] [-i INSTANCE_ID]

AWS_PROFILE="zivohealth"
AWS_REGION="us-east-1"
INSTANCE_ID=""

print_usage() {
  echo "Run database migrations interactively on AWS RDS through SSM session"
  echo "Options:"
  echo "  -p AWS_PROFILE   (default: zivohealth)"
  echo "  -r AWS_REGION    (default: us-east-1)"
  echo "  -i INSTANCE_ID   (optional; read from Terraform if omitted)"
  echo "  -h, --help       Show this help message"
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

echo "🚀 Starting interactive SSM session for database migrations"
echo "📋 Instance: $INSTANCE_ID"
echo ""
echo "📝 Migration commands to run:"
echo "   1. cd /opt/zivohealth/backend"
echo "   2. source venv/bin/activate"
echo "   3. alembic current"
echo "   4. alembic upgrade 16c952807f5d  # Migration 028: Add nutrition_meal_plans table"
echo "   5. alembic upgrade 0677399a8cd8  # Migration 030: Modify meal plans to store JSON"
echo "   6. alembic upgrade 031_add_goal_id_to_user_nutrient_focus  # Migration 031: Add goal_id to user_nutrient_focus"
echo "   7. alembic current"
echo ""
echo "🔗 Starting SSM session..."

aws ssm start-session --profile "$AWS_PROFILE" --region "$AWS_REGION" --target "$INSTANCE_ID"
