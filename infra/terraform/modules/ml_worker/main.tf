# ML Worker Infrastructure
# SQS Queue + Fargate Spot Service for cost-efficient ML processing

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# Data source to get AWS account ID
data "aws_caller_identity" "current" {}

# ====================================================================
# SQS Queues for ML Worker Jobs
# ====================================================================

# Dead Letter Queue (DLQ) - for failed messages
resource "aws_sqs_queue" "ml_worker_dlq" {
  name                      = "${var.environment}-ml-worker-dlq"
  message_retention_seconds = 1209600  # 14 days
  
  tags = {
    Name        = "${var.environment}-ml-worker-dlq"
    Environment = var.environment
    Purpose     = "ML Worker Dead Letter Queue"
  }
}

# Main Queue - for ML processing jobs
resource "aws_sqs_queue" "ml_worker" {
  name                      = "${var.environment}-ml-worker"
  delay_seconds             = 0
  max_message_size          = 262144  # 256 KB
  message_retention_seconds = 345600  # 4 days
  receive_wait_time_seconds = 20      # Long polling
  visibility_timeout_seconds = 300    # 5 minutes (enough for ML processing)
  
  # Dead letter queue configuration
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ml_worker_dlq.arn
    maxReceiveCount     = 3  # Retry 3 times before DLQ
  })
  
  tags = {
    Name        = "${var.environment}-ml-worker"
    Environment = var.environment
    Purpose     = "ML Worker Job Queue"
  }
}

# SQS Queue Policy - Allow necessary access
resource "aws_sqs_queue_policy" "ml_worker" {
  queue_url = aws_sqs_queue.ml_worker.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAPIToSendMessages"
        Effect = "Allow"
        Principal = {
          AWS = var.api_role_arn
        }
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueUrl"
        ]
        Resource = aws_sqs_queue.ml_worker.arn
      }
    ]
  })
}

# ====================================================================
# CloudWatch Alarms for Queue Monitoring
# ====================================================================

resource "aws_cloudwatch_metric_alarm" "queue_depth_high" {
  alarm_name          = "${var.environment}-ml-worker-queue-depth-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = "300"  # 5 minutes
  statistic           = "Average"
  threshold           = "10"
  alarm_description   = "This metric monitors ML worker queue depth"
  alarm_actions       = []  # Add SNS topic if you want notifications
  
  dimensions = {
    QueueName = aws_sqs_queue.ml_worker.name
  }
}

resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  alarm_name          = "${var.environment}-ml-worker-dlq-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "Alert when messages enter DLQ"
  alarm_actions       = []  # Add SNS topic for critical alerts
  
  dimensions = {
    QueueName = aws_sqs_queue.ml_worker_dlq.name
  }
}

# ====================================================================
# ECS Cluster for Fargate
# ====================================================================

resource "aws_ecs_cluster" "ml_worker" {
  name = "${var.environment}-ml-worker-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  
  tags = {
    Name        = "${var.environment}-ml-worker-cluster"
    Environment = var.environment
  }
}

resource "aws_ecs_cluster_capacity_providers" "ml_worker" {
  cluster_name = aws_ecs_cluster.ml_worker.name
  
  capacity_providers = ["FARGATE_SPOT", "FARGATE"]
  
  default_capacity_provider_strategy {
    base              = 0
    weight            = 100
    capacity_provider = "FARGATE_SPOT"  # Use Spot for 70% cost savings
  }
}

# ====================================================================
# CloudWatch Log Group
# ====================================================================

resource "aws_cloudwatch_log_group" "ml_worker" {
  name              = "/ecs/${var.environment}-ml-worker"
  retention_in_days = 7
  
  tags = {
    Name        = "${var.environment}-ml-worker-logs"
    Environment = var.environment
  }
}

# ====================================================================
# ECS Task Definition
# ====================================================================

