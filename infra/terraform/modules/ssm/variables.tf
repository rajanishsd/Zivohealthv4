variable "project" { type = string }
variable "environment" { type = string }
variable "image_tag" { type = string }
variable "db_endpoint" { type = string }
variable "db_username" { type = string }
variable "db_password_ssm_key" { type = string }
variable "s3_bucket_name" { type = string }

variable "db_password_plain" {
  type        = string
  description = "Optional plaintext DB password to store in SSM; if empty, a random password is generated"
  default     = ""
}

variable "reminders_fcm_credentials_json" {
  type        = string
  description = "Optional FCM service account JSON credentials for reminders service"
  default     = ""
  sensitive   = true
}

variable "reminders_fcm_project_id" {
  type        = string
  description = "Optional FCM project ID for reminders service"
  default     = ""
}

variable "react_app_api_key" {
  type        = string
  description = "API key for React dashboard app"
  sensitive   = true
}

variable "ml_worker_queue_url" {
  description = "ML worker SQS queue URL"
  type        = string
  default     = ""
}
