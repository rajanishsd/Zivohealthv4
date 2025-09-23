#!/usr/bin/env bash
set -euo pipefail

# Pull and (re)start docker compose on EC2 via SSM
# Usage:
#   deploy_compose_on_ec2.sh [-p AWS_PROFILE] [-r AWS_REGION] [-i INSTANCE_ID] [--pull-only]

AWS_PROFILE="zivohealth"
AWS_REGION="us-east-1"
INSTANCE_ID=""
PULL_ONLY=false
DISABLE_REMINDERS=false

# Optional: ensure SSM is seeded from backend/.env and refresh remote .env from SSM
SEED_FROM_ENV=false
REFRESH_ENV=false
PROJECT=""
ENVIRONMENT=""
ENV_FILE="backend/.env"

print_usage() {
  echo "Pull and (re)start docker compose on EC2 via SSM"
  echo "Options:"
  echo "  -p AWS_PROFILE   (default: zivohealth)"
  echo "  -r AWS_REGION    (default: us-east-1)"
  echo "  -i INSTANCE_ID   (optional; read from Terraform if omitted)"
  echo "  --pull-only      Only pull images, do not restart"
  echo "  --disable-reminders  Remove reminders service from docker-compose on EC2 before starting"
  echo "  --seed-from-env  Seed SSM from backend/.env before deploy"
  echo "  --refresh-env    Update /opt/zivohealth/.env OPENAI_API_KEY from SSM before restart"
  echo "  --project NAME   Project namespace for SSM path (e.g., zivohealth)"
  echo "  --environment E  Environment for SSM path (e.g., dev)"
  echo "  --env-file PATH  Path to local env file (default: backend/.env)"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p) AWS_PROFILE="$2"; shift 2 ;;
    -r) AWS_REGION="$2"; shift 2 ;;
    -i) INSTANCE_ID="$2"; shift 2 ;;
    --pull-only) PULL_ONLY=true; shift ;;
    --disable-reminders) DISABLE_REMINDERS=true; shift ;;
    --seed-from-env) SEED_FROM_ENV=true; shift ;;
    --refresh-env) REFRESH_ENV=true; shift ;;
    --project) PROJECT="$2"; shift 2 ;;
    --environment) ENVIRONMENT="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    -h|--help) print_usage; exit 0 ;;
    *) echo "Unknown option: $1"; print_usage; exit 1 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TERRAFORM_DIR="$ROOT_DIR/infra/terraform"
ECR_REPO_URL=""
SSM_IMAGE_TAG_PARAM=""
IMAGE_TAG_VALUE=""

if [[ -z "$INSTANCE_ID" ]]; then
  if command -v terraform >/dev/null 2>&1 && [[ -d "$TERRAFORM_DIR" ]]; then
    pushd "$TERRAFORM_DIR" >/dev/null
    INSTANCE_ID="$(AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" terraform output -raw ec2_instance_id)"
    ECR_REPO_URL="$(AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" terraform output -raw ecr_repository_url)"
    SSM_IMAGE_TAG_PARAM="$(AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" terraform output -raw ssm_image_tag_param_name 2>/dev/null || true)"
    popd >/dev/null
  fi
fi

if [[ -z "${INSTANCE_ID:-}" ]]; then
  echo "Error: INSTANCE_ID not provided and could not be inferred from Terraform." >&2
  exit 1
fi

ECR_HOST="${ECR_REPO_URL%%/*}"

echo "Using AWS_PROFILE=$AWS_PROFILE"
echo "Using AWS_REGION=$AWS_REGION"
echo "Using INSTANCE_ID=$INSTANCE_ID"
if [[ -n "$ECR_REPO_URL" ]]; then
  echo "Using ECR_REPO_URL=$ECR_REPO_URL"
  echo "Using ECR_HOST=$ECR_HOST"
else
  echo "Warning: ECR_REPO_URL not inferred. Will attempt ECR login using repo host parsed on EC2." >&2
