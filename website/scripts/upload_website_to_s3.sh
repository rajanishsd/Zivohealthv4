#!/bin/bash

# Script to upload ZivoHealth website files to S3 bucket
# Usage: ./upload_website_to_s3.sh

set -e

# Configuration
BUCKET_NAME="zivohealth-website-bucket"
AWS_PROFILE="zivohealth"
WEBSITE_DIR="$(dirname "$0")/../webpages"
AWS_REGION="us-east-1"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ZivoHealth Website Upload to S3${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo "Please install AWS CLI: https://aws.amazon.com/cli/"
    exit 1
fi

# Check if website directory exists
if [ ! -d "$WEBSITE_DIR" ]; then
    echo -e "${RED}Error: Website directory not found at $WEBSITE_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Website directory found: $WEBSITE_DIR${NC}"
echo ""

# List files to be uploaded
echo -e "${BLUE}Files to upload:${NC}"
find "$WEBSITE_DIR" -type f \( -name "*.html" -o -name "*.png" -o -name "*.jpg" \) | while read file; do
    echo "  - $(basename "$file")"
done
echo ""

# Sync files to S3
echo -e "${BLUE}Uploading files to s3://$BUCKET_NAME...${NC}"

# Upload HTML files
aws s3 sync "$WEBSITE_DIR" "s3://$BUCKET_NAME/" \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --delete \
    --exclude "*" \
    --include "*.html" \
    --content-type "text/html" \
    --cache-control "max-age=300"

# Upload images
aws s3 sync "$WEBSITE_DIR/images" "s3://$BUCKET_NAME/images/" \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --content-type "image/png" \
    --cache-control "max-age=86400"

echo ""
echo -e "${GREEN}✓ Upload complete!${NC}"
echo ""

# Set bucket policy to make files publicly readable
echo -e "${BLUE}Setting bucket policy for public access...${NC}"

BUCKET_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
    }
  ]
}
EOF
)

echo "$BUCKET_POLICY" | aws s3api put-bucket-policy \
    --bucket "$BUCKET_NAME" \
    --policy file:///dev/stdin \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION"

echo -e "${GREEN}✓ Bucket policy updated - files are now publicly accessible${NC}"
echo ""

# Display bucket URL
echo -e "${BLUE}Website URLs:${NC}"
echo "  S3 Bucket: http://$BUCKET_NAME.s3-website-$AWS_REGION.amazonaws.com/"
echo "  Index: http://$BUCKET_NAME.s3-website-$AWS_REGION.amazonaws.com/index.html"
echo "  Privacy: http://$BUCKET_NAME.s3-website-$AWS_REGION.amazonaws.com/privacy-policy.html"
echo "  Terms: http://$BUCKET_NAME.s3-website-$AWS_REGION.amazonaws.com/terms-and-conditions.html"
echo ""

# List uploaded files
echo -e "${BLUE}Verifying uploaded files:${NC}"
aws s3 ls "s3://$BUCKET_NAME/" \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --human-readable

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Upload completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"

