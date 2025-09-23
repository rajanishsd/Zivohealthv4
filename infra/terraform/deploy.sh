#!/bin/bash
set -e

echo "🚀 Deploying ZivoHealth infrastructure (no-snapd version)..."

# Check if we're in the right directory
if [ ! -f "main.tf" ]; then
    echo "❌ Error: main.tf not found. Please run this script from the terraform directory."
    exit 1
fi

# Initialize Terraform
echo "📦 Initializing Terraform..."
terraform init

# Plan the deployment
echo "📋 Planning deployment..."
terraform plan -var-file="terraform.tfvars" -out=tfplan

# Ask for confirmation
echo ""
echo "⚠️  This will create/update EC2 infrastructure without snapd."
echo "   Instance type: t2.micro"
echo "   This deployment removes snapd to prevent CPU issues."
echo ""
read -p "Do you want to proceed? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled."
    exit 1
fi

# Apply the plan
echo "🔧 Applying Terraform plan..."
terraform apply tfplan

# Get the instance details
echo "📊 Getting instance details..."
INSTANCE_ID=$(terraform output -raw ec2_instance_id 2>/dev/null || echo "Instance ID not available")
PUBLIC_IP=$(terraform output -raw ec2_public_ip 2>/dev/null || echo "Public IP not available")

echo ""
echo "✅ Deployment completed!"
echo "🆕 Instance ID: $INSTANCE_ID"
echo "🌐 Public IP: $PUBLIC_IP"
echo ""
echo "🔍 Next steps:"
echo "1. Wait 5-10 minutes for the instance to fully initialize"
echo "2. Test SSM connectivity: aws ssm describe-instance-information --instance-information-filter-list 'key=InstanceIds,valueSet=$INSTANCE_ID' --profile zivohealth --region us-east-1"
echo "3. Verify no snapd: aws ssm send-command --instance-ids '$INSTANCE_ID' --document-name 'AWS-RunShellScript' --parameters 'commands=[\"sudo snap list\"]' --profile zivohealth --region us-east-1"
echo "4. Test application: curl -k https://$PUBLIC_IP/health"
echo ""
