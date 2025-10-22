# Outputs for VPC Endpoints Module

output "ecr_api_endpoint_id" {
  description = "ID of the ECR API VPC endpoint"
  value       = aws_vpc_endpoint.ecr_api.id
}

output "ecr_dkr_endpoint_id" {
  description = "ID of the ECR Docker VPC endpoint"
  value       = aws_vpc_endpoint.ecr_dkr.id
}

output "s3_endpoint_id" {
  description = "ID of the S3 VPC endpoint"
  value       = aws_vpc_endpoint.s3.id
}

output "ssm_endpoint_id" {
  description = "ID of the SSM VPC endpoint"
  value       = aws_vpc_endpoint.ssm.id
}

output "logs_endpoint_id" {
  description = "ID of the CloudWatch Logs VPC endpoint"
  value       = aws_vpc_endpoint.logs.id
}

output "sqs_endpoint_id" {
  description = "ID of the SQS VPC endpoint"
  value       = aws_vpc_endpoint.sqs.id
}

output "vpc_endpoints_sg_id" {
  description = "Security Group ID for VPC endpoints"
  value       = aws_security_group.vpc_endpoints.id
}

