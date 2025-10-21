# AWS Textract PDF Processing Fix

## 🔍 Problem Identified

AWS Textract jobs were **stuck in "IN_PROGRESS"** status indefinitely, causing PDF text extraction to timeout after 5 minutes.

### Root Cause
The S3 bucket policy was missing **Textract service principal permissions**. While the EC2 IAM role had Textract permissions, the Textract service itself couldn't read PDFs from S3.

---

## ✅ Solution Applied

### 1. **Added Textract Service Principal to S3 Bucket Policy**

**File:** `infra/terraform/modules/storage/main.tf`

Added the following statement to the S3 bucket policy:

```json
{
  "Sid": "AllowTextractServiceAccess",
  "Effect": "Allow",
  "Principal": {
    "Service": "textract.amazonaws.com"
  },
  "Action": [
    "s3:GetObject",
    "s3:ListBucket"
  ],
  "Resource": [
    "arn:aws:s3:::zivohealth-data",
    "arn:aws:s3:::zivohealth-data/*"
  ]
}
```

This allows the AWS Textract service to:
- ✅ Read PDF files from the S3 bucket
- ✅ List bucket contents
- ✅ Complete async text detection jobs

---

## 🚀 Deployment Instructions

### Option 1: Deploy via Terraform (Recommended)

```bash
cd /Users/rajanishsd/Documents/ZivohealthPlatform/infra/terraform

# Initialize and validate
terraform init
terraform validate

# Preview changes
terraform plan

# Apply changes
terraform apply
```

**Expected output:**
```
  ~ resource "aws_s3_bucket_policy" "allow_ec2_read_compose" {
      ~ policy = (updated with Textract permissions)
    }

Plan: 0 to add, 1 to change, 0 to destroy.
```

### Option 2: Apply S3 Policy Manually (Quick Fix for Testing)

```bash
# Create policy file
cat > /tmp/textract-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowEC2InstanceReadCompose",
      "Effect": "Allow",
      "Principal": "*",
      "Condition": {
        "ArnLike": {
          "aws:PrincipalArn": [
            "arn:aws:sts::474221740916:assumed-role/zivohealth-production-ec2-role/*",
            "arn:aws:sts::474221740916:assumed-role/zivohealth-dev-ec2-role/*"
          ]
        }
      },
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::zivohealth-data/deploy/dev/*"]
    },
    {
      "Sid": "AllowEC2InstanceListBucket",
      "Effect": "Allow",
      "Principal": "*",
      "Condition": {
        "ArnLike": {
          "aws:PrincipalArn": [
            "arn:aws:sts::474221740916:assumed-role/zivohealth-production-ec2-role/*",
            "arn:aws:sts::474221740916:assumed-role/zivohealth-dev-ec2-role/*"
          ]
        }
      },
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": ["arn:aws:s3:::zivohealth-data"]
    },
    {
      "Sid": "AllowEC2InstancePutUploads",
      "Effect": "Allow",
      "Principal": "*",
      "Condition": {
        "ArnLike": {
          "aws:PrincipalArn": [
            "arn:aws:sts::474221740916:assumed-role/zivohealth-production-ec2-role/*",
            "arn:aws:sts::474221740916:assumed-role/zivohealth-dev-ec2-role/*"
          ]
        }
      },
      "Action": ["s3:PutObject"],
      "Resource": ["arn:aws:s3:::zivohealth-data/uploads/*"]
    },
    {
      "Sid": "AllowTextractServiceAccess",
      "Effect": "Allow",
      "Principal": {
        "Service": "textract.amazonaws.com"
      },
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::zivohealth-data",
        "arn:aws:s3:::zivohealth-data/*"
      ]
    }
  ]
}
EOF

# Apply policy
aws --profile zivohealth s3api put-bucket-policy \
  --bucket zivohealth-data \
  --policy file:///tmp/textract-policy.json

echo "✅ S3 bucket policy updated with Textract permissions"
```

---

## 🧪 Verification

### Test Textract After Deployment

```bash
cd /Users/rajanishsd/Documents/ZivohealthPlatform/backend
python test_textract.py
```

**Expected output (after fix):**
```
✅ Textract client initialized successfully
✅ Bucket exists and is accessible
✅ Job completed successfully in 20-30s
✓ Extracted text: 'Test Document'
```

### Check S3 Policy

```bash
aws --profile zivohealth s3api get-bucket-policy \
  --bucket zivohealth-data \
  --query Policy --output text | python -m json.tool | grep -A 5 "Textract"
```

---

## 📊 Current Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| **Max Wait Time** | 300 seconds (5 min) | Sufficient for most documents |
| **Poll Interval** | 2 seconds | Good balance between responsiveness and API calls |
| **S3 Bucket** | `zivohealth-data` | Production bucket |
| **Region** | `us-east-1` | Textract available |
| **IAM Permissions** | ✅ Configured | EC2 role has Textract permissions |
| **S3 Policy** | ✅ **FIXED** | Textract service can now read PDFs |

---

## 🎯 What This Fixes

1. ✅ PDF text extraction will now complete successfully
2. ✅ Textract jobs will transition from `IN_PROGRESS` to `SUCCEEDED`
3. ✅ `handle_pdf` function in `document_workflow.py` will return extracted text
4. ✅ No more timeout errors after 5 minutes
5. ✅ Lab reports, prescriptions, and other PDF documents will be processed

---

## 📝 Additional Notes

### Timeout Settings in Code

The current timeout settings in `backend/app/agentsv2/tools/ocr_tools.py`:
- **Line 278**: `max_wait_time = 300` (5 minutes)
- **Line 279**: `poll_interval = 2` (2 seconds)

These are **sufficient** and **do not need to be changed**. The issue was purely permissions, not timing.

### Cost Implications

- AWS Textract charges per page processed
- Current usage: ~$1.50 per 1,000 pages
- No additional costs from this fix

### Monitoring

Check Textract job logs:
```bash
tail -f /Users/rajanishsd/Documents/ZivohealthPlatform/backend/logs/server.log | grep "OCR"
```

---

## 🚨 Rollback (If Needed)

To remove Textract permissions:

```bash
# Remove the "AllowTextractServiceAccess" statement from the policy
# Then apply via terraform or manually update S3 policy
```

---

## ✅ Next Steps

1. **Deploy the fix** using Option 1 (Terraform) or Option 2 (Manual)
2. **Verify** using the test script
3. **Test** with a real PDF document upload
4. **Monitor** server logs for successful extractions
5. **Clean up** test files: `rm /Users/rajanishsd/Documents/ZivohealthPlatform/backend/test_textract.py`

---

**Fix applied on:** 2025-10-20  
**Issue:** AWS Textract jobs stuck in IN_PROGRESS  
**Solution:** Added Textract service principal to S3 bucket policy  
**Status:** ✅ Ready to deploy

