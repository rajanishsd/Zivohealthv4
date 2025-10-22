# Fargate ML Worker - Logs Guide 📝

Quick reference for viewing and monitoring Fargate ML worker logs.

---

## Quick Commands

### 1. View Recent Logs (Last 10 minutes)
```bash
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker \
  --since 10m \
  --format short
```

### 2. View Live Logs (Follow mode)
```bash
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker \
  --follow \
  --format short
```

### 3. View Logs by Time Range
```bash
# Last hour
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker \
  --since 1h

# Last 30 minutes
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker \
  --since 30m

# Specific time range (ISO 8601)
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker \
  --start-time 2025-10-21T16:00:00Z \
  --end-time 2025-10-21T17:00:00Z
```

### 4. Search Logs for Specific Patterns
```bash
# Search for errors
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker \
  --since 1h --format short | grep -i error

# Search for a specific user ID
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker \
  --since 1h --format short | grep "user 1"

# Search for successful processing
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker \
  --since 1h --format short | grep "✅"

# Search for message IDs
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker \
  --since 1h --format short | grep "message.*8c1fc1ae"
```

### 5. View Logs from Specific Task
```bash
# Get task ID
TASK_ARN=$(aws --profile zivohealth --region us-east-1 ecs list-tasks \
  --cluster production-ml-worker-cluster \
  --service-name production-ml-worker \
  --output json | jq -r '.taskArns[0]')

TASK_ID=$(echo $TASK_ARN | rev | cut -d'/' -f1 | rev)

echo "Task ID: $TASK_ID"

# View logs for specific task
aws --profile zivohealth --region us-east-1 logs get-log-events \
  --log-group-name "/ecs/production-ml-worker" \
  --log-stream-name "ecs/ml-worker/$TASK_ID" \
  --limit 100
```

---

## Log Formats

### Standard Format
```
2025-10-21T16:36:16 2025-10-21 16:36:16,164 - __main__ - INFO - 🎯 ML Worker started
```

### Short Format (recommended for CLI)
```
2025-10-21T16:36:16 ML Worker started
```

### JSON Format (for parsing)
```bash
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker \
  --since 10m \
  --format json
```

---

## Common Log Patterns

### Startup Logs
```
✅ LOINC mapper imported successfully
ML Worker Service - Lab Categorization, LOINC Mapping & Aggregation
🎯 Mode: SQS
📬 Starting SQS worker mode...
🚀 ML Worker initializing...
✅ AWS SQS client initialized
🎯 ML Worker started, polling for messages...
```

### Message Processing
```
📥 Received 1 message(s) from SQS
🔄 Processing message 8c1fc1ae-9b5b-4776-9a37-f1b26a6c5a49
   Job Type: process_pending_labs
🧪 Processing pending labs for user 1
```

### Successful Completion
```
✅ Message processed successfully
✅ Message deleted from SQS
📊 Processing Stats:
   Duration: 45s
   Records processed: 15
```

### Errors
```
❌ Error processing message: ...
⚠️  Failed to categorize lab report: ...
ERROR - Database connection failed: ...
```

### Shutdown
```
Received signal 15, initiating graceful shutdown...
🛑 ML Worker shutting down...
📊 Worker Stats:
   Uptime: 220s
   Processed: 5
   Errors: 0
✅ ML Worker stopped gracefully
```

---

## Using CloudWatch Console

### Access Logs via Web Console
1. Go to: https://console.aws.amazon.com/cloudwatch/
2. Select region: **us-east-1**
3. Navigate to: **Logs > Log groups**
4. Find: `/ecs/production-ml-worker`
5. Click on log group to see log streams
6. Each stream = one task instance

### Log Stream Naming
```
ecs/ml-worker/<task-id>
```

Example:
```
ecs/ml-worker/6701494645374f40b267d8c41697ffca
```

---

## Monitoring & Debugging

### Check if Task is Running
```bash
aws --profile zivohealth --region us-east-1 ecs describe-services \
  --cluster production-ml-worker-cluster \
  --services production-ml-worker \
  --query 'services[0].{Running:runningCount,Pending:pendingCount,Desired:desiredCount}'
```

### Check Queue Status
```bash
aws --profile zivohealth --region us-east-1 sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/474221740916/production-ml-worker" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
```

### Check Task Details
```bash
# List all tasks
aws --profile zivohealth --region us-east-1 ecs list-tasks \
  --cluster production-ml-worker-cluster \
  --service-name production-ml-worker

# Get task details
TASK_ARN="<task-arn-from-above>"
aws --profile zivohealth --region us-east-1 ecs describe-tasks \
  --cluster production-ml-worker-cluster \
  --tasks "$TASK_ARN" \
  --query 'tasks[0].{Status:lastStatus,Health:healthStatus,Started:startedAt,Container:containers[0].lastStatus}'
```

