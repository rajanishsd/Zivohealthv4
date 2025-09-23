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

# Reminder service configuration (optional)
variable "reminders_fcm_credentials_json" {
  type        = string
  description = "FCM service account JSON credentials for reminders service (optional)"
  default     = ""
  sensitive   = true
}

variable "reminders_fcm_project_id" {
  type        = string
  description = "FCM project ID for reminders service (optional)"
  default     = ""
}

# Reminder service configuration
variable "reminder_service_host" {
  type        = string
  description = "Reminder service host"
  default     = "0.0.0.0"
}

variable "reminder_service_port" {
  type        = number
  description = "Reminder service port"
  default     = 8085
}

variable "reminder_rabbitmq_url" {
  type        = string
  description = "RabbitMQ URL for reminders service"
  default     = "amqp://guest:guest@rabbitmq:5672//"
}

variable "reminder_rabbitmq_exchange" {
  type        = string
  description = "RabbitMQ exchange for reminders service"
  default     = "reminders.direct.v1"
}

variable "reminder_rabbitmq_input_queue" {
  type        = string
  description = "RabbitMQ input queue for reminders service"
  default     = "reminders.input.v1"
}

variable "reminder_rabbitmq_output_queue" {
  type        = string
  description = "RabbitMQ output queue for reminders service"
  default     = "reminders.output.v1"
}

variable "reminder_rabbitmq_input_routing_key" {
  type        = string
  description = "RabbitMQ input routing key for reminders service"
  default     = "input"
}

variable "reminder_rabbitmq_output_routing_key" {
  type        = string
  description = "RabbitMQ output routing key for reminders service"
  default     = "output"
}

variable "reminder_scheduler_scan_interval_seconds" {
  type        = number
  description = "Reminder scheduler scan interval in seconds"
  default     = 30
}

variable "reminder_scheduler_batch_size" {
  type        = number
  description = "Reminder scheduler batch size"
  default     = 1000
}

variable "reminder_metrics_enabled" {
  type        = bool
  description = "Enable metrics for reminders service"
  default     = true
}
