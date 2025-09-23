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
  user_data_rendered = templatefile("${path.module}/user_data.sh.tpl", {
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
  })
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
  count             = var.enable_ssh_tunnel && length(var.ssh_allowed_cidrs) > 0 ? length(var.security_group_ids) : 0
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = var.ssh_allowed_cidrs
  security_group_id = var.security_group_ids[count.index]
  description       = "Allow SSH tunneling from specified CIDRs"
}

output "public_ip" {
  value = aws_instance.host.public_ip
}

output "security_group_id" {
  value = var.security_group_ids[0]
}
