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
