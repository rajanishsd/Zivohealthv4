# ML Worker Modes Explained

## 🎯 Overview

The ML Worker supports **THREE modes** to handle different processing scenarios:

```
┌─────────────────────────────────────────────────────────┐
│  ML Worker (Fargate - 0.5 vCPU, 3GB RAM)              │
│  Loads BioBERT (2.5GB) + processes lab categorization  │
└─────────────────────────────────────────────────────────┘
                         ↓
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼─────┐  ┌──────▼──────┐  ┌───▼───────────┐
│ SQS Mode    │  │ Aggregation │  │  BOTH Mode    │
│             │  │    Mode      │  │               │
│ Processes   │  │ Continuously │  │ Runs SQS +    │
│ jobs from   │  │ processes    │  │ Aggregation   │
│ SQS queue   │  │ pending data │  │ concurrently  │
└─────────────┘  └──────────────┘  └───────────────┘
```

## Mode 1: SQS Mode 📬

**Purpose**: Process specific lab categorization jobs sent via SQS queue

### When to Use:
- API-driven lab report uploads
- On-demand processing
- Event-driven architecture
- Need guaranteed delivery and retries

### How It Works:
```
User uploads lab → API validates → Pushes to SQS → ML Worker pulls → Process → DB update
```

### Configuration:
```bash
ML_WORKER_MODE=sqs
ML_WORKER_SQS_QUEUE_URL=<queue-url>
```

### Use Cases:
- User uploads a lab report via mobile app
- Doctor requests analysis of specific tests
- Batch processing of uploaded documents

### Cost:
- **Scales to 0** when no jobs
- Pay only when processing
- ~$0.001 per job

---

## Mode 2: Aggregation Mode 🔄

**Purpose**: Continuously processes pending lab/vitals/nutrition data for aggregation

### When to Use:
- Background data processing
- Scheduled aggregation tasks
- Catch-up processing for pending entries
- **Replaces `worker_process.py` running on EC2**

### How It Works:
```
Continuous loop:
  1. Query database for pending entries
  2. Process vitals aggregation
  3. Process nutrition aggregation
  4. Process lab categorization (uses BioBERT)
  5. Sleep 30 seconds
  6. Repeat
```

### Configuration:
```bash
ML_WORKER_MODE=aggregation
```

### Use Cases:
- Daily aggregation of vitals data
- Nutrition summary calculations
- Lab report categorization backlog
- **Default mode for production**

### Cost:
- Runs continuously (1 task always on)
- **$5-8/month** with Fargate Spot
- Processes all pending data automatically

---

## Mode 3: Both Mode 🚀

**Purpose**: Run both SQS and aggregation workers simultaneously

### When to Use:
- Need real-time processing (SQS) + background tasks (aggregation)
- High-volume production environments
- Want all-in-one worker

### How It Works:
```
Worker starts → Spawns 2 async tasks:
  Task 1: SQS worker (polls queue)
  Task 2: Aggregation worker (continuous processing)
  Both run concurrently in same container
```

### Configuration:
```bash
ML_WORKER_MODE=both
ML_WORKER_SQS_QUEUE_URL=<queue-url>
```

### Use Cases:
- Production environment with both API uploads and background processing
- Consolidate workers into one Fargate task
- Maximize resource utilization

### Cost:
- Same as aggregation ($5-8/month)
- No additional cost for SQS processing
- More efficient than running 2 separate workers

---

## 📊 Comparison

| Feature | SQS Mode | Aggregation Mode | Both Mode |
|---------|----------|------------------|-----------|
| **Scales to 0** | ✅ Yes | ❌ No (always 1) | ❌ No |
| **API-driven** | ✅ Yes | ❌ No | ✅ Yes |
| **Background processing** | ❌ No | ✅ Yes | ✅ Yes |
| **Cost (idle)** | $0 | $5-8/mo | $5-8/mo |
| **Cost (active)** | Per job | $5-8/mo | $5-8/mo |
| **Best for** | Low volume | Production | High volume |
| **Startup mode** | SQS only | Aggregation only | Both |

---

## 🎯 Recommended Setup

### For Most Users (Recommended):

```hcl
# terraform/main.tf
module "ml_worker" {
  # ...
  worker_mode = "aggregation"  # Default mode
  min_capacity = 1             # Always run 1 worker
  max_capacity = 1             # Don't scale up (not needed for aggregation)
}
```

**Why?**
- ✅ Replaces `worker_process.py` on EC2
- ✅ Processes all pending data automatically
- ✅ Cheapest option ($5-8/month vs $17+ for EC2)
- ✅ No need to configure SQS if you don't use API uploads

### For API-Heavy Workloads:

```hcl
# terraform/main.tf
module "ml_worker" {
  # ...
  worker_mode = "both"         # Handle both SQS and aggregation
  min_capacity = 1             # Start with 1
  max_capacity = 3             # Scale up for SQS backlog
}
```

**Why?**
- ✅ Handles both API uploads and background processing
- ✅ Auto-scales for SQS queue depth
- ✅ Most flexible for production

