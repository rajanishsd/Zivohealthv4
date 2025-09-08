#!/usr/bin/env bash
set -euo pipefail

# Check database migration status on AWS RDS through SSM
# Usage:
#   check_migration_status.sh [-p AWS_PROFILE] [-r AWS_REGION] [-i INSTANCE_ID]

AWS_PROFILE="zivohealth"
AWS_REGION="us-east-1"
INSTANCE_ID=""

print_usage() {
  echo "Check database migration status on AWS RDS through SSM"
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

echo "🔍 Checking database migration status on instance: $INSTANCE_ID"

# Create the status check command
STATUS_COMMAND="
set -euo pipefail

echo '🔍 Checking current directory and environment...'
pwd
ls -la

echo '📁 Navigating to backend directory...'
cd /opt/zivohealth/backend || { echo '❌ Backend directory not found'; exit 1; }

echo '🔧 Setting up Python environment...'
source venv/bin/activate || { echo '❌ Virtual environment not found'; exit 1; }

echo '📊 Current database migration status:'
alembic current

echo '📋 Migration history:'
alembic history --verbose

echo '🔍 Checking database connection and schema...'
python -c \"
import psycopg2
import os
from urllib.parse import urlparse

# Get database URL from environment
db_url = os.getenv('SQLALCHEMY_DATABASE_URI')
if not db_url:
    print('❌ SQLALCHEMY_DATABASE_URI not found in environment')
    exit(1)

print(f'🔗 Database URL: {db_url[:50]}...')

# Parse the URL
parsed = urlparse(db_url)
conn = psycopg2.connect(
    host=parsed.hostname,
    port=parsed.port,
    database=parsed.path[1:],
    user=parsed.username,
    password=parsed.password
)

cur = conn.cursor()

# Check database version
cur.execute('SELECT version();')
version = cur.fetchone()[0]
print(f'📊 PostgreSQL version: {version[:50]}...')

# Check if alembic_version table exists
cur.execute(\"\"\"
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'alembic_version'
    );
\"\"\")
alembic_table_exists = cur.fetchone()[0]
print(f'📋 alembic_version table exists: {alembic_table_exists}')

if alembic_table_exists:
    cur.execute('SELECT version_num FROM alembic_version;')
    current_version = cur.fetchone()[0]
    print(f'📋 Current migration version: {current_version}')

# Check if nutrition_meal_plans table exists
cur.execute(\"\"\"
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'nutrition_meal_plans'
    );
\"\"\")
meal_plans_exists = cur.fetchone()[0]
print(f'📋 nutrition_meal_plans table exists: {meal_plans_exists}')

# Check if user_nutrient_focus has goal_id column
cur.execute(\"\"\"
    SELECT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_nutrient_focus'
        AND column_name = 'goal_id'
    );
\"\"\")
goal_id_exists = cur.fetchone()[0]
print(f'📋 user_nutrient_focus.goal_id column exists: {goal_id_exists}')

# Show table structure for nutrition_meal_plans if it exists
if meal_plans_exists:
    cur.execute(\"\"\"
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'nutrition_meal_plans'
        ORDER BY ordinal_position;
    \"\"\")
    columns = cur.fetchall()
    print('📋 nutrition_meal_plans table structure:')
    for col in columns:
        print(f'  - {col[0]}: {col[1]} (nullable: {col[2]})')

conn.close()
print('✅ Database status check completed!')
\"
"

# Execute the status check through SSM
echo "📤 Sending status check command to EC2 instance..."

aws ssm send-command \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["docker exec zivohealth-api-1 alembic current", "docker exec zivohealth-api-1 alembic history --verbose"]' \
  --output table

echo "✅ Status check command sent successfully!"
echo "📋 You can view the results by running:"
echo "   aws ssm list-command-invocations --profile $AWS_PROFILE --region $AWS_REGION --instance-id $INSTANCE_ID --query 'CommandInvocations[0].{Status:Status,Output:CommandPlugins[0].Output}' --output table"