fi
if [[ -n "$SSM_IMAGE_TAG_PARAM" ]]; then
  IMAGE_TAG_VALUE="$(aws ssm get-parameter --profile "$AWS_PROFILE" --region "$AWS_REGION" --name "$SSM_IMAGE_TAG_PARAM" --with-decryption --query 'Parameter.Value' --output text 2>/dev/null || true)"
  if [[ -n "$IMAGE_TAG_VALUE" ]]; then
    echo "Using IMAGE_TAG from SSM ($SSM_IMAGE_TAG_PARAM): $IMAGE_TAG_VALUE"
  else
    echo "Warning: Could not read IMAGE_TAG from SSM param $SSM_IMAGE_TAG_PARAM" >&2
  fi
fi

# If project/environment not provided, try to infer from SSM image tag param path: /<project>/<env>/deploy/image_tag
if [[ ( -z "$PROJECT" || -z "$ENVIRONMENT" ) && -n "$SSM_IMAGE_TAG_PARAM" ]]; then
  IFS='/' read -r _ PROJECT ENVIRONMENT _ <<< "$SSM_IMAGE_TAG_PARAM"
fi

# Optionally seed SSM from local backend/.env to ensure OPENAI_API_KEY and others match the repo
if [[ "$SEED_FROM_ENV" == true ]]; then
  if [[ -z "$PROJECT" || -z "$ENVIRONMENT" ]]; then
    echo "Error: --project and --environment are required with --seed-from-env" >&2
    exit 1
  fi
  echo "Seeding SSM from $ENV_FILE for $PROJECT/$ENVIRONMENT ..."
  "${ROOT_DIR}/scripts/dev/seed_ssm_from_env.sh" \
    --project "$PROJECT" --environment "$ENVIRONMENT" \
    --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --env-file "${ROOT_DIR}/$ENV_FILE"
fi

# Optionally refresh remote /opt/zivohealth/.env OPENAI_API_KEY from SSM before restarting compose
if [[ "$REFRESH_ENV" == true ]]; then
  if [[ -z "$PROJECT" || -z "$ENVIRONMENT" ]]; then
    echo "Error: --project and --environment are required with --refresh-env" >&2
    exit 1
  fi
  SSM_ENV_FILE="/tmp/ssm_refresh_env.json"
  cat > "$SSM_ENV_FILE" <<JSON
{
  "commands": [
    "bash -lc 'set -e; export AWS_DEFAULT_REGION=$AWS_REGION'",
    "bash -lc 'VAL=$(aws ssm get-parameter --with-decryption --name \"/$PROJECT/$ENVIRONMENT/openai/api_key\" --query \"Parameter.Value\" --output text 2>/dev/null || true); if [ -n \"$VAL\" ]; then sudo sed -i.bak -e \"/^OPENAI_API_KEY=/d\" /opt/zivohealth/.env; echo \"OPENAI_API_KEY=$VAL\" | sudo tee -a /opt/zivohealth/.env >/dev/null; else echo \"Warning: missing SSM OPENAI_API_KEY for /$PROJECT/$ENVIRONMENT/openai/api_key\"; fi'"
  ]
}
JSON
  echo "Updating remote /opt/zivohealth/.env OPENAI_API_KEY from SSM ..."
  aws ssm send-command \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --document-name AWS-RunShellScript \
    --instance-ids "$INSTANCE_ID" \
    --parameters file://"$SSM_ENV_FILE" >/dev/null
fi

SSM_FILE="/tmp/ssm_deploy.json"

