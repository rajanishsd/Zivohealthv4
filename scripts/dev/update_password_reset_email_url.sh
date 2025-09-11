#!/usr/bin/env bash
set -euo pipefail

# Update password reset email URLs to use API domain
# Usage:
#   update_password_reset_email_url.sh [-p AWS_PROFILE] [-r AWS_REGION] [-i INSTANCE_ID]

AWS_PROFILE="zivohealth"
AWS_REGION="us-east-1"
INSTANCE_ID=""

print_usage() {
  echo "Update password reset email URLs to use API domain"
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

echo "🚀 Updating password reset email URLs to use API domain on AWS EC2 instance: $INSTANCE_ID"

# First, set the PASSWORD_RESET_BASE_URL in SSM Parameter Store
echo "📝 Setting PASSWORD_RESET_BASE_URL in SSM Parameter Store..."
aws ssm put-parameter \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --name "/zivohealth/dev/email/password_reset_base_url" \
  --value "https://api.zivohealth.ai" \
  --type "String" \
  --overwrite \
  --output table

# Create the update command
UPDATE_COMMAND="
set -e

echo '🔍 Checking current backend container...'
sudo docker ps | grep zivohealth-api-1

echo '📝 Updating environment variables from SSM...'
/opt/zivohealth/update_env_from_ssm.sh

echo '🔄 Restarting backend container to pick up email service changes...'
sudo docker restart zivohealth-api-1

echo '⏳ Waiting for backend to restart...'
sleep 15

echo '🧪 Testing password reset email URL generation...'
echo 'Testing API domain access:'
curl -I https://api.zivohealth.ai/reset-password/ || echo 'API domain test failed'

echo '✅ Password reset email URL update completed!'
echo '📧 New password reset emails will use: https://api.zivohealth.ai/reset-password/'
echo '🌐 Test the password reset flow by requesting a reset from your mobile app'
"

# Execute the update command
echo "🚀 Running password reset email URL update..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters "commands=[\"$UPDATE_COMMAND\"]" \
  --output table

echo "✅ Password reset email URL update command sent successfully!"
echo ""
echo "📋 You can monitor the progress by running:"
echo "   aws ssm list-command-invocations --profile $AWS_PROFILE --region $AWS_REGION --instance-id $INSTANCE_ID --query 'CommandInvocations[0].{Status:Status,Output:CommandPlugins[0].Output}' --output table"
echo ""
echo "🌐 Once updated, test the password reset flow:"
echo "   1. Request password reset from your mobile app"
echo "   2. Check your email for the reset link"
echo "   3. Click the link - it should now work at: https://api.zivohealth.ai/reset-password/"
echo ""
echo "⚠️  Note: The update will take a few minutes to complete."
