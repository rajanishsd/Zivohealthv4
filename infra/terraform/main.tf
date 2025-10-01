# Use existing RDS VPC instead of creating new one
data "aws_vpc" "existing" {
  id = "vpc-04d23036cd269f2a6"
}

data "aws_subnets" "existing_public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.existing.id]
  }
  filter {
    name   = "map-public-ip-on-launch"
    values = ["true"]
  }
}

data "aws_subnets" "existing_private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.existing.id]
  }
  filter {
    name   = "map-public-ip-on-launch"
    values = ["false"]
  }
}

# Create security group in existing VPC
resource "aws_security_group" "ec2_existing_vpc" {
  name_prefix = "${var.project_name}-${var.environment}-ec2-"
  vpc_id      = data.aws_vpc.existing.id
  description = "Security group for EC2 instances in existing VPC"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH access"
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP access"
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS access"
  }

  # LiveKit signaling (HTTP/WS)
  ingress {
    from_port   = 7880
    to_port     = 7880
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "LiveKit signaling (WS)"
  }

  # LiveKit TCP fallback/TURN
  ingress {
    from_port   = 7881
    to_port     = 7881
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "LiveKit TCP fallback/TURN"
  }

  # LiveKit RTP/RTCP media over UDP
  ingress {
    from_port   = 50000
    to_port     = 60000
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "LiveKit media (UDP 50000-60000)"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-ec2-sg"
  }
}

module "storage" {
  source      = "./modules/storage"
  project     = var.project_name
  environment = var.environment
  bucket_name = "zivohealth-data"
}

module "iam" {
  source              = "./modules/iam"
  project             = var.project_name
  environment         = var.environment
  storage_bucket_arn  = module.storage.bucket_arn
}

module "ecr" {
  source      = "./modules/ecr"
  project     = var.project_name
  environment = var.environment
}

# Use existing RDS database instead of creating new one
data "aws_db_instance" "existing" {
  db_instance_identifier = "zivohealth-dev-postgres"
}

# Add security group rule to allow EC2 to access RDS
resource "aws_security_group_rule" "ec2_to_rds" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.ec2_existing_vpc.id
  security_group_id        = "sg-09f7899176373ad8e"  # RDS security group
  description              = "Allow EC2 access to RDS"
}

module "ssm" {
  source                = "./modules/ssm"
  project               = var.project_name
  environment           = var.environment
  image_tag             = var.image_tag
  db_endpoint           = data.aws_db_instance.existing.endpoint
  db_username           = var.db_username
  db_password_ssm_key   = var.db_password_ssm_name
  s3_bucket_name        = module.storage.bucket_name
  db_password_plain     = "zivo_890"
  reminders_fcm_credentials_json = var.reminders_fcm_credentials_json
  reminders_fcm_project_id = var.reminders_fcm_project_id
}

module "compute" {
  source                = "./modules/compute"
  project               = var.project_name
  environment           = var.environment
  vpc_id                = data.aws_vpc.existing.id
  public_subnet_id      = data.aws_subnets.existing_public.ids[0]
  instance_profile_name = module.iam.instance_profile_name
  security_group_ids    = [aws_security_group.ec2_existing_vpc.id]
  ecr_repo_url          = module.ecr.repository_url
  ssm_image_tag_param   = module.ssm.image_tag_param_name
  aws_region            = var.aws_region
  enable_ssh_tunnel     = var.enable_ssh_tunnel
  ssh_allowed_cidrs     = var.ssh_allowed_cidrs
  key_name              = var.ssh_key_name
  valid_api_keys_override = var.valid_api_keys_override
  app_secret_key_override = var.app_secret_key_override
  
  # Reminder service configuration
  reminder_service_host                    = var.reminder_service_host
  reminder_service_port                    = var.reminder_service_port
  reminder_rabbitmq_url                    = var.reminder_rabbitmq_url
  reminder_rabbitmq_exchange               = var.reminder_rabbitmq_exchange
  reminder_rabbitmq_input_queue            = var.reminder_rabbitmq_input_queue
  reminder_rabbitmq_output_queue           = var.reminder_rabbitmq_output_queue
  reminder_rabbitmq_input_routing_key      = var.reminder_rabbitmq_input_routing_key
  reminder_rabbitmq_output_routing_key     = var.reminder_rabbitmq_output_routing_key
  reminder_scheduler_scan_interval_seconds = var.reminder_scheduler_scan_interval_seconds
  reminder_scheduler_batch_size            = var.reminder_scheduler_batch_size
  reminder_metrics_enabled                 = var.reminder_metrics_enabled
  reminders_fcm_credentials_json           = var.reminders_fcm_credentials_json
  reminders_fcm_project_id                 = var.reminders_fcm_project_id
}

module "route53" {
  source      = "./modules/route53"
  project     = var.project_name
  environment = var.environment
  zone_name   = "zivohealth.ai"
  target_ip   = module.compute.public_ip
}
