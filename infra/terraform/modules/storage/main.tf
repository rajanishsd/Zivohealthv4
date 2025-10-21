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

resource "aws_s3_bucket_policy" "allow_ec2_read_compose" {
  bucket = aws_s3_bucket.uploads.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid      = "AllowEC2InstanceReadCompose",
        Effect   = "Allow",
        Principal = "*",
        Condition = {
          ArnLike = {
            "aws:PrincipalArn" = [
              "arn:aws:sts::474221740916:assumed-role/zivohealth-production-ec2-role/*",
              "arn:aws:sts::474221740916:assumed-role/zivohealth-dev-ec2-role/*"
            ]
          }
        },
        Action   = [
          "s3:GetObject"
        ],
        Resource = [
          "${aws_s3_bucket.uploads.arn}/deploy/${var.environment}/*"
        ]
      },
      {
        Sid      = "AllowEC2InstanceListBucket",
        Effect   = "Allow",
        Principal = "*",
        Condition = {
          ArnLike = {
            "aws:PrincipalArn" = [
              "arn:aws:sts::474221740916:assumed-role/zivohealth-production-ec2-role/*",
              "arn:aws:sts::474221740916:assumed-role/zivohealth-dev-ec2-role/*"
            ]
          }
        },
        Action   = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ],
        Resource = [
          "${aws_s3_bucket.uploads.arn}"
        ]
      },
      {
        Sid      = "AllowEC2InstancePutUploads",
        Effect   = "Allow",
        Principal = "*",
        Condition = {
          ArnLike = {
            "aws:PrincipalArn" = [
              "arn:aws:sts::474221740916:assumed-role/zivohealth-production-ec2-role/*",
              "arn:aws:sts::474221740916:assumed-role/zivohealth-dev-ec2-role/*"
            ]
          }
        },
        Action   = [
          "s3:PutObject"
        ],
        Resource = [
          "${aws_s3_bucket.uploads.arn}/uploads/*"
        ]
      },
      {
        Sid      = "AllowTextractServiceAccess",
        Effect   = "Allow",
        Principal = {
          Service = "textract.amazonaws.com"
        },
        Action   = [
          "s3:GetObject",
          "s3:ListBucket"
        ],
        Resource = [
          "${aws_s3_bucket.uploads.arn}",
          "${aws_s3_bucket.uploads.arn}/*"
        ]
      }
    ]
  })
}
