variable "project" { type = string }
variable "environment" { type = string }

# Storage bucket ARN passed from storage module if needed
variable "storage_bucket_arn" {
  type        = string
  description = "ARN of the S3 bucket for app storage"
  default     = "*"
}
