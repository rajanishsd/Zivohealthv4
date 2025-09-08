#!/usr/bin/env bash
set -euo pipefail

# Run database migrations on AWS RDS through SSM
# Usage:
#   run_migrations_ssm.sh [-p AWS_PROFILE] [-r AWS_REGION] [-i INSTANCE_ID] [--migrations MIGRATION_IDS]

AWS_PROFILE="zivohealth"
AWS_REGION="us-east-1"
INSTANCE_ID=""
MIGRATIONS="16c952807f5d,0677399a8cd8,031_add_goal_id_to_user_nutrient_focus"

print_usage() {
  echo "Run database migrations on AWS RDS through SSM"
  echo "Options:"
  echo "  -p AWS_PROFILE   (default: zivohealth)"
  echo "  -r AWS_REGION    (default: us-east-1)"
  echo "  -i INSTANCE_ID   (optional; read from Terraform if omitted)"
  echo "  --migrations     Comma-separated list of migration IDs (default: 28,30,31)"
  echo "  -h, --help       Show this help message"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p) AWS_PROFILE="$2"; shift 2 ;;
    -r) AWS_REGION="$2"; shift 2 ;;
    -i) INSTANCE_ID="$2"; shift 2 ;;
    --migrations) MIGRATIONS="$2"; shift 2 ;;
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

echo "🚀 Starting database migration on instance: $INSTANCE_ID"
echo "📋 Migrations to run: $MIGRATIONS"

# Execute the migration through SSM
echo "📤 Sending migration command to EC2 instance..."

# Run migrations one by one
echo "🚀 Running migration 028 (16c952807f5d)..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["docker exec zivohealth-api-1 alembic upgrade 16c952807f5d"]' \
  --output table

echo "🚀 Running migration 030 (0677399a8cd8)..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["docker exec zivohealth-api-1 alembic upgrade 0677399a8cd8"]' \
  --output table

echo "🚀 Running migration 031 (031_add_goal_id_to_user_nutrient_focus)..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["docker exec zivohealth-api-1 alembic upgrade 031_add_goal_id_to_user_nutrient_focus"]' \
  --output table

echo "📊 Checking final migration status..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["docker exec zivohealth-api-1 alembic current"]' \
  --output table

echo "✅ Migration command sent successfully!"
echo "📋 You can monitor the progress by running:"
echo "   aws ssm list-command-invocations --profile $AWS_PROFILE --region $AWS_REGION --instance-id $INSTANCE_ID --query 'CommandInvocations[0].{Status:Status,Output:CommandPlugins[0].Output}' --output table"
