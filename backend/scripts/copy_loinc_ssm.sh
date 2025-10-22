#!/bin/bash
# Copy loinc_pg_embedding from local PostgreSQL to RDS using SSM port forwarding
# No SSH keys required - uses AWS Systems Manager

set -e

# Configuration
TABLE_NAME="${TABLE_NAME:-loinc_pg_embedding}"
LOCAL_DB="${LOCAL_DB:-zivohealth}"
LOCAL_USER="${LOCAL_USER:-rajanishsd}"
LOCAL_HOST="${LOCAL_HOST:-localhost}"
LOCAL_PORT="${LOCAL_PORT:-5432}"
AWS_PROFILE="${AWS_PROFILE:-zivohealth}"
FORWARDED_PORT="${FORWARDED_PORT:-15432}"

echo "================================================"
echo "Copy $TABLE_NAME from Local to RDS via SSM"
echo "================================================"

# Get AWS configuration
echo "🔍 Getting AWS configuration..."
EC2_INSTANCE_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=*zivohealth*" "Name=instance-state-name,Values=running" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text \
    --profile "$AWS_PROFILE")

RDS_HOST=$(aws ssm get-parameter --name "/zivohealth/production/db/host" --with-decryption --profile "$AWS_PROFILE" --query "Parameter.Value" --output text)
RDS_USER=$(aws ssm get-parameter --name "/zivohealth/production/db/user" --with-decryption --profile "$AWS_PROFILE" --query "Parameter.Value" --output text)
RDS_PASSWORD=$(aws ssm get-parameter --name "/zivohealth/production/db/password" --with-decryption --profile "$AWS_PROFILE" --query "Parameter.Value" --output text)
RDS_DB="zivohealth_dev"

echo "✓ EC2 Instance ID: $EC2_INSTANCE_ID"
echo "✓ RDS Host: $RDS_HOST"
echo "✓ RDS Database: $RDS_DB"

# Count rows in local table
echo ""
echo "📊 Counting rows in local table..."
LOCAL_COUNT=$(psql -h "$LOCAL_HOST" -p "$LOCAL_PORT" -U "$LOCAL_USER" -d "$LOCAL_DB" -t -c "SELECT COUNT(*) FROM $TABLE_NAME;" 2>/dev/null | xargs || echo "0")
if [ "$LOCAL_COUNT" = "0" ]; then
    echo "❌ Could not connect to local database or table is empty"
    exit 1
fi
echo "✓ Local table has $LOCAL_COUNT rows"

# Start SSM port forwarding
echo ""
echo "🔧 Starting SSM port forwarding..."
echo "   Forwarding localhost:$FORWARDED_PORT → RDS:5432"

# Start port forwarding in background
aws ssm start-session \
    --target "$EC2_INSTANCE_ID" \
    --document-name AWS-StartPortForwardingSessionToRemoteHost \
    --parameters "{\"host\":[\"$RDS_HOST\"],\"portNumber\":[\"5432\"],\"localPortNumber\":[\"$FORWARDED_PORT\"]}" \
    --profile "$AWS_PROFILE" > /tmp/ssm_session.log 2>&1 &

SSM_PID=$!
echo "✓ SSM session started (PID: $SSM_PID)"

# Cleanup function
cleanup() {
    echo ""
    echo "🧹 Cleaning up..."
    if [ -n "$SSM_PID" ] && kill -0 $SSM_PID 2>/dev/null; then
        kill $SSM_PID 2>/dev/null || true
        wait $SSM_PID 2>/dev/null || true
    fi
    # Also kill any remaining SSM sessions
    pkill -f "start-session.*$EC2_INSTANCE_ID" 2>/dev/null || true
    echo "✓ SSM tunnel closed"
}

trap cleanup EXIT INT TERM

# Wait for tunnel to be ready
echo "⏳ Waiting for SSM tunnel to be ready..."
MAX_WAIT=30
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if nc -z localhost $FORWARDED_PORT 2>/dev/null; then
        echo "✓ Tunnel is ready!"
        break
    fi
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    if [ $((WAIT_COUNT % 5)) -eq 0 ]; then
        echo "   Still waiting... ($WAIT_COUNT/$MAX_WAIT seconds)"
    fi
done

if [ $WAIT_COUNT -eq $MAX_WAIT ]; then
    echo "❌ Tunnel failed to establish after $MAX_WAIT seconds"
    echo "Check /tmp/ssm_session.log for details"
    exit 1
fi

# Test RDS connection
echo ""
echo "🔍 Testing RDS connection..."
if ! PGPASSWORD="$RDS_PASSWORD" psql -h localhost -p "$FORWARDED_PORT" -U "$RDS_USER" -d "$RDS_DB" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Could not connect to RDS through SSM tunnel"
    exit 1
fi
echo "✓ RDS connection successful"

# Create dump and restore using custom format (handles pgvector better)
echo ""
echo "📦 Creating binary dump from local PostgreSQL..."
DUMP_FILE="/tmp/${TABLE_NAME}_$(date +%Y%m%d_%H%M%S).dump"

pg_dump -h "$LOCAL_HOST" -p "$LOCAL_PORT" -U "$LOCAL_USER" -d "$LOCAL_DB" \
    -t "$TABLE_NAME" \
    --no-owner --no-acl --data-only \
    -Fc \
    -f "$DUMP_FILE"

DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
echo "✓ Binary dump created: $DUMP_FILE ($DUMP_SIZE)"

echo ""
echo "📥 Restoring to RDS using pg_restore..."
PGPASSWORD="$RDS_PASSWORD" pg_restore -h localhost -p "$FORWARDED_PORT" -U "$RDS_USER" -d "$RDS_DB" \
    --no-owner --no-acl --data-only \
    "$DUMP_FILE"

echo "✓ Restore completed"

# Clean up dump file
rm -f "$DUMP_FILE"
echo "✓ Temporary dump file removed"

# Verify on RDS
echo ""
echo "🔍 Verifying data on RDS..."
RDS_COUNT=$(PGPASSWORD="$RDS_PASSWORD" psql -h localhost -p "$FORWARDED_PORT" -U "$RDS_USER" -d "$RDS_DB" -t -c "SELECT COUNT(*) FROM $TABLE_NAME;" | xargs)
echo "✓ RDS table now has $RDS_COUNT rows"

echo ""
echo "================================================"
if [ "$LOCAL_COUNT" = "$RDS_COUNT" ]; then
    echo "✅ Copy completed successfully! Row counts match."
    echo "   Local: $LOCAL_COUNT rows"
    echo "   RDS: $RDS_COUNT rows"
else
    echo "⚠️  Warning: Row counts don't match!"
    echo "   Local: $LOCAL_COUNT rows"
    echo "   RDS: $RDS_COUNT rows"
fi
echo "================================================"

