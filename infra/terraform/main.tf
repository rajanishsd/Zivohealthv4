# Read REACT_APP_API_KEY from .env.production file dynamically
data "local_file" "env_production" {
  filename = "${path.module}/../../backend/.env.production"
}

locals {
  # Extract REACT_APP_API_KEY value from .env.production file
  env_lines = split("\n", data.local_file.env_production.content)
  react_app_api_key_line = [for line in local.env_lines : line if can(regex("^REACT_APP_API_KEY=", line))][0]
  react_app_api_key = trimspace(split("=", local.react_app_api_key_line)[1])
}

# Use existing RDS VPC instead of creating new one
data "aws_vpc" "existing" {
  id = "vpc-04d23036cd269f2a6"
}

# Manage DNS attributes on the existing VPC to support Interface Endpoint private DNS
resource "aws_vpc" "managed_existing" {
  cidr_block = data.aws_vpc.existing.cidr_block

  enable_dns_support   = true
  enable_dns_hostnames = true

  # Do not manage tags or other attributes on the shared VPC
  lifecycle {
    ignore_changes = [tags]
  }
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

# Get route tables for private subnets (for S3 gateway endpoint)
data "aws_route_tables" "private" {
  vpc_id = data.aws_vpc.existing.id

  filter {
    name   = "association.subnet-id"
    values = data.aws_subnets.existing_private.ids
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
  ec2_role_arn = module.iam.ec2_role_arn
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
  db_endpoint           = split(":", data.aws_db_instance.existing.endpoint)[0]  # Remove port from endpoint
  db_username           = var.db_username
  db_password_ssm_key   = var.db_password_ssm_name
  s3_bucket_name        = module.storage.bucket_name
  db_password_plain     = "zivo_890"
  reminders_fcm_credentials_json = var.reminders_fcm_credentials_json
  reminders_fcm_project_id = var.reminders_fcm_project_id
  react_app_api_key     = local.react_app_api_key
  ml_worker_queue_url   = module.ml_worker.sqs_queue_url
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

  # S3-sourced compose
  compose_s3_bucket = module.storage.bucket_name
  compose_s3_key    = "deploy/${var.environment}/docker-compose.yml"
}

# VPC Endpoints - Allow Fargate tasks in private subnets to access AWS services
module "vpc_endpoints" {
  source = "./modules/vpc_endpoints"
  
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_id             = data.aws_vpc.existing.id
  private_subnet_ids = data.aws_subnets.existing_private.ids
  route_table_ids    = data.aws_route_tables.private.ids
}

# ML Worker module for lab categorization and aggregation
module "ml_worker" {
  source = "./modules/ml_worker"
  depends_on = [module.vpc_endpoints]  # Ensure VPC endpoints exist first
  
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_id             = data.aws_vpc.existing.id
  private_subnet_ids = data.aws_subnets.existing_public.ids  # Use public subnets for internet egress
  ecr_repository_url = module.ecr.registry_host
  
  # IAM roles for Fargate tasks
  execution_role_arn = module.iam.ecs_execution_role_arn
  task_role_arn      = module.iam.ecs_task_role_arn
  api_role_arn       = module.iam.ec2_role_arn
  
  # Database configuration
  db_host            = split(":", data.aws_db_instance.existing.endpoint)[0]
  db_port            = data.aws_db_instance.existing.port
  db_name            = data.aws_db_instance.existing.db_name
  
  # Worker mode: 'sqs' for queue-based triggering (enables scale-to-zero)
  # - 'sqs': Process SQS messages only (ALL domains: labs, vitals, nutrition)
  # - 'aggregation': Background worker only (no scale-to-zero, DEPRECATED)
  # - 'both': SQS + background worker (hybrid approach, DEPRECATED)
  worker_mode        = "sqs"  # All domains now use SQS for full scale-to-zero
  
  # Scaling configuration - Scale to zero for cost savings
  min_capacity       = 0  # Scale to 0 when queue is empty (saves cost)
  max_capacity       = 5  # Up to 5 workers for high load
  target_queue_depth = 0.5  # Start worker immediately when 1+ messages (1÷0.5=2 tasks, capped at max)
}

module "route53" {
  source      = "./modules/route53"
  project     = var.project_name
  environment = var.environment
  zone_name   = "zivohealth.ai"
  target_ip   = module.compute.public_ip
}

# Outputs
output "ml_worker_queue_url" {
  description = "SQS Queue URL for ML Worker"
  value       = module.ml_worker.sqs_queue_url
}

output "ml_worker_cluster_name" {
  description = "ECS Cluster name for ML Worker"
  value       = module.ml_worker.ecs_cluster_name
}

output "ml_worker_service_name" {
  description = "ECS Service name for ML Worker"
  value       = module.ml_worker.ecs_service_name
}
