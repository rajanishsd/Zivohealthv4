# ML Worker - Fargate Spot Architecture Guide

This guide explains the ML worker architecture for cost-efficient processing of lab categorization and LOINC mapping tasks.

## 📐 Architecture Overview

```
┌──────────────────────────────────────┐
│  FastAPI Backend (t3.small)          │
│  - No ML dependencies loaded         │
│  - Lightweight (~500MB RAM)          │
│  - Pushes jobs to SQS                │
└──────────────────────────────────────┘
                 ↓ (SQS Queue)
┌──────────────────────────────────────┐
│  SQS Queue + DLQ                     │
│  - Reliable message delivery         │
│  - Automatic retries (3x)            │
│  - Dead letter queue for failures    │
└──────────────────────────────────────┘
                 ↓ (Long polling)
┌──────────────────────────────────────┐
│  ML Worker (Fargate Spot)            │
│  - Loads BioBERT (2.5GB)             │
│  - Processes lab categorization      │
│  - Scales 0-3 based on queue depth   │
│  - **70% cost savings with Spot!**   │
└──────────────────────────────────────┘
```

## 💰 Cost Breakdown

### Current (Broken) Architecture:
```
Single t2.small: $17/month
Status: Out of Memory (OOM) crashes
```

### New Architecture:
```
API (t3.small):         $17/month  (1 vCPU, 2GB RAM)
ML Worker (Fargate):     $5/month  (0.5 vCPU, 3GB RAM, Spot pricing)
────────────────────────────────────
Total:                  $22/month  ✅ (+$5 but actually works!)

Cost per lab processing: ~$0.001
Savings vs regular Fargate: 70%
Savings vs Lambda cold starts: 40%
```

## 🚀 Initial Setup

### Step 1: Build Base Image (One-Time)

```bash
# Build base image with ML dependencies (10-15 min)
./scripts/dev/build-ml-base-image.sh
```

This creates the base image with torch, transformers, and sentence-transformers.

### Step 2: Build ML Worker Image

```bash
# Build ML worker image (2-3 min)
./scripts/dev/build-ml-worker.sh
```

### Step 3: Deploy Infrastructure with Terraform

Add the ML worker module to your main Terraform configuration:

```hcl
# In infra/terraform/main.tf

module "ml_worker" {
  source = "./modules/ml_worker"
  
  environment         = "production"
  aws_region          = var.aws_region
  vpc_id              = module.networking.vpc_id
  private_subnet_ids  = module.networking.private_subnet_ids
  ecr_repository_url  = module.ecr.repository_url
  
  # IAM roles (you'll need to create these or use existing)
  execution_role_arn  = module.iam.ecs_execution_role_arn
  task_role_arn       = module.iam.ecs_task_role_arn
  api_role_arn        = module.iam.ec2_instance_role_arn
  
  # Database
  db_host            = module.db.db_endpoint
  db_port            = 5432
  db_name            = var.db_name
  
  # Auto-scaling
  min_capacity       = 0   # Scale to zero when idle
  max_capacity       = 3   # Scale up to 3 workers
  target_queue_depth = 5   # Each worker handles ~5 messages
}

output "ml_worker_queue_url" {
  value = module.ml_worker.sqs_queue_url
}

output "ml_worker_cluster_name" {
  value = module.ml_worker.ecs_cluster_name
}

output "ml_worker_service_name" {
  value = module.ml_worker.ecs_service_name
}
```

Apply the Terraform:

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

### Step 4: Configure API to Use SQS

Update your `.env` or SSM parameters:

```bash
# Enable ML Worker
ML_WORKER_ENABLED=true

# Get queue URL from Terraform output
ML_WORKER_SQS_QUEUE_URL=$(cd infra/terraform && terraform output -raw ml_worker_queue_url)

# Set in SSM (for production)
aws ssm put-parameter \
  --name "/zivohealth/production/ml_worker/enabled" \
  --value "true" \
  --type String \
  --profile zivohealth

aws ssm put-parameter \
  --name "/zivohealth/production/ml_worker/queue_url" \
  --value "$ML_WORKER_SQS_QUEUE_URL" \
  --type String \
  --profile zivohealth
```

### Step 5: Deploy ML Worker

```bash
# Push image and update Fargate service
./scripts/dev/push-ml-worker.sh
```

## 🔄 Daily Workflow

### Build and Deploy Code Changes:

```bash
# 1. Build app images (no ML) - FAST!
./scripts/dev/build-production-images.sh

# 2. Build ML worker (only if worker code changed)
./scripts/dev/build-ml-worker.sh

# 3. Deploy everything
./scripts/dev/push-and-deploy.sh
./scripts/dev/push-ml-worker.sh
```

### Update ML Dependencies:

```bash
# Only when requirements-base.txt changes (rare)
./scripts/dev/build-ml-base-image.sh
./scripts/dev/build-ml-worker.sh
./scripts/dev/push-ml-worker.sh
```

## 📊 Monitoring

### Check Queue Depth:

```bash
aws sqs get-queue-attributes \
  --queue-url $(cd infra/terraform && terraform output -raw ml_worker_queue_url) \
  --attribute-names ApproximateNumberOfMessages \
  --profile zivohealth \
  --region us-east-1
```

### View ML Worker Logs:

```bash
aws logs tail /ecs/production-ml-worker --follow \
  --profile zivohealth \
  --region us-east-1
```

