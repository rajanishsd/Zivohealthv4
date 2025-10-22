output "sqs_queue_url" {
  description = "URL of the ML worker SQS queue"
  value       = aws_sqs_queue.ml_worker.url
}

output "sqs_queue_arn" {
  description = "ARN of the ML worker SQS queue"
  value       = aws_sqs_queue.ml_worker.arn
}

output "sqs_dlq_url" {
  description = "URL of the ML worker dead letter queue"
  value       = aws_sqs_queue.ml_worker_dlq.url
}

output "sqs_dlq_arn" {
  description = "ARN of the ML worker dead letter queue"
  value       = aws_sqs_queue.ml_worker_dlq.arn
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.ml_worker.name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.ml_worker.arn
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.ml_worker.name
}

output "ecs_task_definition_arn" {
  description = "ARN of the ECS task definition"
  value       = aws_ecs_task_definition.ml_worker.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name for ML worker"
  value       = aws_cloudwatch_log_group.ml_worker.name
}

output "security_group_id" {
  description = "Security group ID for ML worker tasks"
  value       = aws_security_group.ml_worker.id
}

