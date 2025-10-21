#!/usr/bin/env python3
"""
Test script to diagnose AWS Textract connectivity and timeout issues
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project paths
project_root = Path(__file__).parent.parent
backend_path = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from app.core.config import settings
import time

def test_aws_connection():
    """Test basic AWS connectivity"""
    print("\n" + "="*70)
    print("🔍 Testing AWS Connectivity")
    print("="*70)
    
    # Check environment variables
    print(f"✓ AWS_ACCESS_KEY_ID: {'Set' if settings.AWS_ACCESS_KEY_ID else 'Not set'}")
    print(f"✓ AWS_SECRET_ACCESS_KEY: {'Set' if settings.AWS_SECRET_ACCESS_KEY else 'Not set'}")
    print(f"✓ AWS_REGION: {settings.AWS_REGION}")
    print(f"✓ AWS_S3_BUCKET: {settings.AWS_S3_BUCKET}")
    
    return True

def test_textract_service():
    """Test AWS Textract service availability"""
    print("\n" + "="*70)
    print("🔍 Testing AWS Textract Service")
    print("="*70)
    
    try:
        # Initialize Textract client
        aws_config = {
            'region_name': settings.AWS_REGION or settings.AWS_DEFAULT_REGION or 'us-east-1'
        }
        
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            aws_config['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
            aws_config['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
        
        textract_client = boto3.client('textract', **aws_config)
        
        # Test with a simple text detection (will fail gracefully)
        # This just validates the client is properly initialized
        print("✅ Textract client initialized successfully")
        print(f"✓ Region: {aws_config['region_name']}")
        
        # Check if we can access service operations
        operations = textract_client._service_model.operation_names
        print(f"✓ Available operations: {len(operations)}")
        print(f"  - start_document_text_detection: {'✅' if 'StartDocumentTextDetection' in operations else '❌'}")
        print(f"  - get_document_text_detection: {'✅' if 'GetDocumentTextDetection' in operations else '❌'}")
        
        return True, textract_client
        
    except NoCredentialsError:
        print("❌ AWS credentials not found")
        return False, None
    except Exception as e:
        print(f"❌ Error initializing Textract: {e}")
        print(f"   Type: {type(e).__name__}")
        return False, None

def test_s3_bucket():
    """Test S3 bucket access"""
    print("\n" + "="*70)
    print("🔍 Testing S3 Bucket Access")
    print("="*70)
    
    try:
        aws_config = {
            'region_name': settings.AWS_REGION or settings.AWS_DEFAULT_REGION or 'us-east-1'
        }
        
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            aws_config['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
            aws_config['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
        
        s3_client = boto3.client('s3', **aws_config)
        
        # Try to list objects (just check if we have access)
        bucket = settings.AWS_S3_BUCKET
        print(f"✓ Testing bucket: {bucket}")
        
        try:
            response = s3_client.head_bucket(Bucket=bucket)
            print(f"✅ Bucket exists and is accessible")
            return True, s3_client
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"❌ Bucket does not exist: {bucket}")
            elif error_code == '403':
                print(f"❌ Access denied to bucket: {bucket}")
            else:
                print(f"❌ Error accessing bucket: {error_code}")
            return False, None
            
    except Exception as e:
        print(f"❌ Error testing S3: {e}")
        return False, None

def test_textract_timeout_settings():
    """Check Textract timeout configuration"""
    print("\n" + "="*70)
    print("🔍 Checking Textract Timeout Settings")
    print("="*70)
    
    from app.agentsv2.tools.ocr_tools import OCRToolkit
    
    ocr = OCRToolkit()
    print(f"✓ OCR Toolkit initialized")
    print(f"✓ Textract ready: {ocr.is_textract_ready}")
    print(f"✓ S3 Bucket: {ocr.s3_bucket}")
    
    # Check timeout settings in the code
    print("\n📊 Current Timeout Configuration:")
    print(f"  - Max wait time: 300 seconds (5 minutes)")
    print(f"  - Poll interval: 2 seconds")
    print(f"  - Max polls: ~150 attempts")
    
    return True

def test_sample_textract_job(textract_client, s3_client):
    """Test a sample Textract job to check actual processing"""
    print("\n" + "="*70)
    print("🔍 Testing Sample Textract Job")
    print("="*70)
    
    try:
        # Create a small test PDF content
        test_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj 4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 100 700 Td (Test Document) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000115 00000 n\n0000000291 00000 n\ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n381\n%%EOF"
        
        # Upload to S3
        bucket = settings.AWS_S3_BUCKET
        key = f"textract-test/test-{int(time.time())}.pdf"
        
        print(f"📤 Uploading test PDF to s3://{bucket}/{key}")
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=test_content,
            ContentType='application/pdf'
        )
        print("✅ Test PDF uploaded")
        
        # Start Textract job
        print("🚀 Starting Textract job...")
        response = textract_client.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            }
        )
        
        job_id = response['JobId']
        print(f"✓ Job ID: {job_id}")
        
        # Poll for completion
        max_wait = 60  # 1 minute should be enough for a test document
        poll_interval = 2
        total_wait = 0
        
        print("⏳ Waiting for job completion...")
        while total_wait < max_wait:
            time.sleep(poll_interval)
            total_wait += poll_interval
            
            response = textract_client.get_document_text_detection(JobId=job_id)
            status = response['JobStatus']
            
            print(f"  [{total_wait}s] Status: {status}")
            
            if status == 'SUCCEEDED':
                print(f"✅ Job completed successfully in {total_wait}s")
                
                # Get results
                text_blocks = []
                for block in response.get('Blocks', []):
                    if block['BlockType'] == 'LINE':
                        text_blocks.append(block['Text'])
                
                extracted_text = '\n'.join(text_blocks)
                print(f"✓ Extracted text: '{extracted_text}'")
                
                # Cleanup
                print("🗑️  Cleaning up test file...")
                s3_client.delete_object(Bucket=bucket, Key=key)
                
                return True
                
            elif status == 'FAILED':
                error_msg = response.get('StatusMessage', 'Unknown error')
                print(f"❌ Job failed: {error_msg}")
                s3_client.delete_object(Bucket=bucket, Key=key)
                return False
        
        print(f"❌ Job timed out after {max_wait}s")
        s3_client.delete_object(Bucket=bucket, Key=key)
        return False
        
    except Exception as e:
        print(f"❌ Error testing Textract job: {e}")
        print(f"   Type: {type(e).__name__}")
        return False

def main():
    print("\n" + "="*70)
    print("AWS TEXTRACT DIAGNOSTIC TEST")
    print("="*70)
    
    # Test 1: AWS Connection
    if not test_aws_connection():
        print("\n❌ AWS connection test failed")
        return
    
    # Test 2: Textract Service
    textract_ok, textract_client = test_textract_service()
    if not textract_ok:
        print("\n❌ Textract service test failed")
        return
    
    # Test 3: S3 Bucket
    s3_ok, s3_client = test_s3_bucket()
    if not s3_ok:
        print("\n❌ S3 bucket test failed")
        return
    
    # Test 4: Timeout Settings
    test_textract_timeout_settings()
    
    # Test 5: Sample Textract Job
    print("\n⚠️  This will create and process a test PDF...")
    test_sample_textract_job(textract_client, s3_client)
    
    print("\n" + "="*70)
    print("✅ DIAGNOSTIC TEST COMPLETE")
    print("="*70)

if __name__ == "__main__":
    main()

