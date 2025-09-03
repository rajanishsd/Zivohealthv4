# ZivoHealth Backend CD (Terraform)

This Terraform stack provisions AWS resources for continuous delivery of the backend on a single EC2 instance using Docker Compose. CI (image build/push) is independent; deployment is controlled by an SSM parameter `image_tag` and a deploy-watcher on EC2.

High-level:
- VPC with public subnets
- IAM role/profile for EC2 (ECR pull, S3, Textract, SSM)
- ECR repo for the backend image
- S3 bucket for uploads/Textract
- RDS PostgreSQL (free tier)
- SSM Parameter Store for deployment `image_tag` (and room for app config)
- EC2 t2.micro with Docker and a deploy watcher

Workflow:
1) Build and push image to ECR locally (tag with git SHA).
2) `terraform apply -var image_tag=<git-sha>`
3) EC2 deploy-watcher pulls the new tag from SSM, updates Docker Compose, and restarts containers.

Modules are under `modules/`. Adjust variables in `variables.tf` and pass sensitive values via a `tfvars` file.
