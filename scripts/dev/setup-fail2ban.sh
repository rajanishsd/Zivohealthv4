#!/bin/bash
# Fail2Ban Setup Script for ZivoHealth API
# Protects against automated attacks targeting .env files, .git, and other sensitive paths

set -e

echo "🛡️  Setting up Fail2Ban to block API attacks..."
echo "================================================"

# Install fail2ban
echo ""
echo "📦 Installing fail2ban..."
sudo yum install -y fail2ban

# Enable and start fail2ban service
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Create filter for API env file scanning attacks
echo ""
echo "📝 Creating custom filter for API attacks..."
sudo tee /etc/fail2ban/filter.d/api-env-scan.conf > /dev/null <<'EOF'
[Definition]
# Detect attempts to access .env files
failregex = ^.*"(HEAD|GET|POST) /\.env[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /\.git[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /config\.json[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /\.aws[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /credentials[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /secrets[^"]*" 401.*$

ignoreregex =
EOF

# Create jail configuration
echo ""
echo "🔒 Creating jail configuration..."
sudo tee /etc/fail2ban/jail.d/api-protection.conf > /dev/null <<'EOF'
[api-env-scan]
enabled = true
port = http,https
filter = api-env-scan
logpath = /var/log/docker/zivohealth-api.log
maxretry = 5
findtime = 300
bantime = 3600
action = iptables-multiport[name=API-ATTACK, port="http,https"]
EOF

# Create directory for docker logs if it doesn't exist
sudo mkdir -p /var/log/docker

# Set up log forwarding from docker to file
echo ""
echo "📋 Setting up Docker log forwarding..."

# Create docker log monitoring script
sudo tee /usr/local/bin/monitor-docker-logs.sh > /dev/null <<'EOF'
#!/bin/bash
# Monitor Docker logs and forward to file for fail2ban

LOG_FILE="/var/log/docker/zivohealth-api.log"

# Create log file if it doesn't exist
touch "$LOG_FILE"

# Stream docker logs to file
docker logs -f zivohealth-api 2>&1 | while read line; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') $line" >> "$LOG_FILE"
done
EOF

sudo chmod +x /usr/local/bin/monitor-docker-logs.sh

# Create systemd service for log monitoring
sudo tee /etc/systemd/system/docker-api-logs.service > /dev/null <<'EOF'
[Unit]
Description=Docker API Log Monitoring for Fail2Ban
After=docker.service
Requires=docker.service

[Service]
Type=simple
ExecStart=/usr/local/bin/monitor-docker-logs.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start log monitoring service
sudo systemctl daemon-reload
sudo systemctl enable docker-api-logs.service
sudo systemctl start docker-api-logs.service

# Restart fail2ban to apply changes
echo ""
echo "🔄 Restarting fail2ban..."
sudo systemctl restart fail2ban

# Show status
echo ""
echo "✅ Fail2Ban setup complete!"
echo ""
echo "📊 Status:"
sudo fail2ban-client status

echo ""
echo "🔍 To check API protection jail status:"
echo "   sudo fail2ban-client status api-env-scan"
echo ""
echo "📋 To view banned IPs:"
echo "   sudo fail2ban-client status api-env-scan"
echo ""
echo "🔓 To unban an IP:"
echo "   sudo fail2ban-client set api-env-scan unbanip <IP_ADDRESS>"
echo ""
echo "📝 View fail2ban log:"
echo "   sudo tail -f /var/log/fail2ban.log"
echo ""

# Show current configuration
echo "🛡️  Protection Rules:"
echo "   - Max retries: 5 suspicious requests"
echo "   - Time window: 300 seconds (5 minutes)"
echo "   - Ban duration: 3600 seconds (1 hour)"
echo "   - Protected paths: /.env*, /.git*, /config.json, /.aws*, /credentials*, /secrets*"
echo ""
echo "✅ Your API is now protected against automated attacks!"

