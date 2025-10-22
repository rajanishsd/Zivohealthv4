output "repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "registry_host" {
  description = "ECR registry host (without repository name)"
  value       = split("/", aws_ecr_repository.backend.repository_url)[0]
}
