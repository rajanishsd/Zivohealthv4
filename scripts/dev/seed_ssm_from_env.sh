#!/usr/bin/env bash
set -euo pipefail

# Seed AWS SSM parameters from backend/.env for selected config keys
# Usage:
#   seed_ssm_from_env.sh --project zivohealth --environment dev [--profile zivohealth] [--region us-east-1] [--env-file backend/.env]

PROJECT=""
ENVIRONMENT=""
AWS_PROFILE_ARG=()
AWS_REGION_ARG=()
ENV_FILE="backend/.env"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2;;
    --environment) ENVIRONMENT="$2"; shift 2;;
    --profile) AWS_PROFILE_ARG=("--profile" "$2"); shift 2;;
    --region) AWS_REGION_ARG=("--region" "$2"); shift 2;;
    --env-file) ENV_FILE="$2"; shift 2;;
    -h|--help)
      echo "Usage: $0 --project <name> --environment <env> [--profile prof] [--region reg] [--env-file path]";
      exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 1;;
  esac
done

if [[ -z "$PROJECT" || -z "$ENVIRONMENT" ]]; then
  echo "Error: --project and --environment are required" >&2
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: env file not found: $ENV_FILE" >&2
  exit 2
fi

# Helper: extract a key's value from .env (handles spaces around '=', trims quotes)
get_env_value() {
  key="$1"
  # Find the last occurrence to prefer later overrides
  raw_line=$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$ENV_FILE" | tail -n 1 || true)
  if [ -z "$raw_line" ]; then
    echo ""
    return 0
  fi
  val=${raw_line#*=}
  # trim surrounding whitespace
  val=$(echo "$val" | sed -e 's/^\s*//' -e 's/\s*$//')
  # strip surrounding single or double quotes
  case "$val" in
    \"*\") val=${val#\"}; val=${val%\"} ;;
    "'*'") val=${val#\'}; val=${val%\'} ;;
  esac
  echo "$val"
}

# Helper to put parameter
put_param() {
  local name="$1"; shift
  local type="$1"; shift
  local value="$1"; shift
  if [[ -z "$value" ]]; then
    echo "Skipping $name (empty)"
    return 0
  fi
  echo "Setting $name ($type)"
  
  # Build AWS command with optional profile and region
  local aws_cmd="aws ssm put-parameter"
  if [[ ${#AWS_PROFILE_ARG[@]} -gt 0 ]]; then
    aws_cmd="$aws_cmd ${AWS_PROFILE_ARG[*]}"
  fi
  if [[ ${#AWS_REGION_ARG[@]} -gt 0 ]]; then
    aws_cmd="$aws_cmd ${AWS_REGION_ARG[*]}"
  fi
  aws_cmd="$aws_cmd --name \"$name\" --type \"$type\" --value \"$value\" --overwrite"
  
  eval "$aws_cmd" >/dev/null
}

ns() { echo "/$PROJECT/$ENVIRONMENT/$1"; }

# Secrets
put_param "$(ns openai/api_key)" SecureString "$(get_env_value OPENAI_API_KEY)"
put_param "$(ns langsmith/api_key)" SecureString "$(get_env_value LANGCHAIN_API_KEY)"
put_param "$(ns e2b/api_key)" SecureString "$(get_env_value E2B_API_KEY)"
put_param "$(ns serpapi/key)" SecureString "$(get_env_value SERPAPI_KEY)"
put_param "$(ns livekit/api_key)" SecureString "$(get_env_value LIVEKIT_API_KEY)"
put_param "$(ns livekit/api_secret)" SecureString "$(get_env_value LIVEKIT_API_SECRET)"
put_param "$(ns app/secret_key)" SecureString "$(get_env_value SECRET_KEY)"

# Email Configuration (Secrets)
put_param "$(ns email/smtp_password)" SecureString "$(get_env_value SMTP_PASSWORD)"


# API Security (Secrets)
put_param "$(ns api/valid_api_keys)" SecureString "$(get_env_value VALID_API_KEYS)"
put_param "$(ns app/app_secret_key)" SecureString "$(get_env_value APP_SECRET_KEY)"

# Database Configuration (Secrets)
put_param "$(ns db/password)" SecureString "$(get_env_value POSTGRES_PASSWORD)"

# Non-secrets
put_param "$(ns langsmith/project)" String "$(get_env_value LANGCHAIN_PROJECT)"
put_param "$(ns langsmith/endpoint)" String "$(get_env_value LANGCHAIN_ENDPOINT)"
put_param "$(ns livekit/url)" String "$(get_env_value LIVEKIT_URL)"

# 
 Configuration (Non-secrets)
put_param "$(ns email/smtp_server)" String "$(get_env_value SMTP_SERVER)"
put_param "$(ns email/smtp_port)" String "$(get_env_value SMTP_PORT)"
put_param "$(ns email/smtp_username)" String "$(get_env_value SMTP_USERNAME)"
put_param "$(ns email/from_email)" String "$(get_env_value FROM_EMAIL)"
put_param "$(ns email/frontend_url)" String "$(get_env_value FRONTEND_URL)"
put_param "$(ns email/password_reset_token_expiry_minutes)" String "$(get_env_value PASSWORD_RESET_TOKEN_EXPIRY_MINUTES)"

# AWS Configuration (Non-secrets)
put_param "$(ns aws/default_region)" String "$(get_env_value AWS_DEFAULT_REGION)"
put_param "$(ns aws/region)" String "$(get_env_value AWS_REGION)"
put_param "$(ns aws/s3_bucket)" String "$(get_env_value AWS_S3_BUCKET)"
put_param "$(ns aws/uploads_s3_prefix)" String "$(get_env_value UPLOADS_S3_PREFIX)"

# API Security (Non-secrets)
put_param "$(ns api/require_api_key)" String "$(get_env_value REQUIRE_API_KEY)"
put_param "$(ns api/require_app_signature)" String "$(get_env_value REQUIRE_APP_SIGNATURE)"

# Server Configuration
put_param "$(ns server/host)" String "$(get_env_value SERVER_HOST)"
put_param "$(ns server/port)" String "$(get_env_value SERVER_PORT)"
put_param "$(ns server/process_pending_on_startup)" String "$(get_env_value PROCESS_PENDING_ON_STARTUP)"

# Database Configuration (Non-secrets)
put_param "$(ns db/server)" String "$(get_env_value POSTGRES_SERVER)"
put_param "$(ns db/port)" String "$(get_env_value POSTGRES_PORT)"
put_param "$(ns db/user)" String "$(get_env_value POSTGRES_USER)"
put_param "$(ns db/name)" String "$(get_env_value POSTGRES_DB)"

# Redis Configuration
put_param "$(ns redis/host)" String "$(get_env_value REDIS_HOST)"
put_param "$(ns redis/port)" String "$(get_env_value REDIS_PORT)"
put_param "$(ns redis/db)" String "$(get_env_value REDIS_DB)"

# OCR Configuration
put_param "$(ns ocr/provider)" String "$(get_env_value OCR_PROVIDER)"
put_param "$(ns ocr/timeout)" String "$(get_env_value OCR_TIMEOUT)"
put_param "$(ns ocr/max_file_size)" String "$(get_env_value OCR_MAX_FILE_SIZE)"

# CORS Configuration
put_param "$(ns cors/origins)" String "$(get_env_value CORS_ORIGINS)"

# WebSocket Configuration
put_param "$(ns websocket/message_queue)" String "$(get_env_value WS_MESSAGE_QUEUE)"

# Vitals Configuration
put_param "$(ns vitals/batch_size)" String "$(get_env_value VITALS_BATCH_SIZE)"
put_param "$(ns vitals/aggregation_delay_bulk)" String "$(get_env_value VITALS_AGGREGATION_DELAY_BULK)"
put_param "$(ns vitals/aggregation_delay_incremental)" String "$(get_env_value VITALS_AGGREGATION_DELAY_INCREMENTAL)"

# Project Information
put_param "$(ns project/name)" String "$(get_env_value PROJECT_NAME)"
put_param "$(ns project/version)" String "$(get_env_value VERSION)"
put_param "$(ns project/project_version)" String "$(get_env_value PROJECT_VERSION)"
put_param "$(ns project/api_v1_str)" String "$(get_env_value API_V1_STR)"

# Security Configuration
put_param "$(ns security/algorithm)" String "$(get_env_value ALGORITHM)"
put_param "$(ns security/access_token_expire_minutes)" String "$(get_env_value ACCESS_TOKEN_EXPIRE_MINUTES)"

# Password Reset App Configuration
put_param "$(ns app/password_reset_app_dir)" String "$(get_env_value PASSWORD_RESET_APP_DIR)"

# Model configs
put_param "$(ns models/default_ai_model)" String "$(get_env_value DEFAULT_AI_MODEL)"
put_param "$(ns models/base_agent_model)" String "$(get_env_value BASE_AGENT_MODEL)"
put_param "$(ns models/base_agent_temperature)" String "$(get_env_value BASE_AGENT_TEMPERATURE)"
put_param "$(ns models/lab_agent_model)" String "$(get_env_value LAB_AGENT)"
put_param "$(ns models/lab_agent_temperature)" String "$(get_env_value LAB_AGENT_TEMPERATURE)"
put_param "$(ns models/customer_agent_model)" String "$(get_env_value CUSTOMER_AGENT_MODEL)"
put_param "$(ns models/customer_agent_temperature)" String "$(get_env_value CUSTOMER_AGENT_TEMPERATURE)"
put_param "$(ns models/medical_doctor_model)" String "$(get_env_value MEDICAL_DOCTOR_MODEL)"
put_param "$(ns models/medical_doctor_temperature)" String "$(get_env_value MEDICAL_DOCTOR_TEMPERATURE)"
put_param "$(ns models/document_workflow_model)" String "$(get_env_value DOCUMENT_WORKFLOW_MODEL)"
put_param "$(ns models/document_workflow_temperature)" String "$(get_env_value DOCUMENT_WORKFLOW_TEMPERATURE)"
put_param "$(ns models/openai_client_model)" String "$(get_env_value OPENAI_CLIENT_MODEL)"
put_param "$(ns models/lab_aggregation_agent_model)" String "$(get_env_value LAB_AGGREGATION_AGENT_MODEL)"
put_param "$(ns models/lab_aggregation_agent_temperature)" String "$(get_env_value LAB_AGGREGATION_AGENT_TEMPERATURE)"
put_param "$(ns models/nutrition_vision_model)" String "$(get_env_value NUTRITION_VISION_MODEL)"
put_param "$(ns models/nutrition_agent_model)" String "$(get_env_value NUTRITION_AGENT_MODEL)"
put_param "$(ns models/vitals_vision_model)" String "$(get_env_value VITALS_VISION_MODEL)"
put_param "$(ns models/vitals_agent_model)" String "$(get_env_value VITALS_AGENT_MODEL)"
put_param "$(ns models/prescription_clinical_agent_model)" String "$(get_env_value PRESCRIPTION_CLINICAL_AGENT_MODEL)"
put_param "$(ns models/prescription_clinical_vision_model)" String "$(get_env_value PRESCRIPTION_CLINICAL_VISION_MODEL)"
put_param "$(ns models/prescription_clinical_vision_max_tokens)" String "$(get_env_value PRESCRIPTION_CLINICAL_VISION_MAX_TOKENS)"
put_param "$(ns models/pharmacy_agent_model)" String "$(get_env_value PHARMACY_AGENT_MODEL)"
put_param "$(ns models/pharmacy_vision_model)" String "$(get_env_value PHARMACY_VISION_MODEL)"

echo "Done seeding SSM parameters for $PROJECT/$ENVIRONMENT from $ENV_FILE"


