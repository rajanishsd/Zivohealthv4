#!/usr/bin/env bash
set -euo pipefail

# Run password reset database migrations (032 and 033) on AWS RDS through SSM
# Usage:
#   run_password_reset_migrations.sh [-p AWS_PROFILE] [-r AWS_REGION] [-i INSTANCE_ID]

AWS_PROFILE="zivohealth"
AWS_REGION="us-east-1"
INSTANCE_ID=""

print_usage() {
  echo "Run password reset database migrations (032 and 033) on AWS RDS through SSM"
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

echo "🚀 Starting password reset database migrations on instance: $INSTANCE_ID"
echo "📋 Migrations to run: 032_add_password_reset, 033_password_reset_doctors"

# Execute migrations step by step to avoid parameter parsing issues
echo "🚀 Running password reset migrations with proper environment setup..."

# Step 1: Check current status
echo "🔍 Step 1: Checking current migration status..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /opt/zivohealth/backend && source venv/bin/activate && alembic current"]' \
  --output table

echo "⏳ Waiting 10 seconds..."
sleep 10

# Step 2: Run migration 032
echo "🚀 Step 2: Running migration 032 (Add password reset tokens table)..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /opt/zivohealth/backend && source venv/bin/activate && alembic upgrade 032_add_password_reset"]' \
  --output table

echo "⏳ Waiting 15 seconds..."
sleep 15

# Step 3: Run migration 033
echo "🚀 Step 3: Running migration 033 (Update password reset tokens to support doctors)..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /opt/zivohealth/backend && source venv/bin/activate && alembic upgrade 033_password_reset_doctors"]' \
  --output table

echo "⏳ Waiting 15 seconds..."
sleep 15

# Step 4: Verify final status
echo "📊 Step 4: Verifying final migration status..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /opt/zivohealth/backend && source venv/bin/activate && alembic current"]' \
  --output table

echo "⏳ Waiting 10 seconds..."
sleep 10

# Step 5: Verify table structure
echo "🔍 Step 5: Verifying password_reset_tokens table structure..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /opt/zivohealth/backend && source venv/bin/activate && python -c \"import psycopg2; import os; from urllib.parse import urlparse; db_url = os.getenv(\\\"SQLALCHEMY_DATABASE_URI\\\"); parsed = urlparse(db_url); conn = psycopg2.connect(host=parsed.hostname, port=parsed.port, database=parsed.path[1:], user=parsed.username, password=parsed.password); cur = conn.cursor(); cur.execute(\\\"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = \\\"public\\\" AND table_name = \\\"password_reset_tokens\\\")\\\"); print(f\\\"password_reset_tokens table exists: {cur.fetchone()[0]}\\\"); conn.close()\""]' \
  --output table

echo "✅ Password reset migration commands sent successfully!"
echo ""
echo "📋 You can monitor the progress by running:"
echo "   aws ssm list-command-invocations --profile $AWS_PROFILE --region $AWS_REGION --instance-id $INSTANCE_ID --query 'CommandInvocations[0].{Status:Status,Output:CommandPlugins[0].Output}' --output table"
echo ""
echo "🔍 To check the final status, run:"
echo "   ./scripts/dev/check_migration_status.sh -p $AWS_PROFILE -r $AWS_REGION"
echo ""
echo "⚠️  Note: The migrations will take a few minutes to complete. Check the command status before proceeding."
