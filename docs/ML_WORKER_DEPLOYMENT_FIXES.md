# ML Worker Deployment - Permanent Fixes Applied

## Summary
All issues encountered during ML worker deployment have been **permanently fixed** in the codebase. Future deployments will not experience these problems.

---

## ✅ Fixes Applied

### 1. **Database Host Port Issue** 🔧
**Problem**: SSM parameter `/zivohealth/production/db/host` included the port (`:5432`), causing SQLAlchemy to construct invalid database URLs like `host:5432:5432`.

**Fix Location**: `infra/terraform/main.tf` (Line 152)
```terraform
# BEFORE:
db_endpoint = data.aws_db_instance.existing.endpoint

# AFTER:
db_endpoint = split(":", data.aws_db_instance.existing.endpoint)[0]  # Remove port from endpoint
```

**Impact**: EC2 API containers will now start properly with correct database connection strings.

---

### 2. **ML Worker Image Path Issue** 🐳
**Problem**: ML worker task definition used incorrect ECR image path:
- Wrong: `474221740916.dkr.ecr.us-east-1.amazonaws.com/zivohealth-production-backend/zivohealth-production-ml-worker:latest`
- Correct: `474221740916.dkr.ecr.us-east-1.amazonaws.com/zivohealth-production-ml-worker:latest`

**Fix Location**: 
1. `infra/terraform/modules/ecr/outputs.tf` - Added `registry_host` output:
```terraform
output "registry_host" {
  description = "ECR registry host (without repository name)"
  value       = split("/", aws_ecr_repository.backend.repository_url)[0]
}
```

2. `infra/terraform/main.tf` (Line 207) - Use registry_host for ML worker:
```terraform
# BEFORE:
ecr_repository_url = module.ecr.repository_url

# AFTER:
ecr_repository_url = module.ecr.registry_host
```

**Impact**: Fargate ML worker will correctly pull images from ECR.

---

### 3. **ML Worker Infrastructure Added** 🚀
**New Components**:
- ✅ Fargate Spot ECS cluster (`production-ml-worker-cluster`)
- ✅ ECS service with auto-scaling (min: 1, max: 1 for aggregation mode)
- ✅ SQS queue + Dead Letter Queue (for future SQS mode)
- ✅ CloudWatch logs (`/ecs/production-ml-worker`)
- ✅ CloudWatch alarms (queue depth, DLQ messages)
- ✅ IAM roles (ECS execution + task roles)
- ✅ Security groups (private subnet access)

**Configuration** (`infra/terraform/main.tf`, lines 199-229):
- **Mode**: `aggregation` (runs background lab categorization)
- **Resources**: 0.5 vCPU, 3GB RAM (sufficient for BioBERT)
- **Cost**: ~$7-10/month (Fargate Spot pricing)
- **Replaces**: `worker_process.py` on EC2

---

### 4. **IAM Roles for ECS** 🔐
**New Roles** (`infra/terraform/modules/iam/main.tf`):

1. **ECS Task Execution Role** (`zivohealth-production-ecs-task-execution`):
   - Pulls images from ECR
   - Writes to CloudWatch logs
   - Reads SSM parameters (database secrets)

2. **ECS Task Role** (`zivohealth-production-ecs-task`):
   - Accesses SQS queues (receive/delete messages)
   - Accesses S3 (same permissions as EC2 for document processing)

**Impact**: Fargate tasks have correct permissions to run ML workloads.

---

### 5. **Terraform Version Upgrade** ⬆️
**Updated**: AWS provider from `6.14.1` → `6.17.0`
**Reason**: Compatibility with ECS Fargate Spot capacity providers

---

## 📁 Files Modified

### Terraform Files:
1. `infra/terraform/main.tf`
   - Fixed database host parameter (line 152)
   - Added ML worker module (lines 199-229)
   - Added ML worker outputs (lines 239-255)

2. `infra/terraform/modules/ecr/outputs.tf`
   - Added `registry_host` output

3. `infra/terraform/modules/iam/main.tf`
   - Added ECS execution role
   - Added ECS task role
   - Added IAM policies for SQS, S3, SSM

4. `infra/terraform/modules/iam/outputs.tf`
   - Exported ECS role ARNs

5. `infra/terraform/modules/ml_worker/` (New Module)
   - `main.tf` - ECS cluster, service, task definition, SQS, auto-scaling
   - `variables.tf` - ML worker configuration variables
   - `outputs.tf` - SQS URL, cluster/service names

### Application Files:
- ✅ `backend/Dockerfile.worker` - ML worker container definition
- ✅ `backend/app/services/ml_worker.py` - ML worker service with 3 modes
- ✅ `scripts/dev/build-ml-worker.sh` - Build ML worker image
- ✅ `scripts/dev/push-ml-worker.sh` - Push and deploy ML worker

---

## 🎯 What Happens on Next Deployment?

When you run `terraform apply` in the future:
1. ✅ Database host parameter will be correct (no port)
2. ✅ ML worker will use correct ECR image path
3. ✅ Fargate service will start successfully
4. ✅ IAM permissions will be properly configured
5. ✅ No manual SSM parameter fixes needed

---

## 🔄 Worker Process Migration

### Old Setup (EC2):
- `worker_process.py` ran directly on EC2
- Consumed EC2 memory (caused OOM on t2.small)
- Competed with API for resources

### New Setup (Fargate):
- `worker_process.py` logic runs in Fargate Spot
- Isolated 3GB RAM (sufficient for BioBERT)
- Cost-optimized (~$7-10/month)
- Auto-scalable (currently fixed at 1 task)

---

## 💡 Future Enhancements

To enable SQS-based auto-scaling (0-3 workers), change in `infra/terraform/main.tf`:
```terraform
worker_mode  = "sqs"         # Instead of "aggregation"
min_capacity = 0             # Scale to 0 when idle
max_capacity = 3             # Scale up to 3 for high load
```

Then run:
```bash
cd infra/terraform
terraform apply
```

---

## 📊 Cost Comparison

| Component | Old (EC2) | New (Fargate) |
|-----------|-----------|---------------|
| Instance | t2.small (2GB) | Fargate Spot (3GB) |
| Monthly Cost | ~$17 | ~$7-10 |
| ML Worker | Included (OOM risk) | Separate (isolated) |
| **Upgrade Path** | t3.medium (~$30/mo) | Current setup OK |

**Savings**: ~$20/month vs upgrading EC2 to t3.medium

---

## ✅ Verification Commands

### Check ML Worker Status:
```bash
export AWS_PROFILE=zivohealth

# Service status
aws ecs describe-services \
  --cluster production-ml-worker-cluster \
  --services production-ml-worker \
  --region us-east-1 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'

# View logs
aws logs tail /ecs/production-ml-worker --region us-east-1 --follow
```

### Check EC2 API Health:
```bash
ssh -i ~/Documents/pem/ec2-dbeaver.pem ubuntu@$(terraform output -raw ec2_public_ip) \
  "docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

---

**Document Created**: 2025-10-21
**Author**: AI Assistant
**Status**: All fixes applied and tested ✅

