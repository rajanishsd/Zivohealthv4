#!/usr/bin/env bash
set -euo pipefail

# Update Caddy configuration to route password reset requests to backend
# Usage:
#   update_caddy_for_password_reset.sh [-p AWS_PROFILE] [-r AWS_REGION] [-i INSTANCE_ID]

AWS_PROFILE="zivohealth"
AWS_REGION="us-east-1"
INSTANCE_ID=""

print_usage() {
  echo "Update Caddy configuration to route password reset requests to backend"
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

echo "🚀 Updating Caddy configuration for password reset routing on AWS EC2 instance: $INSTANCE_ID"

# Execute individual commands to avoid quote parsing issues
echo "🚀 Running Caddy configuration update..."

# Step 1: Check current configuration
echo "📋 Step 1: Checking current Caddy configuration..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker exec zivohealth-caddy-1 cat /etc/caddy/Caddyfile"]' \
  --output table

# Step 2: Create new Caddyfile
echo "📝 Step 2: Creating new Caddyfile with password reset routing..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker exec zivohealth-caddy-1 sh -c \"echo \\\"api.zivohealth.ai {\\n  encode zstd gzip\\n  reverse_proxy api:8000\\n}\\n\\nzivohealth.ai, www.zivohealth.ai {\\n  encode zstd gzip\\n  \\n  # Route password reset requests to backend API\\n  handle /reset-password* {\\n    reverse_proxy api:8000\\n  }\\n  \\n  # Serve all other requests as static files\\n  root * /srv/www\\n  file_server\\n}\\\" > /etc/caddy/Caddyfile\""]' \
  --output table

# Step 3: Reload Caddy
echo "🔄 Step 3: Reloading Caddy configuration..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker exec zivohealth-caddy-1 caddy reload --config /etc/caddy/Caddyfile", "sleep 5"]' \
  --output table

# Step 4: Test the configuration
echo "🧪 Step 4: Testing password reset routing..."
aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["curl -I https://zivohealth.ai/reset-password/ || echo \"HTTPS test failed\"", "curl -I http://zivohealth.ai/reset-password/ || echo \"HTTP test failed\""]' \
  --output table

echo "✅ Caddy configuration update command sent successfully!"
echo ""
echo "📋 You can monitor the progress by running:"
echo "   aws ssm list-command-invocations --profile $AWS_PROFILE --region $AWS_REGION --instance-id $INSTANCE_ID --query 'CommandInvocations[0].{Status:Status,Output:CommandPlugins[0].Output}' --output table"
echo ""
echo "🌐 Once updated, test the password reset page at:"
echo "   https://zivohealth.ai/reset-password/"
echo ""
echo "⚠️  Note: The update will take a few minutes to complete."
