# Required
image_tag = "latest"
environment = "production"

# Database configuration
db_password_ssm_name = "/zivohealth/production/db/password"

# Optional: enable SSH tunneling (port 22) alongside SSM
# Set your IP in CIDR format like "203.0.113.25/32" to restrict access
enable_ssh_tunnel = false
ssh_allowed_cidrs = []

# Optional: existing EC2 key pair name to allow key-based SSH
# Set to null to skip
ssh_key_name = "ec2-dbeaver"
