data "aws_iam_policy_document" "assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_role" {
  name               = "${var.project}-${var.environment}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "ssm_params_read" {
  name = "${var.project}-${var.environment}-ssm-params-read"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParameterHistory"
        ],
        Resource = [
          "arn:aws:ssm:*:*:parameter/${var.project}/${var.environment}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "s3_textract_inline" {
  name = "${var.project}-${var.environment}-s3-textract"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = ["s3:*"],
        Resource = [
          var.storage_bucket_arn,
          "${var.storage_bucket_arn}/*"
        ]
      },
      {
        Effect   = "Allow",
        Action   = [
          "textract:StartDocumentTextDetection",
          "textract:GetDocumentTextDetection",
          "textract:StartDocumentAnalysis",
          "textract:GetDocumentAnalysis"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project}-${var.environment}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# ====================================================================
# ECS Task Execution Role (for Fargate ML Worker)
# ====================================================================

data "aws_iam_policy_document" "ecs_task_execution_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${var.project}-${var.environment}-ecs-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json
  
  tags = {
    Name        = "${var.project}-${var.environment}-ecs-task-execution"
    Environment = var.environment
  }
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow reading SSM parameters (for secrets)
resource "aws_iam_role_policy" "ecs_task_execution_ssm" {
  name = "${var.project}-${var.environment}-ecs-task-execution-ssm"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ],
        Resource = [
          "arn:aws:ssm:*:*:parameter/${var.project}/${var.environment}/*",
          "arn:aws:ssm:*:*:parameter/${var.project}/dev/db/password"  # Temporary: dev password until prod password is created
        ]
      }
    ]
  })
}

# ====================================================================
# ECS Task Role (for Fargate ML Worker runtime permissions)
# ====================================================================

data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task" {
  name               = "${var.project}-${var.environment}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
  
  tags = {
    Name        = "${var.project}-${var.environment}-ecs-task"
    Environment = var.environment
  }
}

# Allow SQS access (for ML worker to receive/delete messages)
resource "aws_iam_role_policy" "ecs_task_sqs" {
  name = "${var.project}-${var.environment}-ecs-task-sqs"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ],
        Resource = "arn:aws:sqs:*:*:${var.environment}-ml-worker*"
      }
    ]
  })
}

# Allow S3 access (same as EC2 role)
resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "${var.project}-${var.environment}-ecs-task-s3"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = ["s3:*"],
        Resource = [
          var.storage_bucket_arn,
          "${var.storage_bucket_arn}/*"
        ]
      }
    ]
  })
}
