output "ec2_public_ip" {
  value       = module.compute.public_ip
  description = "Public IP of the EC2 instance"
}

output "ecr_repository_url" {
  value       = module.ecr.repository_url
  description = "ECR repository URL for backend image"
}

output "rds_endpoint" {
  value       = module.db.endpoint
  description = "RDS PostgreSQL endpoint"
}

output "ec2_instance_id" {
  value       = module.compute.instance_id
  description = "EC2 instance ID for SSM port forwarding"
}

output "ssm_image_tag_param_name" {
  value       = module.ssm.image_tag_param_name
  description = "SSM parameter name that stores the desired image tag for deploy watcher"
}