# Build SSM JSON with placeholders, then replace
cat > "$SSM_FILE" <<'JSON'
{
  "commands": [
    "bash -lc 'set -e; export AWS_DEFAULT_REGION=__REGION__'",
    "bash -lc 'aws ecr get-login-password --region __REGION__ | sudo docker login --username AWS --password-stdin __ECR_HOST__ || true'",
    "bash -lc 'if ! sudo docker info >/dev/null 2>&1; then echo Docker not running; exit 1; fi'",
    "bash -lc 'ECR_R=\"__ECR_REPO_URL__\"; TAG=\"__IMAGE_TAG_VALUE__\"; if [ -z \"$ECR_R\" ] || [ -z \"$TAG\" ]; then IMG=$(sudo docker ps --filter name=zivohealth-api-1 --format {{.Image}}); if [ -n \"$IMG\" ]; then ECR_R=${IMG%:*}; TAG=${IMG##*:}; fi; fi; echo ECR=$ECR_R TAG=$TAG > /tmp/deploy_env'",
    "bash -lc '. /tmp/deploy_env; if [ -n \"$ECR\" ] && [ -n \"$TAG\" ]; then echo Using ECR=$ECR TAG=$TAG; else echo Missing ECR/TAG, proceeding without overrides; fi'",
    "bash -lc '. /tmp/deploy_env; if [ -n \"$ECR\" ] && [ -n \"$TAG\" ]; then sudo -E env ECR_REPO_URL=$ECR IMAGE_TAG=$TAG docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml down; else sudo docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml down; fi'",
    "bash -lc '. /tmp/deploy_env; if [ -n \"$ECR\" ] && [ -n \"$TAG\" ]; then sudo -E env ECR_REPO_URL=$ECR IMAGE_TAG=$TAG docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml pull; else echo Skipping compose pull due to missing ECR/TAG; fi'",
    "bash -lc '. /tmp/deploy_env; if [ -n \"$ECR\" ] && [ -n \"$TAG\" ]; then sudo -E env ECR_REPO_URL=$ECR IMAGE_TAG=$TAG docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml up -d; else sudo docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml up -d; fi'",
    "bash -lc 'if [ \"__DISABLE_REMINDERS__\" = \"true\" ]; then echo Stopping reminders container ...; sudo docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml stop reminders || true; sudo docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml rm -f reminders || true; fi'",
    "bash -lc 'sudo docker compose --env-file /opt/zivohealth/.env -f /opt/zivohealth/docker-compose.yml ps'"
  ]
}
JSON

# Replace placeholders
if command -v sed >/dev/null 2>&1; then
  # macOS/BSD sed compatibility
  sed -i '' -e "s|__REGION__|$AWS_REGION|g" "$SSM_FILE" || sed -i -e "s|__REGION__|$AWS_REGION|g" "$SSM_FILE"
  sed -i '' -e "s|__ECR_HOST__|$ECR_HOST|g" "$SSM_FILE" || sed -i -e "s|__ECR_HOST__|$ECR_HOST|g" "$SSM_FILE"
  sed -i '' -e "s|__ECR_REPO_URL__|$ECR_REPO_URL|g" "$SSM_FILE" || sed -i -e "s|__ECR_REPO_URL__|$ECR_REPO_URL|g" "$SSM_FILE"
  sed -i '' -e "s|__IMAGE_TAG_VALUE__|$IMAGE_TAG_VALUE|g" "$SSM_FILE" || sed -i -e "s|__IMAGE_TAG_VALUE__|$IMAGE_TAG_VALUE|g" "$SSM_FILE"
  sed -i '' -e "s|__DISABLE_REMINDERS__|$DISABLE_REMINDERS|g" "$SSM_FILE" || sed -i -e "s|__DISABLE_REMINDERS__|$DISABLE_REMINDERS|g" "$SSM_FILE"
fi

# If pull-only, remove the up -d line from the JSON
if [[ "$PULL_ONLY" == true ]]; then
  awk 'BEGIN{rem=0} {if ($0 ~ /compose -f \/opt\/zivohealth\/docker-compose.yml up -d/) rem=1; else print $0}' "$SSM_FILE" > "$SSM_FILE.tmp" && mv "$SSM_FILE.tmp" "$SSM_FILE"
fi

echo "Sending SSM command..."
CMD_ID=$(aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --document-name AWS-RunShellScript \
  --instance-ids "$INSTANCE_ID" \
  --parameters file://"$SSM_FILE" \
  --query 'Command.CommandId' --output text)

echo "CommandId: $CMD_ID"

echo "Streaming SSM output (will stop when finished)..."
while true; do
  STATUS=$(aws ssm list-commands \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --command-id "$CMD_ID" \
    --query 'Commands[0].Status' --output text 2>/dev/null || echo "")

  aws ssm list-command-invocations \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --command-id "$CMD_ID" \
    --details \
    --query 'CommandInvocations[0].CommandPlugins[].Output' \
    --output text | sed -e 's/\r$//' || true

  case "$STATUS" in
    Pending|InProgress|Delayed) sleep 3 ;;
    *) break ;;
  esac
done

echo "SSM Status: ${STATUS:-unknown}"
