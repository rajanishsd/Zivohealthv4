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

variable "reminders_fcm_credentials_json" {
  type        = string
  description = "FCM service account JSON credentials for reminders service"
  default     = ""
  sensitive   = true
}

variable "reminders_fcm_project_id" {
  type        = string
  description = "FCM project ID for reminders service"
  default     = ""
}
