variable "project_name" {
  type        = string
  description = "Project name prefix for resource naming"
  default     = "zivohealth"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Environment name (dev/staging/prod)"
  default     = "dev"
}

variable "image_tag" {
  type        = string
  description = "ECR image tag to deploy"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for VPC"
  default     = "10.20.0.0/16"
}

variable "db_username" {
  type        = string
  description = "PostgreSQL username"
  default     = "zivo"
}

variable "db_password_ssm_name" {
  type        = string
  description = "SSM parameter name storing the PostgreSQL password (SecureString)"
  default     = "/zivohealth/dev/db/password"
}

variable "domain_name" {
  type        = string
  description = "Optional domain name to point to EC2 (Route53)"
  default     = null
}

variable "enable_ssh_tunnel" {
  type        = bool
  description = "Whether to enable SSH ingress (port 22) for tunneling"
  default     = false
}

variable "ssh_allowed_cidrs" {
  type        = list(string)
  description = "CIDR blocks allowed to SSH if enable_ssh_tunnel is true"
  default     = []
}

variable "ssh_key_name" {
  type        = string
  description = "Existing EC2 key pair name to attach for SSH (optional)"
  default     = null
}

# API security overrides passed to compute module (optional)
variable "valid_api_keys_override" {
  type        = string
  description = "JSON array of API keys to inject into instance .env (overrides SSM)"
  default     = ""
}

variable "app_secret_key_override" {
  type        = string
  description = "App secret key to inject into instance .env (overrides SSM)"
  default     = ""
}