### Check Service Events
```bash
aws --profile zivohealth --region us-east-1 ecs describe-services \
  --cluster production-ml-worker-cluster \
  --services production-ml-worker \
  --query 'services[0].events[:5]'
```

---

## Manual Service Operations

### Scale Service Up
```bash
aws --profile zivohealth --region us-east-1 ecs update-service \
  --cluster production-ml-worker-cluster \
  --service production-ml-worker \
  --desired-count 1
```

### Scale to Zero (Cost Savings)
```bash
aws --profile zivohealth --region us-east-1 ecs update-service \
  --cluster production-ml-worker-cluster \
  --service production-ml-worker \
  --desired-count 0
```

### Force New Deployment
```bash
aws --profile zivohealth --region us-east-1 ecs update-service \
  --cluster production-ml-worker-cluster \
  --service production-ml-worker \
  --force-new-deployment
```

---

## Troubleshooting

### No Logs Appearing
**Possible causes:**
1. Task hasn't started yet (check `Pending` status)
2. Container crashed immediately (check task events)
3. Log group permissions issue (check IAM role)

**Solutions:**
```bash
# Check task status
aws --profile zivohealth --region us-east-1 ecs describe-services \
  --cluster production-ml-worker-cluster \
  --services production-ml-worker

# Check stopped tasks for errors
aws --profile zivohealth --region us-east-1 ecs list-tasks \
  --cluster production-ml-worker-cluster \
  --desired-status STOPPED | head -1

# Get stopped task details
STOPPED_TASK="<task-arn>"
aws --profile zivohealth --region us-east-1 ecs describe-tasks \
  --cluster production-ml-worker-cluster \
  --tasks "$STOPPED_TASK"
```

### Task Stuck in PENDING
**Possible causes:**
1. Pulling large Docker image (4.6GB ML worker)
2. Network issues (ECR connectivity)
3. Resource constraints (no available capacity)

**Solutions:**
```bash
# Wait 2-3 minutes for image pull
# Check service events for errors
aws --profile zivohealth --region us-east-1 ecs describe-services \
  --cluster production-ml-worker-cluster \
  --services production-ml-worker \
  --query 'services[0].events[:5]'
```

### Container Keeps Restarting
**Check logs for:**
- Import errors: `ModuleNotFoundError`
- Config errors: `ValidationError`
- Database errors: `OperationalError`
- SMTP errors: `Production should not use development SMTP`

**View crash logs:**
```bash
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker \
  --since 10m --format short | grep -E "(Error|Exception|Traceback)"
```

---

## Useful One-Liners

### View last error
```bash
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker --since 1h --format short | grep -i error | tail -5
```

### Count processed messages
```bash
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker --since 1h --format short | grep "Message processed successfully" | wc -l
```

### View processing times
```bash
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker --since 1h --format short | grep "Duration:"
```

### Monitor in real-time
```bash
watch -n 5 'aws --profile zivohealth --region us-east-1 ecs describe-services --cluster production-ml-worker-cluster --services production-ml-worker --query "services[0].{Running:runningCount,Pending:pendingCount}" && aws --profile zivohealth --region us-east-1 sqs get-queue-attributes --queue-url "https://sqs.us-east-1.amazonaws.com/474221740916/production-ml-worker" --attribute-names ApproximateNumberOfMessages --query "Attributes.ApproximateNumberOfMessages"'
```

---

## Log Retention

- **Current Retention**: 7 days (configurable)
- **Log Group**: `/ecs/production-ml-worker`
- **Region**: us-east-1

### Change Retention Period
```bash
# Set to 30 days
aws --profile zivohealth --region us-east-1 logs put-retention-policy \
  --log-group-name /ecs/production-ml-worker \
  --retention-in-days 30

# Options: 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
```

---

## Quick Reference Card

```bash
# Essential commands to keep handy

# View recent logs
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker --since 10m

# Follow live logs
aws --profile zivohealth --region us-east-1 logs tail /ecs/production-ml-worker --follow

# Check service status
aws --profile zivohealth --region us-east-1 ecs describe-services \
  --cluster production-ml-worker-cluster --services production-ml-worker \
  --query 'services[0].{Running:runningCount,Pending:pendingCount}'

# Check queue
aws --profile zivohealth --region us-east-1 sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/474221740916/production-ml-worker" \
  --attribute-names ApproximateNumberOfMessages

# Scale up
aws --profile zivohealth --region us-east-1 ecs update-service \
  --cluster production-ml-worker-cluster --services production-ml-worker --desired-count 1

# Scale down
aws --profile zivohealth --region us-east-1 ecs update-service \
  --cluster production-ml-worker-cluster --service production-ml-worker --desired-count 0
```

---

**Log Group**: `/ecs/production-ml-worker`  
**Region**: `us-east-1`  
**Cluster**: `production-ml-worker-cluster`  
**Service**: `production-ml-worker`

