resource "random_password" "db" {
  length  = 20
  special = true
}

locals {
  effective_db_password = var.db_password_plain != "" ? var.db_password_plain : random_password.db.result
}

resource "aws_ssm_parameter" "image_tag" {
  name  = "/${var.project}/${var.environment}/deploy/image_tag"
  type  = "String"
  value = var.image_tag
}

resource "aws_ssm_parameter" "db_password" {
  name  = var.db_password_ssm_key
  type  = "SecureString"
  value = local.effective_db_password
}

resource "aws_ssm_parameter" "db_host" {
  name  = "/${var.project}/${var.environment}/db/host"
  type  = "String"
  value = var.db_endpoint
}

resource "aws_ssm_parameter" "db_user" {
  name  = "/${var.project}/${var.environment}/db/user"
  type  = "String"
  value = var.db_username
}

resource "aws_ssm_parameter" "s3_bucket" {
  name  = "/${var.project}/${var.environment}/s3/bucket"
  type  = "String"
  value = var.s3_bucket_name
}

# Reminder service parameters (optional - can be set manually in AWS console)
resource "aws_ssm_parameter" "reminders_fcm_credentials_json" {
  count = var.reminders_fcm_credentials_json != "" ? 1 : 0
  name  = "/${var.project}/${var.environment}/reminders/fcm_credentials_json"
  type  = "SecureString"
  value = var.reminders_fcm_credentials_json
}

resource "aws_ssm_parameter" "reminders_fcm_project_id" {
  count = var.reminders_fcm_project_id != "" ? 1 : 0
  name  = "/${var.project}/${var.environment}/reminders/fcm_project_id"
  type  = "String"
  value = var.reminders_fcm_project_id
}
