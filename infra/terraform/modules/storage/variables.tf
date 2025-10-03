variable "project" { type = string }
variable "environment" { type = string }
variable "bucket_name" {
  type        = string
  description = "Optional fixed S3 bucket name"
  default     = ""
}

variable "ec2_role_arn" {
  type        = string
  description = "EC2 role ARN permitted to read compose objects"
}
