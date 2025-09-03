variable "project" { type = string }
variable "environment" { type = string }
variable "zone_name" { type = string }
variable "target_ip" { type = string }

variable "create_www_record" {
  type    = bool
  default = true
}