### For Event-Driven Only:

```hcl
# terraform/main.tf
module "ml_worker" {
  # ...
  worker_mode = "sqs"          # Only process SQS jobs
  min_capacity = 0             # Scale to 0 when no jobs
  max_capacity = 5             # Scale up for bursts
}
```

**Why?**
- ✅ Pay only when processing
- ✅ Best for infrequent uploads
- ⚠️ **Note**: You'll still need `worker_process.py` on EC2 for aggregation

---

## 🔧 Configuration Examples

### Production Setup (Aggregation Mode):

```hcl
# infra/terraform/main.tf
module "ml_worker" {
  source = "./modules/ml_worker"
  
  environment        = "production"
  worker_mode        = "aggregation"  # ← Default mode
  
  # Scaling (aggregation doesn't need auto-scaling)
  min_capacity       = 1
  max_capacity       = 1
  
  # Other configs...
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  # ...
}
```

### High-Volume Setup (Both Mode):

```hcl
module "ml_worker" {
  source = "./modules/ml_worker"
  
  environment        = "production"
  worker_mode        = "both"  # ← Run both workers
  
  # Scaling (for SQS queue depth)
  min_capacity       = 1       # Always 1 for aggregation
  max_capacity       = 5       # Scale up to 5 for SQS bursts
  target_queue_depth = 10      # Scale when >10 SQS messages
  
  # ...
}
```

---

## 🚀 Migration Path

### Current: EC2 with `worker_process.py`

```
t2.small EC2 ($17/month) → Running worker_process.py
Problem: Out of Memory (OOM) crashes
```

### Step 1: Deploy ML Worker (Aggregation Mode)

```bash
# Build and deploy ML worker
./scripts/dev/build-ml-worker.sh
./scripts/dev/push-ml-worker.sh

# Configure Terraform
# Set: worker_mode = "aggregation"
terraform apply
```

**Result**: ML worker processes all aggregation tasks on Fargate

### Step 2: Stop `worker_process.py` on EC2

```bash
# SSH to EC2 or use SSM
aws ssm send-command --instance-ids <id> \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["pkill -f worker_process.py"]'
```

**Result**: No more OOM crashes!

### Step 3: (Optional) Add SQS Mode

```bash
# Update Terraform to "both" mode
# Set: worker_mode = "both"
terraform apply
```

**Result**: Now handles both API uploads and background processing

---

## 📝 Environment Variables

### SQS Mode:
```bash
ML_WORKER_MODE=sqs
ML_WORKER_SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/.../ml-worker
ML_WORKER_BATCH_SIZE=1
ML_WORKER_WAIT_TIME=20
```

### Aggregation Mode:
```bash
ML_WORKER_MODE=aggregation
# No SQS variables needed
```

### Both Mode:
```bash
ML_WORKER_MODE=both
ML_WORKER_SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/.../ml-worker
# Combines both configs
```

---

## 🧪 Testing

### Test Aggregation Mode:

```bash
# Check logs
aws logs tail /ecs/production-ml-worker --follow --profile zivohealth

# Should see:
# 🔄 Starting background aggregation mode...
# 📊 Processing batch: X vitals + Y nutrition + Z lab reports
# ✅ Lab categorization completed
```

### Test SQS Mode:

```python
from app.utils.sqs_client import get_ml_worker_client

client = get_ml_worker_client()
message_id = client.send_lab_categorization_job(
    user_id=123,
    document_id=456,
    tests=[{"test_name": "Hemoglobin", "test_value": "14.5"}]
)
```

### Test Both Mode:

Both of the above should work simultaneously!

---

## ✅ Recommendations

| Scenario | Recommended Mode | Why |
|----------|-----------------|-----|
| **Starting out** | `aggregation` | Simplest, handles background tasks |
| **Production (low API)** | `aggregation` | Cheapest, no SQS needed |
| **Production (high API)** | `both` | Handles everything, auto-scales |
| **Event-driven only** | `sqs` | Pay per use, scales to 0 |
| **Development** | `aggregation` | Match production setup |

**Default recommendation**: Start with `aggregation` mode. Add SQS later if needed!

---

## 🔍 Troubleshooting

**Q: Which mode should I use?**
A: Start with `aggregation` - it's the simplest and handles all background processing.

**Q: Can I switch modes?**
A: Yes! Just update `worker_mode` in Terraform and redeploy.

**Q: How much does each mode cost?**
A: 
- SQS mode (idle): $0
- Aggregation mode: $5-8/month
- Both mode: $5-8/month (same as aggregation)

**Q: Do I still need `worker_process.py` on EC2?**
A: No! Aggregation mode replaces it completely.

---

## 📚 Related Docs

- [ML Worker Guide](docs/ML_WORKER_GUIDE.md)
- [Two-Tier Docker Build](docs/TWO_TIER_DOCKER_BUILD.md)
- [Quick Build Guide](QUICK_BUILD_GUIDE.md)

