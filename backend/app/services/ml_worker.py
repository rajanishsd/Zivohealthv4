#!/usr/bin/env python3
"""
ML Worker - Processes lab categorization and aggregation jobs
Runs on AWS Fargate Spot for cost efficiency

This worker supports TWO modes:
1. SQS Mode: Polls SQS queue for lab processing jobs
2. Background Aggregation Mode: Continuously processes pending lab/vitals/nutrition data

Mode is selected via ML_WORKER_MODE environment variable:
- "sqs" (default): Process jobs from SQS queue
- "aggregation": Run background aggregation worker
- "both": Run both SQS and aggregation workers
"""

import os
import sys
import json
import time
import signal
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

# Import database and models
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.crud.lab_categorization import LabCategorizationCRUD

# Import background worker
from app.core.background_worker import run_worker_process

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration from environment
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
SQS_QUEUE_URL = os.getenv('ML_WORKER_SQS_QUEUE_URL')
MAX_MESSAGES = int(os.getenv('ML_WORKER_BATCH_SIZE', '1'))
WAIT_TIME_SECONDS = int(os.getenv('ML_WORKER_WAIT_TIME', '20'))
VISIBILITY_TIMEOUT = int(os.getenv('ML_WORKER_VISIBILITY_TIMEOUT', '300'))
ML_WORKER_MODE = os.getenv('ML_WORKER_MODE', 'sqs').lower()  # 'sqs', 'aggregation', or 'both'

# Graceful shutdown flag
shutdown_flag = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_flag
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_flag = True

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