resource "aws_ecs_task_definition" "ml_worker" {
  family                   = "${var.environment}-ml-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"   # 0.5 vCPU
  memory                   = "3072"  # 3 GB (enough for 2.5GB BioBERT + overhead)
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  
  container_definitions = jsonencode([{
    name      = "ml-worker"
    image     = "${var.ecr_repository_url}/zivohealth-production-ml-worker:${var.image_tag}"
    essential = true
    
    environment = [
      {
        name  = "AWS_REGION"
        value = var.aws_region
      },
      {
        name  = "ML_WORKER_MODE"
        value = var.worker_mode
      },
      {
        name  = "ML_WORKER_SQS_QUEUE_URL"
        value = aws_sqs_queue.ml_worker.url
      },
      {
        name  = "ML_WORKER_BATCH_SIZE"
        value = "1"
      },
      {
        name  = "ML_WORKER_WAIT_TIME"
        value = "20"
      },
      {
        name  = "ML_WORKER_VISIBILITY_TIMEOUT"
        value = "300"
      },
      {
        name  = "POSTGRES_SERVER"
        value = var.db_host
      },
      {
        name  = "POSTGRES_PORT"
        value = tostring(var.db_port)
      },
      {
        name  = "POSTGRES_DB"
        value = var.db_name
      },
      {
        name  = "ENVIRONMENT"
        value = var.environment
      },
      # Required by app.core.config.Settings (with defaults for ML worker)
      {
        name  = "PROJECT_NAME"
        value = "zivohealth"
      },
      {
        name  = "VERSION"
        value = "1.0.0"
      },
      {
        name  = "PROJECT_VERSION"
        value = "1.0.0"
      },
      {
        name  = "API_V1_STR"
        value = "/api/v1"
      },
      {
        name  = "SERVER_HOST"
        value = "0.0.0.0"
      },
      {
        name  = "SERVER_PORT"
        value = "8000"
      },
      {
        name  = "SECRET_KEY"
        value = "ml-worker-secret-key-not-used"
      },
      {
        name  = "ACCESS_TOKEN_EXPIRE_MINUTES"
        value = "30"
      },
      {
        name  = "ALGORITHM"
        value = "HS256"
      },
      {
        name  = "REDIS_HOST"
        value = "localhost"
      },
      {
        name  = "REDIS_PORT"
        value = "6379"
      },
      {
        name  = "REDIS_DB"
        value = "0"
      },
      {
        name  = "AWS_S3_BUCKET"
        value = "zivohealth-data"
      },
      {
        name  = "CHAT_WS_HEARTBEAT_MAX_SECONDS"
        value = "60"
      },
      {
        name  = "OCR_PROVIDER"
        value = "textract"
      },
      {
        name  = "OCR_TIMEOUT"
        value = "30"
      },
      {
        name  = "OCR_MAX_FILE_SIZE"
        value = "10485760"
      },
      {
        name  = "CORS_ORIGINS"
        value = "[]"
      },
      # Enable LOINC mapper for lab categorization with proper LOINC codes
      {
        name  = "LOINC_ENABLED"
        value = "1"
      },
      {
        name  = "LOINC_CREATE_TABLES"
        value = "0"
      },
      {
        name  = "WS_MESSAGE_QUEUE"
        value = "ws_messages"
      },
      {
        name  = "SMTP_SERVER"
        value = "smtp.zoho.in"
      },
      {
        name  = "SMTP_PORT"
        value = "587"
      },
      {
        name  = "SMTP_USERNAME"
        value = "noreply@zivohealth.ai"
      },
      {
        name  = "SMTP_PASSWORD"
        value = "not-used-in-ml-worker"
      },
      {
        name  = "FROM_EMAIL"
        value = "noreply@zivohealth.ai"
      },
      {
        name  = "FRONTEND_URL"
        value = "https://app.zivohealth.com"
      },
      {
        name  = "PASSWORD_RESET_APP_DIR"
        value = "/app/www/reset-password"
      }
    ]
    
    secrets = [
      {
        name      = "POSTGRES_USER"
        valueFrom = "${var.ssm_parameter_prefix}/db/user"
      },
      {
        name      = "POSTGRES_PASSWORD"
        valueFrom = "${var.ssm_parameter_prefix}/db/password"
      },
      {
        name      = "OPENAI_API_KEY"
        valueFrom = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/zivohealth/${var.environment}/openai/api_key"
      }
    ]
    
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ml_worker.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ml-worker"
      }
    }
    
    healthCheck = {
      command     = ["CMD-SHELL", "/app/healthcheck.sh || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
  
  tags = {
    Name        = "${var.environment}-ml-worker-task"
    Environment = var.environment
  }
}

# ====================================================================
# ECS Service with Auto-Scaling
# ====================================================================

resource "aws_ecs_service" "ml_worker" {
  name            = "${var.environment}-ml-worker"
  cluster         = aws_ecs_cluster.ml_worker.id
  task_definition = aws_ecs_task_definition.ml_worker.arn
  desired_count   = var.min_capacity  # Start with minimum
  
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ml_worker.id]
    assign_public_ip = true  # Public IP for internet egress (Hugging Face, etc.)
  }
  
  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 100
    base              = 0
  }
  
  lifecycle {
    ignore_changes = [desired_count]  # Managed by auto-scaling
  }
  
  tags = {
    Name        = "${var.environment}-ml-worker-service"
    Environment = var.environment
  }
}

