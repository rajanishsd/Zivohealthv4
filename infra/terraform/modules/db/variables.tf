variable "project" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "db_username" { type = string }
variable "db_password_ssm_key" { type = string }
variable "sg_ids_allowing_db" { type = list(string) }
variable "db_password" { type = string }
