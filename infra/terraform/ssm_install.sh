#!/bin/bash

# SSM Agent Installation and Configuration Script for Ubuntu 22.04

echo "Starting SSM Agent installation and configuration..."

# Update system packages
sudo apt-get update -y

# Remove any existing SSM agent installations
echo "Removing existing SSM agent installations..."
sudo snap remove amazon-ssm-agent 2>/dev/null || true
sudo systemctl stop amazon-ssm-agent 2>/dev/null || true
sudo systemctl disable amazon-ssm-agent 2>/dev/null || true

# Install dependencies
echo "Installing dependencies..."
sudo apt-get install -y curl wget

# Download and install the latest SSM agent
echo "Downloading SSM agent..."
cd /tmp
wget https://s3.amazonaws.com/ec2-downloads-windows/SSMAgent/latest/debian_amd64/amazon-ssm-agent.deb

# Install the SSM agent
echo "Installing SSM agent..."
sudo dpkg -i amazon-ssm-agent.deb

# Start and enable the SSM agent
echo "Starting SSM agent..."
sudo systemctl start amazon-ssm-agent
sudo systemctl enable amazon-ssm-agent

# Check status
echo "Checking SSM agent status..."
sudo systemctl status amazon-ssm-agent

# Clean up
rm -f amazon-ssm-agent.deb

echo "SSM Agent installation completed!"