# ====================================================================
# Security Group for ML Worker
# ====================================================================

resource "aws_security_group" "ml_worker" {
  name_prefix = "${var.environment}-ml-worker-"
  description = "Security group for ML Worker Fargate tasks"
  vpc_id      = var.vpc_id
  
  # Outbound: Allow all (needed for SQS, RDS, SSM, ECR)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name        = "${var.environment}-ml-worker-sg"
    Environment = var.environment
  }
}

# ====================================================================
# Auto-Scaling Configuration
# ====================================================================

resource "aws_appautoscaling_target" "ml_worker" {
  max_capacity       = var.max_capacity
  min_capacity       = var.min_capacity
  resource_id        = "service/${aws_ecs_cluster.ml_worker.name}/${aws_ecs_service.ml_worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Scale UP based on queue depth
resource "aws_appautoscaling_policy" "ml_worker_scale_up" {
  name               = "${var.environment}-ml-worker-scale-up"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ml_worker.resource_id
  scalable_dimension = aws_appautoscaling_target.ml_worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ml_worker.service_namespace
  
  target_tracking_scaling_policy_configuration {
    target_value       = var.target_queue_depth  # Target messages per task
    scale_in_cooldown  = 300  # 5 min cooldown before scaling in
    scale_out_cooldown = 60   # 1 min cooldown before scaling out
    
    customized_metric_specification {
      metric_name = "ApproximateNumberOfMessagesVisible"
      namespace   = "AWS/SQS"
      statistic   = "Average"
      unit        = "Count"
      
      dimensions {
        name  = "QueueName"
        value = aws_sqs_queue.ml_worker.name
      }
    }
  }
}

# Scale DOWN to zero when queue is empty (optional scheduled scaling)
resource "aws_appautoscaling_scheduled_action" "ml_worker_scale_down_night" {
  count = var.enable_scheduled_scaling ? 1 : 0
  
  name               = "${var.environment}-ml-worker-scale-down-night"
  service_namespace  = aws_appautoscaling_target.ml_worker.service_namespace
  resource_id        = aws_appautoscaling_target.ml_worker.resource_id
  scalable_dimension = aws_appautoscaling_target.ml_worker.scalable_dimension
  schedule           = "cron(0 2 * * ? *)"  # 2 AM UTC
  
  scalable_target_action {
    min_capacity = 0
    max_capacity = var.max_capacity
  }
}

# Scale UP during business hours (optional)
resource "aws_appautoscaling_scheduled_action" "ml_worker_scale_up_morning" {
  count = var.enable_scheduled_scaling ? 1 : 0
  
  name               = "${var.environment}-ml-worker-scale-up-morning"
  service_namespace  = aws_appautoscaling_target.ml_worker.service_namespace
  resource_id        = aws_appautoscaling_target.ml_worker.resource_id
  scalable_dimension = aws_appautoscaling_target.ml_worker.scalable_dimension
  schedule           = "cron(0 8 * * ? *)"  # 8 AM UTC
  
  scalable_target_action {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }
}

