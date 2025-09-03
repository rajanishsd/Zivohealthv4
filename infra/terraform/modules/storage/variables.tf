variable "project" { type = string }
variable "environment" { type = string }
variable "bucket_name" {
  type        = string
  description = "Optional fixed S3 bucket name"
  default     = ""
}