class MLWorker:
    """ML Worker that processes lab categorization jobs from SQS"""
    
    def __init__(self):
        self.sqs_client = None
        self.crud = LabCategorizationCRUD()
        self.processed_count = 0
        self.error_count = 0
        self.start_time = datetime.utcnow()
        
        # Validate configuration
        if not SQS_QUEUE_URL:
            raise ValueError("ML_WORKER_SQS_QUEUE_URL environment variable is required")
        
        logger.info("🚀 ML Worker initializing...")
        logger.info(f"   Queue URL: {SQS_QUEUE_URL}")
        logger.info(f"   Region: {AWS_REGION}")
        logger.info(f"   Batch Size: {MAX_MESSAGES}")
        logger.info(f"   Wait Time: {WAIT_TIME_SECONDS}s")
    
    def initialize_aws(self):
        """Initialize AWS SQS client"""
        try:
            self.sqs_client = boto3.client('sqs', region_name=AWS_REGION)
            logger.info("✅ AWS SQS client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize AWS client: {e}")
            raise
    
    def receive_messages(self) -> list:
        """Receive messages from SQS queue"""
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=MAX_MESSAGES,
                WaitTimeSeconds=WAIT_TIME_SECONDS,
                VisibilityTimeout=VISIBILITY_TIMEOUT,
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            if messages:
                logger.info(f"📥 Received {len(messages)} message(s) from SQS")
            
            return messages
        
        except ClientError as e:
            logger.error(f"❌ Error receiving messages from SQS: {e}")
            return []
    
    def process_message(self, message: Dict[str, Any]) -> bool:
        """Process a single lab categorization job"""
        receipt_handle = message['ReceiptHandle']
        message_id = message['MessageId']
        
        try:
            # Parse message body
            body = json.loads(message['Body'])
            logger.info(f"🔄 Processing message {message_id}")
            logger.info(f"   Job Type: {body.get('job_type', 'unknown')}")
            
            job_type = body.get('job_type')
            
            if job_type == 'lab_categorization':
                result = self._process_lab_categorization(body)
            elif job_type == 'loinc_mapping':
                result = self._process_loinc_mapping(body)
            elif job_type == 'process_pending_labs':
                result = self._process_pending_labs(body)
            elif job_type == 'process_pending_vitals':
                result = self._process_pending_vitals(body)
            elif job_type == 'process_pending_nutrition':
                result = self._process_pending_nutrition(body)
            else:
                logger.error(f"❌ Unknown job type: {job_type}")
                return False
            
            if result:
                logger.info(f"✅ Successfully processed message {message_id}")
                self.processed_count += 1
                return True
            else:
                logger.error(f"❌ Failed to process message {message_id}")
                self.error_count += 1
                return False
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in message {message_id}: {e}")
            self.error_count += 1
            return False
        
        except Exception as e:
            logger.error(f"❌ Error processing message {message_id}: {e}", exc_info=True)
            self.error_count += 1
            return False
    
    def _process_lab_categorization(self, job_data: Dict[str, Any]) -> bool:
        """
        Process lab categorization job (DEPRECATED - use process_pending_labs instead)
        
        This was the original approach where the full test data was sent via SQS.
        Now we use lightweight triggers that just tell the worker to check for pending labs.
        """
        user_id = job_data.get('user_id')
        document_id = job_data.get('document_id')
        tests = job_data.get('tests', [])
        
        logger.info(f"🧪 Processing lab categorization for user {user_id}, document {document_id}")
        logger.info(f"   Tests count: {len(tests)}")
        logger.warning("⚠️  This job type is deprecated, use 'process_pending_labs' instead")
        
        db = SessionLocal()
        try:
            # Get pending reports from database instead of using the provided tests
            pending_reports = self.crud.get_pending_categorization_entries(db, limit=100)
            
            if not pending_reports:
                logger.info("✅ No pending lab reports found")
                return True
            
            # Categorize and transfer to lab_report_categorized
            categorized_count = self.crud.categorize_and_transfer_lab_reports(db, pending_reports)
            logger.info(f"✅ Categorized {categorized_count} lab reports")
            return True
        
        except Exception as e:
            logger.error(f"❌ Lab categorization failed: {e}", exc_info=True)
            db.rollback()
            return False
        
        finally:
            db.close()
    
    def _process_loinc_mapping(self, job_data: Dict[str, Any]) -> bool:
        """Process LOINC mapping job"""
        test_name = job_data.get('test_name')
        
        logger.info(f"🔬 Processing LOINC mapping for test: {test_name}")
        
        db = SessionLocal()
        try:
            # Call the LOINC mapping CRUD
            result = self.crud.map_test_to_loinc(
                db=db,
                test_name=test_name
            )
            
            logger.info(f"✅ LOINC mapping completed: {result}")
            return True
        
        except Exception as e:
            logger.error(f"❌ LOINC mapping failed: {e}", exc_info=True)
            db.rollback()
            return False
        
        finally:
            db.close()
    
    def _process_pending_labs(self, job_data: Dict[str, Any]) -> bool:
        """
        Process all pending lab reports for a user
        
        This is triggered when a lab is uploaded - it processes all pending
        lab reports in the lab_report_raw table (categorization + aggregation)
        """
        user_id = job_data.get('user_id')
        
        logger.info(f"🧪 Processing pending labs for user {user_id}")
        
        db = SessionLocal()
        try:
            # Get pending lab reports from lab_report_raw
            pending_reports = self.crud.get_pending_categorization_entries(db, limit=100)
            
            if not pending_reports:
                logger.info(f"✅ No pending lab reports found for user {user_id}")
                return True
            
            logger.info(f"   Found {len(pending_reports)} pending lab reports")
            
            # Categorize and transfer to lab_report_categorized
            categorized_count = self.crud.categorize_and_transfer_lab_reports(db, pending_reports)
            logger.info(f"   Categorized {categorized_count} lab reports")
            
            # Now trigger aggregation for affected users and dates
            from app.crud.lab_aggregation import LabAggregationCRUD
            
            affected_users_dates = set()
            for report in pending_reports:
                affected_users_dates.add((report.user_id, report.test_date))
            
            logger.info(f"   Aggregating data for {len(affected_users_dates)} user/date combinations")
            
            # Aggregate lab data for each affected user/date
            for uid, test_date in affected_users_dates:
                try:
                    # Aggregate daily lab data
                    daily_count = LabAggregationCRUD.aggregate_daily_data(db, uid, test_date)
                    
                    # Aggregate monthly data
                    monthly_count = LabAggregationCRUD.aggregate_monthly_data(db, uid, test_date.year, test_date.month)
                    
                    # Aggregate quarterly data
                    quarter = ((test_date.month - 1) // 3) + 1
                    quarterly_count = LabAggregationCRUD.aggregate_quarterly_data(db, uid, test_date.year, quarter)
                    
                    # Aggregate yearly data
                    yearly_count = LabAggregationCRUD.aggregate_yearly_data(db, uid, test_date.year)
                    
                    logger.info(
                        f"   User {uid}: {daily_count} daily, {monthly_count} monthly, "
                        f"{quarterly_count} quarterly, {yearly_count} yearly aggregates"
                    )
                    
                except Exception as e:
                    logger.error(f"❌ Aggregation failed for user {uid} on {test_date}: {e}")
            
            logger.info(f"✅ Pending labs processing completed for user {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Pending labs processing failed: {e}", exc_info=True)
            db.rollback()
            return False
        
        finally:
            db.close()
    
    def _process_pending_vitals(self, job_data: Dict[str, Any]) -> bool:
        """
        Process all pending vitals data for a user
        
        This is triggered when vitals are synced - it processes all pending
        vitals in the vitals_raw_data table (categorization + aggregation)
        
        Processing order (EXACT replica of background_worker.py logic):
        1. Get pending entries
        2. Group by user_id and date
        3. Mark as processing
        4. For each user/date:
           - Copy raw to categorized with LOINC
           - Aggregate hourly data
           - Aggregate daily data
           - Aggregate weekly data (week starts Monday)
           - Aggregate monthly data
           - Mark categorized as aggregated
        5. On error: mark as failed
        """
        user_id = job_data.get('user_id')
        
        logger.info(f"💓 Processing pending vitals for user {user_id}")
        
        db = SessionLocal()
        try:
            # Import required modules (same as background_worker.py)
            from app.crud.vitals import VitalsCRUD
            from datetime import timedelta, date as date_type
            
            # Get pending vitals entries from vitals_raw_data
            pending_entries = VitalsCRUD.get_pending_aggregation_entries(db, limit=100)
            
            if not pending_entries:
                logger.info(f"✅ No pending vitals found for user {user_id}")
                return True
            
            logger.info(f"   Found {len(pending_entries)} pending vitals entries")
            
            # Group entries by user and date for efficient aggregation
            user_date_groups = {}
            for entry in pending_entries:
                uid = entry.user_id
                entry_date = entry.start_date.date()
                key = (uid, entry_date)
                
                if key not in user_date_groups:
                    user_date_groups[key] = []
                user_date_groups[key].append(entry)
            
            # Mark entries as processing
            entry_ids = [entry.id for entry in pending_entries]
            VitalsCRUD.mark_aggregation_processing(db, entry_ids)
            db.commit()  # Commit status updates immediately
            
            processed_count = 0
            
            # Process each user-date group
            for (uid, target_date), group_entries in user_date_groups.items():
                try:
                    # Step 1: Copy raw data to categorized table with LOINC code mapping
                    categorized_count = VitalsCRUD.copy_raw_to_categorized_with_loinc(db, uid, target_date)
                    logger.debug(f"   📋 Categorized {categorized_count} vitals records with LOINC codes")
                    
                    # Step 2: Aggregate hourly data first
                    hourly_count = VitalsCRUD.aggregate_hourly_data(db, uid, target_date)
                    
                    # Then aggregate daily data
                    daily_count = VitalsCRUD.aggregate_daily_data(db, uid, target_date)
                    
                    # Calculate week start (Monday) for weekly aggregation
                    days_since_monday = target_date.weekday()
                    week_start = target_date - timedelta(days=days_since_monday)
                    
                    # Aggregate weekly data
                    weekly_count = VitalsCRUD.aggregate_weekly_data(db, uid, week_start)
                    
                    # Aggregate monthly data
                    monthly_count = VitalsCRUD.aggregate_monthly_data(db, uid, target_date.year, target_date.month)
                    
                    # Step 3: Mark categorized records as aggregated after successful aggregation
                    aggregated_count = VitalsCRUD.mark_categorized_aggregation_completed(db, uid, target_date)
                    
                    logger.info(
                        f"   User {uid}: {hourly_count} hourly, {daily_count} daily, "
                        f"{weekly_count} weekly, {monthly_count} monthly vitals aggregates; "
                        f"marked {aggregated_count} categorized records as aggregated"
                    )
                    
                    # Commit after each user-date aggregation to release locks
                    db.commit()
                    
                    processed_count += len(group_entries)
                    
                except Exception as e:
                    db.rollback()  # Rollback failed transaction
                    logger.error(f"❌ Vitals aggregation failed for user {uid} on {target_date}: {e}")
                    
                    # Mark entries as failed
                    group_entry_ids = [entry.id for entry in group_entries]
                    VitalsCRUD.mark_aggregation_failed(db, group_entry_ids, str(e))
                    db.commit()  # Commit failure status
            
            logger.info(f"✅ Pending vitals processing completed: {processed_count} entries processed")
            return True
        
        except Exception as e:
            logger.error(f"❌ Pending vitals processing failed: {e}", exc_info=True)
            db.rollback()
            return False
        
        finally:
            db.close()
    
    def _process_pending_nutrition(self, job_data: Dict[str, Any]) -> bool:
        """
        Process all pending nutrition data for a user
        
        This is triggered when nutrition is submitted - it processes all pending
        nutrition in the nutrition_raw_data table (aggregation only, no categorization)
        
        Processing order (EXACT replica of background_worker.py logic):
        1. Get pending entries
        2. Group by user_id and meal_date
        3. Mark as processing
        4. For each user/date:
           - Aggregate daily data
           - Aggregate weekly data (week starts Monday)
           - Aggregate monthly data
        5. On error: mark as failed
        """
        user_id = job_data.get('user_id')
        
        logger.info(f"🍎 Processing pending nutrition for user {user_id}")
        
        db = SessionLocal()
        try:
            # Import required modules (same as background_worker.py)
            from app.crud.nutrition import nutrition_data as NutritionCRUD
            from datetime import timedelta, date as date_type
            
            # Get pending nutrition entries from nutrition_raw_data
            pending_entries = NutritionCRUD.get_pending_aggregation_entries(db, limit=100)
            
            if not pending_entries:
                logger.info(f"✅ No pending nutrition found for user {user_id}")
                return True
            
            logger.info(f"   Found {len(pending_entries)} pending nutrition entries")
            
            # Group entries by user and date for efficient aggregation
            user_date_groups = {}
            for entry in pending_entries:
                uid = entry.user_id
                entry_date = entry.meal_date  # Note: nutrition uses meal_date, not start_date
                key = (uid, entry_date)
                
                if key not in user_date_groups:
                    user_date_groups[key] = []
                user_date_groups[key].append(entry)
            
            # Mark entries as processing
            entry_ids = [entry.id for entry in pending_entries]
            NutritionCRUD.mark_aggregation_processing(db, entry_ids)
            db.commit()  # Commit status updates immediately
            
            processed_count = 0
            
            # Process each user-date group
            for (uid, target_date), group_entries in user_date_groups.items():
                try:
                    # Aggregate daily data first
                    daily_count = NutritionCRUD.aggregate_daily_data(db, uid, target_date)
                    
                    # Calculate week start (Monday) for weekly aggregation
                    days_since_monday = target_date.weekday()
                    week_start = target_date - timedelta(days=days_since_monday)
                    
                    # Aggregate weekly data
                    weekly_count = NutritionCRUD.aggregate_weekly_data(db, uid, week_start)
                    
                    # Aggregate monthly data
                    monthly_count = NutritionCRUD.aggregate_monthly_data(db, uid, target_date.year, target_date.month)
                    
                    logger.info(
                        f"   User {uid}: {daily_count} daily, {weekly_count} weekly, "
                        f"{monthly_count} monthly nutrition aggregates"
                    )
                    
                    # Commit after each user-date aggregation to release locks
                    db.commit()
                    
                    processed_count += len(group_entries)
                    
                except Exception as e:
                    db.rollback()  # Rollback failed transaction
                    logger.error(f"❌ Nutrition aggregation failed for user {uid} on {target_date}: {e}")
                    
                    # Mark entries as failed
                    group_entry_ids = [entry.id for entry in group_entries]
                    NutritionCRUD.mark_aggregation_failed(db, group_entry_ids, str(e))
                    db.commit()  # Commit failure status
            
            logger.info(f"✅ Pending nutrition processing completed: {processed_count} entries processed")
            return True
        
        except Exception as e:
            logger.error(f"❌ Pending nutrition processing failed: {e}", exc_info=True)
            db.rollback()
            return False
        
        finally:
            db.close()
    
    def delete_message(self, receipt_handle: str) -> bool:
        """Delete message from SQS queue"""
        try:
            self.sqs_client.delete_message(
                QueueUrl=SQS_QUEUE_URL,
                ReceiptHandle=receipt_handle
            )
            logger.info("🗑️  Message deleted from queue")
            return True
        
        except ClientError as e:
            logger.error(f"❌ Error deleting message from SQS: {e}")
            return False
    
    def log_stats(self):
        """Log worker statistics"""
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        logger.info(f"📊 Worker Stats:")
        logger.info(f"   Uptime: {uptime:.0f}s")
        logger.info(f"   Processed: {self.processed_count}")
        logger.info(f"   Errors: {self.error_count}")
        if self.processed_count > 0:
            logger.info(f"   Success Rate: {(self.processed_count/(self.processed_count+self.error_count))*100:.1f}%")
    
    def run(self):
        """Main worker loop"""
        logger.info("🎯 ML Worker started, polling for messages...")
        
        # Initialize AWS
        self.initialize_aws()
        
        # Stats logging interval
        last_stats_time = time.time()
        stats_interval = 300  # Log stats every 5 minutes
        
        while not shutdown_flag:
            try:
                # Receive messages
                messages = self.receive_messages()
                
                if not messages:
                    # No messages, continue polling
                    continue
                
                # Process each message
                for message in messages:
                    if shutdown_flag:
                        logger.info("⚠️  Shutdown flag set, stopping message processing")
                        break
                    
                    # Process the message
                    success = self.process_message(message)
                    
                    # Delete message if successful
                    if success:
                        self.delete_message(message['ReceiptHandle'])
                    else:
                        logger.warning("⚠️  Message processing failed, will retry after visibility timeout")
                
                # Log stats periodically
                if time.time() - last_stats_time > stats_interval:
                    self.log_stats()
                    last_stats_time = time.time()
            
            except KeyboardInterrupt:
                logger.info("⚠️  Received keyboard interrupt, shutting down...")
                break
            
            except Exception as e:
                logger.error(f"❌ Unexpected error in worker loop: {e}", exc_info=True)
                time.sleep(5)  # Wait before retrying
        
        # Final stats
        logger.info("🛑 ML Worker shutting down...")
        self.log_stats()


def main():
    """Main entry point"""
    logger.info("=" * 80)
    logger.info("ML Worker Service - Lab Categorization, LOINC Mapping & Aggregation")
    logger.info("=" * 80)
    logger.info(f"🎯 Mode: {ML_WORKER_MODE.upper()}")
    logger.info("=" * 80)
    
    # DEBUG: Check OPENAI_API_KEY
    import os
    openai_key = os.getenv('OPENAI_API_KEY', '')
    logger.info(f"🔍 DEBUG: OPENAI_API_KEY is set: {bool(openai_key)}")
    logger.info(f"🔍 DEBUG: OPENAI_API_KEY length: {len(openai_key)}")
    if openai_key:
        logger.info(f"🔍 DEBUG: OPENAI_API_KEY starts with: {openai_key[:10]}...")
    
    try:
        if ML_WORKER_MODE == 'sqs':
            # Run only SQS worker
            logger.info("📬 Starting SQS worker mode...")
            worker = MLWorker()
            worker.run()
            
        elif ML_WORKER_MODE == 'aggregation':
            # Run only background aggregation worker
            logger.info("🔄 Starting background aggregation mode...")
            asyncio.run(run_worker_process())
            
        elif ML_WORKER_MODE == 'both':
            # Run both SQS and aggregation workers concurrently
            logger.info("🚀 Starting BOTH SQS and aggregation workers...")
            
            # Create async tasks for both workers
            async def run_both_workers():
                sqs_task = asyncio.create_task(run_sqs_worker_async())
                aggregation_task = asyncio.create_task(run_worker_process())
                
                # Wait for both tasks (they run indefinitely)
                await asyncio.gather(sqs_task, aggregation_task, return_exceptions=True)
            
            asyncio.run(run_both_workers())
        else:
            logger.error(f"❌ Invalid ML_WORKER_MODE: {ML_WORKER_MODE}")
            logger.error("   Valid modes: 'sqs', 'aggregation', 'both'")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("⚠️  Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("✅ ML Worker stopped gracefully")
    sys.exit(0)


async def run_sqs_worker_async():
    """Run SQS worker in async mode"""
    try:
        worker = MLWorker()
        
        # Convert synchronous run() to async
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, worker.run)
    except Exception as e:
        logger.error(f"❌ SQS worker error: {e}", exc_info=True)


if __name__ == "__main__":
    main()

