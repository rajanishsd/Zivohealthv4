variable "environment" {
  description = "Environment name (production, staging, etc.)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_id" {
  description = "VPC ID where ML worker will run"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for Fargate tasks"
  type        = list(string)
}

variable "ecr_repository_url" {
  description = "ECR repository URL for ML worker image"
  type        = string
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "execution_role_arn" {
  description = "ECS task execution role ARN (for pulling images, accessing secrets)"
  type        = string
}

variable "task_role_arn" {
  description = "ECS task role ARN (for SQS, RDS access)"
  type        = string
}

variable "api_role_arn" {
  description = "IAM role ARN of the API service (to allow sending SQS messages)"
  type        = string
}

variable "db_host" {
  description = "Database host"
  type        = string
}

variable "db_port" {
  description = "Database port"
  type        = number
  default     = 5432
}

variable "db_name" {
  description = "Database name"
  type        = string
}

variable "ssm_parameter_prefix" {
  description = "SSM parameter prefix for secrets"
  type        = string
  default     = "/zivohealth/production"
}

variable "min_capacity" {
  description = "Minimum number of ML worker tasks"
  type        = number
  default     = 0  # Can scale to zero when no jobs
}

variable "max_capacity" {
  description = "Maximum number of ML worker tasks"
  type        = number
  default     = 3  # Scale up to 3 workers for high load
}

variable "target_queue_depth" {
  description = "Target number of messages per worker task (for auto-scaling). Set <1 to trigger with 1 message."
  type        = number
  default     = 0.5  # Auto-scale immediately with 1+ messages (1÷0.5=2 tasks)
}

variable "enable_scheduled_scaling" {
  description = "Enable scheduled scaling (scale down at night, up in morning)"
  type        = bool
  default     = false
}

variable "worker_mode" {
  description = "ML Worker mode: 'sqs' (process SQS queue), 'aggregation' (background aggregation), or 'both'"
  type        = string
  default     = "aggregation"
  
  validation {
    condition     = contains(["sqs", "aggregation", "both"], var.worker_mode)
    error_message = "worker_mode must be one of: 'sqs', 'aggregation', or 'both'"
  }
}