### Check Fargate Service Status:

```bash
aws ecs describe-services \
  --cluster $(cd infra/terraform && terraform output -raw ml_worker_cluster_name) \
  --services $(cd infra/terraform && terraform output -raw ml_worker_service_name) \
  --profile zivohealth \
  --region us-east-1 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

### Monitor Auto-Scaling:

```bash
# Check current task count
aws ecs list-tasks \
  --cluster $(cd infra/terraform && terraform output -raw ml_worker_cluster_name) \
  --service-name $(cd infra/terraform && terraform output -raw ml_worker_service_name) \
  --profile zivohealth \
  --region us-east-1
```

## 🧪 Testing

### Send Test Job to Queue:

```python
from app.utils.sqs_client import get_ml_worker_client

client = get_ml_worker_client()

# Send test job
message_id = client.send_lab_categorization_job(
    user_id=123,
    document_id=456,
    tests=[
        {"test_name": "Hemoglobin", "test_value": "14.5", "test_unit": "g/dL"},
        {"test_name": "WBC Count", "test_value": "7.2", "test_unit": "K/uL"}
    ],
    priority="normal"
)

print(f"Job sent! Message ID: {message_id}")
```

### Monitor Processing:

```bash
# Watch logs for processing
aws logs tail /ecs/production-ml-worker --follow --profile zivohealth --region us-east-1

# Should see:
# ✅ Lab categorization job sent to SQS
# 📥 Received 1 message(s) from SQS
# 🧪 Processing lab categorization for user 123, document 456
# ✅ Lab categorization completed
# 🗑️  Message deleted from queue
```

## 🚨 Troubleshooting

### Issue: ML Worker Not Processing Jobs

**Check:**
1. Is the Fargate service running?
   ```bash
   aws ecs describe-services --cluster production-ml-worker-cluster --services production-ml-worker --profile zivohealth --region us-east-1
   ```

2. Are there messages in the queue?
   ```bash
   aws sqs get-queue-attributes --queue-url <QUEUE_URL> --attribute-names All --profile zivohealth --region us-east-1
   ```

3. Check worker logs for errors:
   ```bash
   aws logs tail /ecs/production-ml-worker --profile zivohealth --region us-east-1
   ```

### Issue: Tasks Failing to Start

**Check:**
1. Is the base image in ECR?
   ```bash
   aws ecr describe-images --repository-name zivohealth-base --profile zivohealth --region us-east-1
   ```

2. Do the IAM roles have correct permissions?
   - Task execution role: ECR pull, SSM read, CloudWatch logs
   - Task role: SQS receive/delete, RDS connect

3. Are the database credentials in SSM?
   ```bash
   aws ssm get-parameter --name "/zivohealth/production/db/username" --profile zivohealth --region us-east-1
   ```

### Issue: High DLQ Message Count

Messages going to DLQ means repeated failures. Check:

```bash
# View DLQ messages
aws sqs receive-message \
  --queue-url $(cd infra/terraform && terraform output -raw ml_worker_dlq_url) \
  --max-number-of-messages 1 \
  --profile zivohealth \
  --region us-east-1
```

Common causes:
- Database connection issues
- Missing LOINC data
- BioBERT model loading failures
- Invalid message format

## 📈 Scaling Configuration

The ML worker auto-scales based on SQS queue depth:

```
Queue Messages  |  Workers  |  Processing Capacity
─────────────────────────────────────────────────
0               |  0        |  0 jobs/min (costs $0)
1-5             |  1        |  ~12 jobs/min
6-10            |  2        |  ~24 jobs/min
11-15           |  3        |  ~36 jobs/min
```

**Tune auto-scaling:**

In `infra/terraform/main.tf`:

```hcl
module "ml_worker" {
  # ...
  min_capacity       = 0    # Scale to zero when idle
  max_capacity       = 5    # Allow up to 5 workers for high load
  target_queue_depth = 3    # More aggressive scaling (1 worker per 3 messages)
}
```

## 🔐 Security Notes

1. **No Public IP**: ML workers run in private subnets
2. **IAM Roles**: Least-privilege access to SQS, RDS, SSM
3. **VPC Security Groups**: Only allow outbound connections
4. **Secrets**: Database credentials stored in SSM Parameter Store
5. **Fargate Spot**: Can be interrupted (SQS handles retries automatically)

## 💡 Pro Tips

1. **Monitor costs**: Check AWS Cost Explorer for Fargate Spot usage
2. **Set up alarms**: Get notified when DLQ has messages
3. **Use priority queues**: Add separate queues for urgent jobs
4. **Batch processing**: Update worker to process multiple tests per message
5. **Optimize model loading**: Cache BioBERT model in EFS for faster cold starts (advanced)

## 📚 Related Documentation

- [Two-Tier Docker Build Strategy](TWO_TIER_DOCKER_BUILD.md)
- [Quick Build Guide](../QUICK_BUILD_GUIDE.md)
- [Production Deployment](../scripts/dev/README.md)

## ✅ Success Checklist

- [ ] Base image built and pushed to ECR
- [ ] ML worker image built and pushed to ECR
- [ ] Terraform infrastructure deployed
- [ ] SQS queue URL configured in API
- [ ] Fargate service running and healthy
- [ ] Test job processed successfully
- [ ] CloudWatch logs visible
- [ ] Auto-scaling working
- [ ] Costs monitored

**Questions?** Check the logs or open an issue!

