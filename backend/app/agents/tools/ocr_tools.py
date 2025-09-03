"""
OCR (Optical Character Recognition) Tools using AWS Textract

Provides tools for extracting text from images and PDFs using AWS Textract.
More reliable and doesn't require local OCR dependencies.
"""

import os
import logging
import base64
import io
from typing import List, Dict, Any, Union, Optional
from PIL import Image
from langchain.tools import Tool
from pathlib import Path
import tempfile
from app.utils.timezone import now_local, isoformat_now
# Import configuration
from app.core.config import settings

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    TEXTRACT_AVAILABLE = True
except ImportError:
    TEXTRACT_AVAILABLE = False
    logging.warning("AWS boto3 not available. Install boto3 for Textract OCR")


class OCRToolkit:
    """Toolkit for extracting text from images and PDFs using AWS Textract"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.pdf']
        
        # S3 configuration for async processing
        self.s3_bucket = getattr(settings, 'AWS_S3_BUCKET', 'zivohealth-textract-temp')
        
        if TEXTRACT_AVAILABLE:
            try:
                # Use configuration settings for AWS client initialization
                aws_config = {}
                
                if settings.AWS_REGION:
                    aws_config['region_name'] = settings.AWS_REGION
                elif settings.AWS_DEFAULT_REGION:
                    aws_config['region_name'] = settings.AWS_DEFAULT_REGION
                else:
                    # Default to us-east-1 if no region is configured
                    aws_config['region_name'] = 'us-east-1'
                
                # Add credentials if provided in environment
                if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                    aws_config['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
                    aws_config['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
                
                self.textract_client = boto3.client('textract', **aws_config)
                self.s3_client = boto3.client('s3', **aws_config)
                    
                # Test credentials by checking if we can access the service
                # This doesn't make an actual API call but validates the client setup
                self.textract_client._service_model.operation_names
                self.logger.info(f"AWS Textract client initialized successfully with region: {aws_config.get('region_name')}")
                self.logger.info(f"S3 bucket configured: {self.s3_bucket}")
                self.is_textract_ready = True
            except Exception as e:
                self.logger.warning(f"AWS Textract not properly configured: {e}")
                self.is_textract_ready = False
                self.textract_client = None
                self.s3_client = None
        else:
            self.textract_client = None
            self.s3_client = None
            self.is_textract_ready = False
            self.logger.warning("AWS Textract tools are not available due to missing boto3 dependency")
    
    def get_tools(self) -> List[Tool]:
        """Get all OCR tools"""
        return [self.get_text_extraction_tool()]
    
    def get_text_extraction_tool(self) -> Tool:
        """Get the text extraction tool using AWS Textract"""
        
        def extract_text_from_file(file_path: str) -> str:
            """Extract text from image or PDF file using AWS Textract"""
            
            if not self.is_textract_ready:
                return "AWS Textract not available - install boto3 and configure AWS credentials"
            
            try:
                file_path = Path(file_path)
                
                if not file_path.exists():
                    return f"File not found: {file_path}"
                
                file_extension = file_path.suffix.lower()
                
                if file_extension not in self.supported_formats:
                    return f"Unsupported file type: {file_extension}. Supported formats: {self.supported_formats}"
                
                # Read file content
                with open(file_path, 'rb') as file:
                    file_content = file.read()
                
                if file_extension == '.pdf':
                    return self._extract_text_from_pdf(file_path)
                else:
                    return self._extract_text_from_image(file_path)
                
            except Exception as e:
                self.logger.error(f"Error extracting text from {file_path}: {e}")
                return f"Error extracting text: {str(e)}"
        
        return Tool(
            name="extract_text_from_file",
            description="Extract text from image files (JPG, PNG) or PDF files using AWS Textract",
            func=extract_text_from_file
        )
    
    def _extract_text_from_image_bytes(self, image_bytes: bytes) -> str:
        """Extract text from image bytes using AWS Textract"""
        
        try:
            if not self.is_textract_ready or not self.textract_client:
                self.logger.error("❌ [OCR] AWS Textract not available for image processing")
                return "AWS Textract not available"
            
            self.logger.debug(f"🔧 [OCR] Calling AWS Textract detect_document_text for image ({len(image_bytes)} bytes)")
            
            # Use detect_document_text for simple text extraction
            response = self.textract_client.detect_document_text(
                Document={'Bytes': image_bytes}
            )
            
            self.logger.debug(f"📋 [OCR] AWS Textract response received with {len(response.get('Blocks', []))} blocks")
            
            # Extract text from response
            text_blocks = []
            for block in response.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    text_blocks.append(block['Text'])
            
            extracted_text = '\n'.join(text_blocks)
            result = extracted_text.strip() if extracted_text else "No text found in image"
            self.logger.info(f"✅ [OCR] AWS Textract extracted {len(result)} characters from image")
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            self.logger.error(f"❌ [OCR] AWS Textract ClientError: {error_code} - {e.response['Error']['Message']}")
            if error_code == 'InvalidImageException':
                return "Invalid image format or corrupted image"
            elif error_code == 'UnsupportedDocumentException':
                return "Unsupported document format"
            else:
                self.logger.error(f"❌ [OCR] AWS Textract error: {e}")
                return f"AWS Textract error: {error_code}"
        except NoCredentialsError as e:
            self.logger.error(f"❌ [OCR] AWS credentials not found: {e}")
            return "AWS credentials not configured"
        except Exception as e:
            self.logger.error(f"❌ [OCR] Error processing image with Textract: {e}")
            self.logger.error(f"❌ [OCR] Exception type: {type(e).__name__}")
            return f"Error processing image: {str(e)}"
    
    def _extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes using AWS Textract async API with S3 upload"""
        import time
        import uuid
        
        s3_key = None
        try:
            if not self.is_textract_ready or not self.textract_client or not self.s3_client:
                self.logger.error("❌ [OCR] AWS Textract or S3 not available for PDF processing")
                return "AWS Textract or S3 not available"
            
            self.logger.debug(f"🔧 [OCR] Starting async text detection for PDF ({len(pdf_bytes)} bytes)")
            
            # Upload PDF to S3 first
            s3_key = f"textract-temp/{uuid.uuid4()}.pdf"
            self.logger.debug(f"📤 [OCR] Uploading PDF to S3: s3://{self.s3_bucket}/{s3_key}")
            
            try:
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=pdf_bytes,
                    ContentType='application/pdf'
                )
                self.logger.info(f"✅ [OCR] PDF uploaded to S3 successfully")
            except ClientError as s3_error:
                self.logger.error(f"❌ [OCR] Failed to upload PDF to S3: {s3_error}")
                return f"Failed to upload PDF to S3: {s3_error}"
            
            # Start async text detection using S3 location
            response = self.textract_client.start_document_text_detection(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': self.s3_bucket,
                        'Name': s3_key
                    }
                }
            )
            
            job_id = response['JobId']
            self.logger.debug(f"📋 [OCR] Started async job with ID: {job_id}")
            
            # Poll for completion
            max_wait_time = 300  # Maximum 5 minutes for larger documents
            poll_interval = 2    # Poll every 2 seconds
            total_wait = 0
            
            while total_wait < max_wait_time:
                self.logger.debug(f"⏳ [OCR] Polling job status (waited {total_wait}s)")
                
                response = self.textract_client.get_document_text_detection(JobId=job_id)
                status = response['JobStatus']
                
                if status == 'SUCCEEDED':
                    self.logger.info(f"✅ [OCR] Async job completed successfully after {total_wait}s")
                    break
                elif status == 'FAILED':
                    error_msg = response.get('StatusMessage', 'Unknown error')
                    self.logger.error(f"❌ [OCR] Async job failed: {error_msg}")
                    return f"PDF processing failed: {error_msg}"
                elif status in ['IN_PROGRESS']:
                    time.sleep(poll_interval)
                    total_wait += poll_interval
                else:
                    self.logger.warning(f"⚠️ [OCR] Unexpected job status: {status}")
                    time.sleep(poll_interval)
                    total_wait += poll_interval
            
            if total_wait >= max_wait_time:
                self.logger.error(f"❌ [OCR] Async job timed out after {max_wait_time}s")
                return "PDF processing timed out. Please try with a smaller document."
            
            # Extract text from all pages and store AWS response
            text_blocks = []
            next_token = None
            page_count = 0
            all_responses = []  # Store all response data
            
            while True:
                if next_token:
                    response = self.textract_client.get_document_text_detection(
                        JobId=job_id, NextToken=next_token
                    )
                else:
                    response = self.textract_client.get_document_text_detection(JobId=job_id)
                
                # Store this response batch
                all_responses.append(response)
                
                # Process blocks from this batch
                for block in response.get('Blocks', []):
                    if block['BlockType'] == 'LINE':
                        text_blocks.append(block['Text'])
                    elif block['BlockType'] == 'PAGE':
                        page_count += 1
                
                next_token = response.get('NextToken')
                if not next_token:
                    break
            
            # Store the complete AWS response to file
            self._store_aws_response(job_id, all_responses, page_count)
            
            extracted_text = '\n'.join(text_blocks)
            result = extracted_text.strip() if extracted_text else "No text found in PDF"
            
            page_text = "page" if page_count == 1 else "pages"
            self.logger.info(f"✅ [OCR] Successfully extracted {len(result)} characters from {page_count} {page_text}")
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            self.logger.error(f"❌ [OCR] AWS Textract async error: {error_code} - {e.response['Error']['Message']}")
            if error_code == 'InvalidDocumentException':
                return "Invalid PDF format or corrupted PDF"
            elif error_code == 'UnsupportedDocumentException':
                return "PDF format not supported or too large"
            else:
                return f"AWS Textract error: {error_code}"
        except NoCredentialsError as e:
            self.logger.error(f"❌ [OCR] AWS credentials not found for PDF: {e}")
            return "AWS credentials not configured"
        except Exception as e:
            self.logger.error(f"❌ [OCR] Error processing PDF with Textract: {e}")
            self.logger.error(f"❌ [OCR] Exception type: {type(e).__name__}")
            return f"Error processing PDF: {str(e)}"
        finally:
            # Clean up S3 object
            if s3_key and self.s3_client:
                try:
                    self.s3_client.delete_object(Bucket=self.s3_bucket, Key=s3_key)
                    self.logger.debug(f"🗑️ [OCR] Cleaned up S3 object: s3://{self.s3_bucket}/{s3_key}")
                except Exception as cleanup_error:
                    self.logger.warning(f"⚠️ [OCR] Failed to cleanup S3 object: {cleanup_error}")
    
    def get_document_analysis_tool(self) -> Tool:
        """Get tool for analyzing document structure using AWS Textract"""
        
        def analyze_document_structure(file_path: str) -> str:
            """Analyze document structure including tables and forms"""
            
            if not self.is_textract_ready or not self.textract_client:
                return "AWS Textract not available"
            
            try:
                file_path = Path(file_path)
                
                if not file_path.exists():
                    return f"File not found: {file_path}"
                
                with open(file_path, 'rb') as file:
                    file_content = file.read()
                
                # Use analyze_document for structured data extraction
                response = self.textract_client.analyze_document(
                    Document={'Bytes': file_content},
                    FeatureTypes=['TABLES', 'FORMS']
                )
                
                analysis_result = {
                    "text_blocks": 0,
                    "tables": 0,
                    "forms": 0,
                    "key_value_pairs": 0
                }
                
                for block in response.get('Blocks', []):
                    if block['BlockType'] == 'LINE':
                        analysis_result["text_blocks"] += 1
                    elif block['BlockType'] == 'TABLE':
                        analysis_result["tables"] += 1
                    elif block['BlockType'] == 'KEY_VALUE_SET':
                        analysis_result["forms"] += 1
                        if block.get('EntityTypes') and 'KEY' in block['EntityTypes']:
                            analysis_result["key_value_pairs"] += 1
                
                return f"Document Analysis: {analysis_result}"
                
            except Exception as e:
                return f"Analysis failed: {str(e)}"
        
        return Tool(
            name="analyze_document_structure",
            description="Analyze document structure including tables and forms using AWS Textract",
            func=analyze_document_structure
        )
    
    def get_document_metadata_tool(self) -> Tool:
        """Extract document metadata"""
        def extract_document_metadata(file_path: str) -> str:
            """Extract metadata from documents"""
            try:
                if not os.path.exists(file_path):
                    return f"Error: File not found at {file_path}"
                
                file_stats = os.stat(file_path)
                file_ext = os.path.splitext(file_path)[1].lower()
                
                metadata = {
                    "filename": os.path.basename(file_path),
                    "file_extension": file_ext,
                    "file_size_bytes": file_stats.st_size,
                    "file_size_mb": round(file_stats.st_size / (1024 * 1024), 2),
                    "created_time": file_stats.st_ctime,
                    "modified_time": file_stats.st_mtime,
                    "is_supported": file_ext in self.supported_formats,
                    "ocr_service": "AWS Textract" if self.is_textract_ready else "Not Available"
                }
                
                return f"Document metadata: {metadata}"
                
            except Exception as e:
                return f"Error extracting metadata: {str(e)}"
        
        return Tool(
            name="Document_Metadata",
            func=extract_document_metadata,
            description="Extract metadata information from uploaded documents"
        )
    
    def process_base64_image(self, base64_data: str, image_format: str = "png") -> str:
        """Process base64 encoded images using AWS Textract"""
        try:
            if not self.is_textract_ready or not self.textract_client:
                return "AWS Textract not available"
            
            # Decode base64 image
            image_bytes = base64.b64decode(base64_data)
            
            # Extract text directly from bytes
            result = self._extract_text_from_image_bytes(image_bytes)
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing base64 image: {e}")
            return f"Error processing base64 image: {str(e)}"
    
    def _extract_text_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file - public method with fallback"""
        self.logger.info(f"🔍 [OCR] Starting PDF text extraction for: {file_path.name}")
        
        if not self.is_textract_ready:
            # Fallback for when AWS credentials are not configured
            self.logger.warning(f"⚠️ [OCR] AWS Textract not ready - using fallback for PDF: {file_path.name}")
            self.logger.debug(f"🔧 [OCR] AWS credentials configured: {bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)}")
            self.logger.debug(f"🔧 [OCR] Textract client available: {bool(self.textract_client)}")
            return f"[OCR FALLBACK] Mock extracted text from PDF: {file_path.name}. Please configure AWS credentials for actual OCR processing."
        
        try:
            self.logger.debug(f"📖 [OCR] Reading PDF file: {file_path}")
            with open(file_path, 'rb') as file:
                file_content = file.read()
            self.logger.debug(f"📊 [OCR] PDF file size: {len(file_content)} bytes")
            
            result = self._extract_text_from_pdf_bytes(file_content)
            
            # Check if the result indicates an error
            if result.startswith("AWS Textract error:") or result.startswith("Error processing PDF:") or result.startswith("AWS credentials not configured"):
                self.logger.error(f"❌ [OCR] PDF processing failed: {result}")
                return f"[OCR ERROR] {result}"
            
            self.logger.info(f"✅ [OCR] Successfully extracted {len(result)} characters from PDF: {file_path.name}")
            return result
        except Exception as e:
            self.logger.error(f"❌ [OCR] Error extracting text from PDF {file_path}: {e}")
            self.logger.error(f"❌ [OCR] Exception type: {type(e).__name__}")
            return f"[OCR ERROR] Failed to extract text from PDF: {str(e)}"
    
    def _extract_text_from_image(self, file_path: Path) -> str:
        """Extract text from image file - public method with fallback"""
        self.logger.info(f"🔍 [OCR] Starting image text extraction for: {file_path.name}")
        
        if not self.is_textract_ready:
            # Fallback for when AWS credentials are not configured
            self.logger.warning(f"⚠️ [OCR] AWS Textract not ready - using fallback for image: {file_path.name}")
            self.logger.debug(f"🔧 [OCR] AWS credentials configured: {bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)}")
            self.logger.debug(f"🔧 [OCR] Textract client available: {bool(self.textract_client)}")
            return f"[OCR FALLBACK] Mock extracted text from image: {file_path.name}. Please configure AWS credentials for actual OCR processing."
        
        try:
            self.logger.debug(f"📖 [OCR] Reading image file: {file_path}")
            with open(file_path, 'rb') as file:
                file_content = file.read()
            self.logger.debug(f"📊 [OCR] Image file size: {len(file_content)} bytes")
            
            result = self._extract_text_from_image_bytes(file_content)
            
            # Check if the result indicates an error
            if result.startswith("AWS Textract error:") or result.startswith("Error processing image:") or result.startswith("AWS credentials not configured"):
                self.logger.error(f"❌ [OCR] Image processing failed: {result}")
                return f"[OCR ERROR] {result}"
            
            self.logger.info(f"✅ [OCR] Successfully extracted {len(result)} characters from image: {file_path.name}")
            return result
        except Exception as e:
            self.logger.error(f"❌ [OCR] Error extracting text from image {file_path}: {e}")
            self.logger.error(f"❌ [OCR] Exception type: {type(e).__name__}")
            return f"[OCR ERROR] Failed to extract text from image: {str(e)}"
    
    def _store_aws_response(self, job_id: str, all_responses: list, page_count: int) -> None:
        """Store AWS Textract response data to file for analysis"""
        import json
        from datetime import datetime
        
        try:
            # Create AWS responses directory
            aws_responses_dir = "data/aws_responses"
            os.makedirs(aws_responses_dir, exist_ok=True)
            
            # Create filename with timestamp
            timestamp = now_local().strftime("%Y%m%d_%H%M%S")
            filename = f"textract_response_{job_id}_{timestamp}.json"
            file_path = os.path.join(aws_responses_dir, filename)
            
            # Prepare response data for storage
            response_data = {
                "job_id": job_id,
                "timestamp": isoformat_now(),
                "page_count": page_count,
                "total_responses": len(all_responses),
                "responses": all_responses
            }
            
            # Store to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, default=str)
            
            self.logger.info(f"💾 [OCR] Stored AWS response to: {file_path}")
            self.logger.debug(f"📊 [OCR] Response file size: {os.path.getsize(file_path)} bytes")
            
        except Exception as e:
            self.logger.error(f"❌ [OCR] Failed to store AWS response: {e}")
            # Don't fail the main process if storage fails


def create_ocr_tools() -> List[Tool]:
    """Create OCR tools using AWS Textract"""
    toolkit = OCRToolkit()
    return toolkit.get_tools()


def extract_text(file_path: str) -> str:
    """Simple function to extract text from a file using AWS Textract"""
    toolkit = OCRToolkit()
    tool = toolkit.get_text_extraction_tool()
    return tool.func(file_path) 