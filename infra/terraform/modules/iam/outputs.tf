output "instance_profile_name" {
  value = aws_iam_instance_profile.ec2_profile.name
}

output "ec2_role_arn" {
  value = aws_iam_role.ec2_role.arn
}

output "ec2_role_name" {
  value = aws_iam_role.ec2_role.name
}

output "ecs_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = aws_iam_role.ecs_task.arn
}
