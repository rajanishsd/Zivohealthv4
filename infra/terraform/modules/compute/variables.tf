variable "project" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_id" { type = string }
variable "instance_profile_name" { type = string }
variable "security_group_ids" { type = list(string) }
variable "ecr_repo_url" { type = string }
variable "ssm_image_tag_param" { type = string }
variable "aws_region" { type = string }

# Optional overrides for API security; if set, they take precedence over SSM
variable "valid_api_keys_override" {
  type        = string
  description = "JSON array of API keys to inject into .env (overrides SSM)"
  default     = ""
}

variable "app_secret_key_override" {
  type        = string
  description = "App secret key for HMAC to inject into .env (overrides SSM)"
  default     = ""
}

variable "enable_ssh_tunnel" {
  type        = bool
  description = "Whether to enable SSH ingress for tunneling on port 22"
  default     = false
}

variable "ssh_allowed_cidrs" {
  type        = list(string)
  description = "List of CIDR blocks allowed to SSH when enable_ssh_tunnel is true"
  default     = []
}

variable "key_name" {
  type        = string
  description = "Existing EC2 key pair name to attach for SSH (optional)"
  default     = null
}
