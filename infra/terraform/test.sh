#!/bin/bash
set -e

echo "🧪 Testing ZivoHealth infrastructure..."

# Get instance details from Terraform output
INSTANCE_ID=$(terraform output -raw ec2_instance_id 2>/dev/null || echo "")
PUBLIC_IP=$(terraform output -raw ec2_public_ip 2>/dev/null || echo "")

if [ -z "$INSTANCE_ID" ]; then
    echo "❌ Error: Could not get instance ID from Terraform output"
    echo "   Make sure you've deployed the infrastructure first"
    exit 1
fi

echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
echo ""

# Test SSM connectivity
echo "🔍 Testing SSM connectivity..."
aws ssm describe-instance-information \
    --instance-information-filter-list "key=InstanceIds,valueSet=$INSTANCE_ID" \
    --profile zivohealth \
    --region us-east-1 \
    --query "InstanceInformationList[0].{InstanceId:InstanceId,PingStatus:PingStatus,LastPingDateTime:LastPingDateTime}" \
    --output table

echo ""

# Test that snapd is removed
echo "🔍 Testing snapd removal..."
COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=["sudo snap list"]' \
    --profile zivohealth \
    --region us-east-1 \
    --query "Command.CommandId" \
    --output text)

echo "Command ID: $COMMAND_ID"
echo "Waiting for command to complete..."
sleep 10

aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --profile zivohealth \
    --region us-east-1 \
    --query "StandardErrorContent" \
    --output text

echo ""

# Test application health
echo "🔍 Testing application health..."
if [ ! -z "$PUBLIC_IP" ]; then
    echo "Testing application at https://$PUBLIC_IP/health"
    curl -k -s https://$PUBLIC_IP/health || echo "Application not yet ready"
else
    echo "Public IP not available for testing"
fi

echo ""
echo "✅ Testing completed!"
