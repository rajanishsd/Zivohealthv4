data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  rendered_compose = templatefile("${path.module}/docker-compose.yml.tpl", {
    # Derive the ECR registry host without depending on the ECR module to avoid unnecessary replacements
    ECR_REGISTRY_HOST = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
    IMAGE_TAG    = "latest"
    AWS_REGION   = var.aws_region
    reminder_service_port = var.reminder_service_port
  })

  compose_sha256 = sha256(local.rendered_compose)

  user_data_rendered = templatefile("${path.module}/user_data_minimal.sh.tpl", {
    ECR_REPO_URL        = var.ecr_repo_url
    IMAGE_TAG           = "latest"
    SSM_IMAGE_TAG_PARAM = var.ssm_image_tag_param
    AWS_REGION          = var.aws_region
    PROJECT             = var.project
    ENVIRONMENT         = var.environment
    VALID_API_KEYS_OVERRIDE = var.valid_api_keys_override
    APP_SECRET_KEY_OVERRIDE = var.app_secret_key_override
    reminder_service_host = var.reminder_service_host
    reminder_service_port = var.reminder_service_port
    reminder_rabbitmq_url = var.reminder_rabbitmq_url
    reminder_rabbitmq_exchange = var.reminder_rabbitmq_exchange
    reminder_rabbitmq_input_queue = var.reminder_rabbitmq_input_queue
    reminder_rabbitmq_output_queue = var.reminder_rabbitmq_output_queue
    reminder_rabbitmq_input_routing_key = var.reminder_rabbitmq_input_routing_key
    reminder_rabbitmq_output_routing_key = var.reminder_rabbitmq_output_routing_key
    reminder_scheduler_scan_interval_seconds = var.reminder_scheduler_scan_interval_seconds
    reminder_scheduler_batch_size = var.reminder_scheduler_batch_size
    reminder_metrics_enabled = var.reminder_metrics_enabled
    REMINDER_FCM_CREDENTIALS_JSON = var.reminders_fcm_credentials_json
    REMINDER_FCM_PROJECT_ID = var.reminders_fcm_project_id
    COMPOSE_S3_BUCKET = var.compose_s3_bucket
    COMPOSE_S3_KEY    = var.compose_s3_key
    COMPOSE_SHA256    = local.compose_sha256
  })
}

resource "aws_s3_object" "compose" {
  bucket  = var.compose_s3_bucket
  key     = var.compose_s3_key
  content = local.rendered_compose
  etag    = md5(local.rendered_compose)
}

resource "aws_ssm_parameter" "compose_sha256" {
  name  = "/${var.project}/${var.environment}/deploy/docker_compose_sha256"
  type  = "String"
  value = local.compose_sha256
}

resource "aws_instance" "host" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t2.small"
  subnet_id                   = var.public_subnet_id
  vpc_security_group_ids      = var.security_group_ids
  iam_instance_profile        = var.instance_profile_name
  associate_public_ip_address = true
  key_name                    = var.key_name

  user_data = local.user_data_rendered

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    delete_on_termination = true
  }

  tags = {
    Name = "${var.project}-${var.environment}-ec2-no-snapd"
  }
}

# Optionally open SSH on attached Security Group(s) when enable_ssh_tunnel is true
resource "aws_security_group_rule" "allow_ssh" {
  count = var.enable_ssh_tunnel && length(var.ssh_allowed_cidrs) > 0 ? 1 : 0

  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = var.ssh_allowed_cidrs
  security_group_id = var.security_group_ids[0]
  description       = "Allow SSH tunneling from specified CIDRs"

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [cidr_blocks]
  }
}

output "public_ip" {
  value = aws_instance.host.public_ip
}

output "security_group_id" {
  value = var.security_group_ids[0]
}
