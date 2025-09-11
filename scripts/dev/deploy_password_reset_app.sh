#!/usr/bin/env bash
set -euo pipefail

# Deploy password reset app to AWS EC2 instance
# Usage:
#   deploy_password_reset_app.sh [-p AWS_PROFILE] [-r AWS_REGION] [-i INSTANCE_ID]

AWS_PROFILE="zivohealth"
AWS_REGION="us-east-1"
INSTANCE_ID=""

print_usage() {
  echo "Deploy password reset app to AWS EC2 instance"
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

echo "🚀 Deploying password reset app to AWS EC2 instance: $INSTANCE_ID"

# Create deployment command
DEPLOY_COMMAND="
set -e

echo '🔍 Checking current setup...'
sudo docker ps | grep zivohealth-api-1 || { echo '❌ zivohealth-api-1 container not running'; exit 1; }

echo '📁 Creating web directory structure...'
sudo mkdir -p /srv/www

echo '📦 Copying password reset app from container...'
sudo docker cp zivohealth-api-1:/app/www/reset-password /srv/www/

echo '🔧 Setting proper permissions...'
sudo chown -R root:root /srv/www/reset-password
sudo chmod -R 755 /srv/www/reset-password

echo '📋 Verifying files...'
ls -la /srv/www/reset-password/
ls -la /srv/www/reset-password/static/

echo '🔄 Restarting Caddy to pick up changes...'
sudo docker restart zivohealth-caddy-1

echo '⏳ Waiting for Caddy to restart...'
sleep 10

echo '🧪 Testing password reset page...'
curl -I https://zivohealth.ai/reset-password/ || echo '⚠️ HTTPS test failed, trying HTTP...'
curl -I http://zivohealth.ai/reset-password/ || echo '⚠️ HTTP test also failed'

echo '✅ Password reset app deployment completed!'
echo '🌐 Password reset page should be available at: https://zivohealth.ai/reset-password/'
"

# Execute the deployment command
echo "🚀 Running password reset app deployment..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters "commands=[\"$DEPLOY_COMMAND\"]" \
  --output table

echo "✅ Password reset app deployment command sent successfully!"
echo ""
echo "📋 You can monitor the progress by running:"
echo "   aws ssm list-command-invocations --profile $AWS_PROFILE --region $AWS_REGION --instance-id $INSTANCE_ID --query 'CommandInvocations[0].{Status:Status,Output:CommandPlugins[0].Output}' --output table"
echo ""
echo "🌐 Once deployed, test the password reset page at:"
echo "   https://zivohealth.ai/reset-password/"
echo ""
echo "⚠️  Note: The deployment will take a few minutes to complete."
