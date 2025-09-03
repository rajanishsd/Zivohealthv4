resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  computed_bucket_name = "${var.project}-${var.environment}-uploads-${random_id.suffix.hex}"
  final_bucket_name    = var.bucket_name != "" ? var.bucket_name : local.computed_bucket_name
}

resource "aws_s3_bucket" "uploads" {
  bucket = local.final_bucket_name
}
