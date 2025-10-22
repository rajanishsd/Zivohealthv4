"""
SQS Client for ML Worker Job Queue
Sends lab categorization and LOINC mapping jobs to SQS for async processing
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
ML_WORKER_SQS_QUEUE_URL = os.getenv('ML_WORKER_SQS_QUEUE_URL')
ML_WORKER_ENABLED = os.getenv('ML_WORKER_ENABLED', 'false').lower() == 'true'


class MLWorkerClient:
    """Client for sending jobs to ML Worker via SQS"""
    
    def __init__(self):
        self.sqs_client = None
        self.queue_url = ML_WORKER_SQS_QUEUE_URL
        self.enabled = ML_WORKER_ENABLED
        
        if self.enabled and self.queue_url:
            try:
                self.sqs_client = boto3.client('sqs', region_name=AWS_REGION)
                logger.info(f"✅ ML Worker SQS client initialized (queue: {self.queue_url})")
            except Exception as e:
                logger.error(f"❌ Failed to initialize SQS client: {e}")
                self.enabled = False
        else:
            logger.info("ℹ️  ML Worker is disabled or queue URL not configured")
    
    def is_enabled(self) -> bool:
        """Check if ML Worker is enabled"""
        return self.enabled and self.sqs_client is not None
    
    def send_lab_categorization_job(
        self,
        user_id: int,
        document_id: int,
        tests: list,
        priority: str = "normal"
    ) -> Optional[str]:
        """
        Send lab categorization job to SQS
        
        Args:
            user_id: User ID
            document_id: Document ID
            tests: List of lab test dictionaries
            priority: Job priority ("high", "normal", "low")
        
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.is_enabled():
            logger.warning("ML Worker is not enabled, cannot send job")
            return None
        
        try:
            message_body = {
                "job_type": "lab_categorization",
                "user_id": user_id,
                "document_id": document_id,
                "tests": tests,
                "priority": priority,
                "submitted_at": datetime.utcnow().isoformat(),
                "test_count": len(tests)
            }
            
            # Send message to SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    'JobType': {
                        'DataType': 'String',
                        'StringValue': 'lab_categorization'
                    },
                    'Priority': {
                        'DataType': 'String',
                        'StringValue': priority
                    },
                    'UserId': {
                        'DataType': 'Number',
                        'StringValue': str(user_id)
                    }
                }
            )
            
            message_id = response['MessageId']
            logger.info(
                f"✅ Lab categorization job sent to SQS "
                f"(user: {user_id}, doc: {document_id}, tests: {len(tests)}, msg_id: {message_id})"
            )
            return message_id
        
        except ClientError as e:
            logger.error(f"❌ Failed to send lab categorization job to SQS: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error sending job to SQS: {e}")
            return None
    
    def send_loinc_mapping_job(
        self,
        test_name: str,
        priority: str = "normal"
    ) -> Optional[str]:
        """
        Send LOINC mapping job to SQS
        
        Args:
            test_name: Name of the lab test
            priority: Job priority ("high", "normal", "low")
        
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.is_enabled():
            logger.warning("ML Worker is not enabled, cannot send job")
            return None
        
        try:
            message_body = {
                "job_type": "loinc_mapping",
                "test_name": test_name,
                "priority": priority,
                "submitted_at": datetime.utcnow().isoformat()
            }
            
            # Send message to SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    'JobType': {
                        'DataType': 'String',
                        'StringValue': 'loinc_mapping'
                    },
                    'Priority': {
                        'DataType': 'String',
                        'StringValue': priority
                    }
                }
            )
            
            message_id = response['MessageId']
            logger.info(f"✅ LOINC mapping job sent to SQS (test: {test_name}, msg_id: {message_id})")
            return message_id
        
        except ClientError as e:
            logger.error(f"❌ Failed to send LOINC mapping job to SQS: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error sending job to SQS: {e}")
            return None
    
    def send_lab_processing_trigger(
        self,
        user_id: int,
        priority: str = "normal"
    ) -> Optional[str]:
        """
        Send a trigger to process pending lab reports for a user
        
        This is a lightweight trigger that tells the ML worker to check for
        and process any pending lab reports in lab_report_raw table.
        
        Args:
            user_id: User ID whose pending labs should be processed
            priority: Job priority ("high", "normal", "low")
        
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.is_enabled():
            logger.warning("ML Worker is not enabled, cannot send job")
            return None
        
        try:
            message_body = {
                "job_type": "process_pending_labs",
                "user_id": user_id,
                "priority": priority,
                "submitted_at": datetime.utcnow().isoformat()
            }
            
            # Send message to SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    'JobType': {
                        'DataType': 'String',
                        'StringValue': 'process_pending_labs'
                    },
                    'Priority': {
                        'DataType': 'String',
                        'StringValue': priority
                    },
                    'UserId': {
                        'DataType': 'Number',
                        'StringValue': str(user_id)
                    }
                }
            )
            
            message_id = response['MessageId']
            logger.info(
                f"✅ Lab processing trigger sent to SQS "
                f"(user: {user_id}, msg_id: {message_id})"
            )
            return message_id
        
        except ClientError as e:
            logger.error(f"❌ Failed to send lab processing trigger to SQS: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error sending trigger to SQS: {e}")
            return None
    
    def send_vitals_processing_trigger(
        self,
        user_id: int,
        priority: str = "normal"
    ) -> Optional[str]:
        """
        Send a trigger to process pending vitals data for a user
        
        This is a lightweight trigger that tells the ML worker to check for
        and process any pending vitals data in vitals_raw_data table.
        
        Args:
            user_id: User ID whose pending vitals should be processed
            priority: Job priority ("high", "normal", "low")
        
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.is_enabled():
            logger.warning("ML Worker is not enabled, cannot send job")
            return None
        
        try:
            message_body = {
                "job_type": "process_pending_vitals",
                "user_id": user_id,
                "priority": priority,
                "submitted_at": datetime.utcnow().isoformat()
            }
            
            # Send message to SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    'JobType': {
                        'DataType': 'String',
                        'StringValue': 'process_pending_vitals'
                    },
                    'Priority': {
                        'DataType': 'String',
                        'StringValue': priority
                    },
                    'UserId': {
                        'DataType': 'Number',
                        'StringValue': str(user_id)
                    }
                }
            )
            
            message_id = response['MessageId']
            logger.info(
                f"✅ Vitals processing trigger sent to SQS "
                f"(user: {user_id}, msg_id: {message_id})"
            )
            return message_id
        
        except ClientError as e:
            logger.error(f"❌ Failed to send vitals processing trigger to SQS: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error sending trigger to SQS: {e}")
            return None
    
    def send_nutrition_processing_trigger(
        self,
        user_id: int,
        priority: str = "normal"
    ) -> Optional[str]:
        """
        Send a trigger to process pending nutrition data for a user
        
        This is a lightweight trigger that tells the ML worker to check for
        and process any pending nutrition data in nutrition_raw_data table.
        
        Args:
            user_id: User ID whose pending nutrition should be processed
            priority: Job priority ("high", "normal", "low")
        
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.is_enabled():
            logger.warning("ML Worker is not enabled, cannot send job")
            return None
        
        try:
            message_body = {
                "job_type": "process_pending_nutrition",
                "user_id": user_id,
                "priority": priority,
                "submitted_at": datetime.utcnow().isoformat()
            }
            
            # Send message to SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    'JobType': {
                        'DataType': 'String',
                        'StringValue': 'process_pending_nutrition'
                    },
                    'Priority': {
                        'DataType': 'String',
                        'StringValue': priority
                    },
                    'UserId': {
                        'DataType': 'Number',
                        'StringValue': str(user_id)
                    }
                }
            )
            
            message_id = response['MessageId']
            logger.info(
                f"✅ Nutrition processing trigger sent to SQS "
                f"(user: {user_id}, msg_id: {message_id})"
            )
            return message_id
        
        except ClientError as e:
            logger.error(f"❌ Failed to send nutrition processing trigger to SQS: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error sending trigger to SQS: {e}")
            return None
    
    def get_queue_depth(self) -> Optional[int]:
        """
        Get approximate number of messages in queue
        
        Returns:
            Number of messages, or None if error
        """
        if not self.is_enabled():
            return None
        
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=['ApproximateNumberOfMessages']
            )
            
            count = int(response['Attributes']['ApproximateNumberOfMessages'])
            return count
        
        except Exception as e:
            logger.error(f"❌ Failed to get queue depth: {e}")
            return None


# Global instance
_ml_worker_client = None

def get_ml_worker_client() -> MLWorkerClient:
    """Get or create ML Worker client singleton"""
    global _ml_worker_client
    if _ml_worker_client is None:
        _ml_worker_client = MLWorkerClient()
    return _ml_worker_client

