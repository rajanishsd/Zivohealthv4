#!/usr/bin/env python3
"""
Smart Delayed Aggregation Worker - Separate Process Architecture
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.crud.vitals import VitalsCRUD
from app.crud.nutrition import nutrition_data as NutritionCRUD
from app.models.vitals_data import VitalsRawData
from app.models.nutrition_data import NutritionRawData
from app.core.config import settings
from app.utils.timezone import now_local
# Configure logging for worker process
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SmartDelayedAggregationWorker:
    """
    Smart delayed aggregation worker designed for separate process execution
    """
    
    def __init__(self, batch_size: int = None, delay_seconds: int = 30, allowed_domains: set = None):
        # Configuration - smaller batch sizes to prevent connection exhaustion
        self.batch_size = batch_size or 100  # Reduced from default to 100
        self.delay_seconds = delay_seconds
        self.max_batch_size = 500  # Hard limit to prevent connection pool exhaustion
        
        # Optional domain filtering: {'vitals', 'nutrition', 'labs'} or None for all
        self.allowed_domains = set(allowed_domains) if allowed_domains else None
        
        # Worker state
        self.running = False
        self.start_time = None
        self.total_processed = 0
        self.batches_processed = 0
        self.pending_timer_task = None
        
        # Ensure batch size doesn't exceed safe limits
        if self.batch_size > self.max_batch_size:
            logger.warning(f"Batch size {self.batch_size} exceeds safe limit, reducing to {self.max_batch_size}")
            self.batch_size = self.max_batch_size

    async def trigger_delayed_aggregation(self, user_id: int = None, domains: list = None):
        """Trigger smart delayed aggregation - waits for data chunks to stop.
        If domains provided, restrict processing to those domains for this run.
        """
        
        # Update domain restriction for this cycle if provided
        if domains is not None:
            self.allowed_domains = set(domains)
        
        # Cancel existing timer if running
        if self.pending_timer_task and not self.pending_timer_task.done():
            self.pending_timer_task.cancel()
            logger.info(f"⏰ [SmartWorker] Data received - will start aggregation in {self.delay_seconds}s if no more data arrives")
        else:
            logger.info(f"⏰ [SmartWorker] Data received - will start aggregation in {self.delay_seconds}s if no more data arrives")
        
        # Start new timer
        self.pending_timer_task = asyncio.create_task(
            self._delayed_aggregation_timer(user_id)
        )

    async def _delayed_aggregation_timer(self, user_id: int = None):
        """Wait for delay period, then start aggregation if no more data arrives"""
        try:
            await asyncio.sleep(self.delay_seconds)
            
            # If we reach here, no new data arrived during delay period
            logger.info(f"🚀 [SmartWorker] Delay period complete - starting aggregation")
            
            # Check if worker is already running before starting
            if self.running:
                logger.info(f"⚠️ [SmartWorker] Worker already running from previous trigger - skipping")
                return
            
            # Start processing in the same event loop to avoid conflicts
            await self.process_all_pending_data()
            
        except asyncio.CancelledError:
            logger.info(f"⏰ [SmartWorker] Timer cancelled - new data arrived, resetting delay")
            raise
        except Exception as e:
            logger.error(f"❌ [SmartWorker] Error in delayed aggregation timer: {e}")
            # Reset running state in case of error
            self.running = False

    async def process_all_pending_data(self):
        """Process ALL pending data in small batches with proper connection cleanup"""
        if self.running:
            logger.info(f"⚠️ [SmartWorker] Already running - skipping duplicate start")
            return 0
            
        self.running = True
        self.start_time = now_local()
        
        logger.info("🚀 [SmartWorker] Starting delayed aggregation - will process until completion")
        
        total_cycles = 0
        max_cycles = 1000  # Prevent infinite loops
        max_duration = 300  # 5 minutes max runtime
        
        try:
            while self.running:
                # Check for timeout
                duration = (now_local() - self.start_time).total_seconds()
                if duration > max_duration:
                    logger.warning(f"⏰ [SmartWorker] Max duration ({max_duration}s) reached - stopping")
                    break
                
                # Check for max cycles
                if total_cycles >= max_cycles:
                    logger.warning(f"⏰ [SmartWorker] Max cycles ({max_cycles}) reached - stopping")
                    break
                
                # Process one small batch with fresh connection
                try:
                    processed_count = await self.process_batch()
                except Exception as e:
                    logger.error(f"❌ [SmartWorker] Error processing batch: {e}")
                    # Continue with next batch instead of failing completely
                    processed_count = 0
                
                if processed_count == 0:
                    # No more data to process - mission complete!
                    logger.info("✅ [SmartWorker] No more pending data - job complete, terminating")
                    break
                
                total_cycles += 1
                self.total_processed += processed_count
                self.batches_processed += 1
                
                # Log progress every 10 batches
                if total_cycles % 10 == 0:
                    logger.info(f"📊 [SmartWorker] Progress: {self.total_processed:,} entries processed in {total_cycles} batches")
                
                # Small delay between batches to prevent overwhelming the database
                await asyncio.sleep(0.1)
            
            # Final statistics
            duration = (now_local() - self.start_time).total_seconds()
            throughput = self.total_processed / duration if duration > 0 else 0
            
            logger.info(f"🎉 [SmartWorker] Job completed successfully!")
            logger.info(f"📈 Final Stats: {self.total_processed:,} entries, {self.batches_processed} batches, {duration:.1f}s, {throughput:.1f} entries/sec")
            
            return self.total_processed
            
        except Exception as e:
            logger.error(f"❌ [SmartWorker] Critical error in process_all_pending_data: {e}")
            return 0
        finally:
            self.running = False

    async def process_batch(self) -> int:
        """Process a batch of pending aggregation data"""
        db = SessionLocal()
        try:
            # Get pending entries for requested systems only
            vitals_entries = []
            nutrition_entries = []
            lab_entries = []

            if self.allowed_domains is None or 'vitals' in self.allowed_domains:
                vitals_entries = VitalsCRUD.get_pending_aggregation_entries(db, limit=self.batch_size)
            if self.allowed_domains is None or 'nutrition' in self.allowed_domains:
                nutrition_entries = NutritionCRUD.get_pending_aggregation_entries(db, limit=self.batch_size)
            if self.allowed_domains is None or 'labs' in self.allowed_domains:
                from app.crud.lab_categorization import lab_categorization
                lab_entries = lab_categorization.get_pending_categorization_entries(db, limit=self.batch_size)
            
            # Combine all types for processing
            total_entries = len(vitals_entries) + len(nutrition_entries) + len(lab_entries)
            
            if total_entries == 0:
                logger.info("📊 [SmartWorker] No pending data found")
                return 0
            
            logger.info(f"📊 [SmartWorker] Processing batch: {len(vitals_entries)} vitals + {len(nutrition_entries)} nutrition + {len(lab_entries)} lab reports = {total_entries} total entries")
            
            processed_count = 0
            
            # Process vitals data
            if vitals_entries:
                processed_count += await self._process_vitals_batch(db, vitals_entries)
            
            # Process nutrition data  
            if nutrition_entries:
                processed_count += await self._process_nutrition_batch(db, nutrition_entries)
            
            # Process lab categorization and aggregation
            if lab_entries:
                processed_count += await self._perform_lab_categorization_and_aggregation(db)
            
            return processed_count
        finally:
            db.close()

    async def _process_vitals_batch(self, db: Session, entries: List[VitalsRawData]) -> int:
        """Process a batch of vitals entries"""
        processed_count = 0
        
        # Group entries by user and date for efficient aggregation
        user_date_groups = {}
        for entry in entries:
            user_id = entry.user_id
            entry_date = entry.start_date.date()
            key = (user_id, entry_date)
            
            if key not in user_date_groups:
                user_date_groups[key] = []
            user_date_groups[key].append(entry)
        
        # Mark entries as processing
        entry_ids = [entry.id for entry in entries]
        VitalsCRUD.mark_aggregation_processing(db, entry_ids)
        
        # Process each user-date group
        for (user_id, target_date), group_entries in user_date_groups.items():
            try:
                await self._perform_vitals_aggregation(db, user_id, target_date)
                
                # Note: Don't mark entries as "completed" - they are marked as "categorized" 
                # in copy_raw_to_categorized_with_loinc method, which is the correct status
                # for vitals_raw_data after categorization
                processed_count += len(group_entries)
                
                logger.debug(f"✅ [SmartWorker] Completed vitals aggregation for user {user_id} on {target_date}")
                    
            except Exception as e:
                logger.error(f"❌ [SmartWorker] Vitals aggregation failed for user {user_id} on {target_date}: {e}")
                
                # Mark entries as failed
                group_entry_ids = [entry.id for entry in group_entries]
                VitalsCRUD.mark_aggregation_failed(db, group_entry_ids, str(e))
        
        return processed_count

    async def _process_nutrition_batch(self, db: Session, entries: List[NutritionRawData]) -> int:
        """Process a batch of nutrition entries"""
        processed_count = 0
        
        # Group entries by user and date for efficient aggregation
        user_date_groups = {}
        for entry in entries:
            user_id = entry.user_id
            entry_date = entry.meal_date
            key = (user_id, entry_date)
            
            if key not in user_date_groups:
                user_date_groups[key] = []
            user_date_groups[key].append(entry)
        
        # Mark entries as processing
        entry_ids = [entry.id for entry in entries]
        NutritionCRUD.mark_aggregation_processing(db, entry_ids)
        
        # Process each user-date group
        for (user_id, target_date), group_entries in user_date_groups.items():
            try:
                await self._perform_nutrition_aggregation(db, user_id, target_date)
                
                # Mark entries as completed (done inside the aggregation methods)
                processed_count += len(group_entries)
                
                logger.info(f"✅ [SmartWorker] Completed nutrition aggregation for user {user_id} on {target_date}")
                
            except Exception as e:
                logger.error(f"❌ [SmartWorker] Nutrition aggregation failed for user {user_id} on {target_date}: {e}")
                
                # Mark entries as failed
                group_entry_ids = [entry.id for entry in group_entries]
                NutritionCRUD.mark_aggregation_failed(db, group_entry_ids, str(e))
        
        return processed_count

    async def _perform_vitals_aggregation(self, db: Session, user_id: int, target_date: date):
        """Perform the actual vitals aggregation for a user and date"""
        # Step 1: Copy raw data to categorized table with LOINC code mapping
        categorized_count = VitalsCRUD.copy_raw_to_categorized_with_loinc(db, user_id, target_date)
        logger.debug(f"📋 [SmartWorker] Categorized {categorized_count} vitals records with LOINC codes")
        
        # Step 2: Aggregate hourly data first
        hourly_count = VitalsCRUD.aggregate_hourly_data(db, user_id, target_date)
        # Then aggregate daily data
        daily_count = VitalsCRUD.aggregate_daily_data(db, user_id, target_date)
        
        # Calculate week start (Monday) for weekly aggregation
        days_since_monday = target_date.weekday()
        week_start = target_date - timedelta(days=days_since_monday)
        
        # Aggregate weekly data
        weekly_count = VitalsCRUD.aggregate_weekly_data(db, user_id, week_start)
        
        # Aggregate monthly data
        monthly_count = VitalsCRUD.aggregate_monthly_data(db, user_id, target_date.year, target_date.month)
        
        # Step 3: Mark categorized records as aggregated after successful aggregation
        aggregated_count = VitalsCRUD.mark_categorized_aggregation_completed(db, user_id, target_date)
        
        logger.debug(f"📊 [SmartWorker] Created {hourly_count} hourly, {daily_count} daily, {weekly_count} weekly, {monthly_count} monthly vitals aggregates; marked {aggregated_count} categorized records as aggregated")

    async def _perform_nutrition_aggregation(self, db: Session, user_id: int, target_date: date):
        """Perform the actual nutrition aggregation for a user and date"""
        # Aggregate daily data first
        daily_count = NutritionCRUD.aggregate_daily_data(db, user_id, target_date)
        
        # Calculate week start (Monday) for weekly aggregation
        days_since_monday = target_date.weekday()
        week_start = target_date - timedelta(days=days_since_monday)
        
        # Aggregate weekly data
        weekly_count = NutritionCRUD.aggregate_weekly_data(db, user_id, week_start)
        
        # Aggregate monthly data
        monthly_count = NutritionCRUD.aggregate_monthly_data(db, user_id, target_date.year, target_date.month)
        
        logger.info(f"📊 [SmartWorker] Created {daily_count} daily, {weekly_count} weekly, {monthly_count} monthly nutrition aggregates")

    async def _perform_lab_categorization_and_aggregation(self, db: Session):
        """Perform lab categorization and aggregation for lab reports"""
        from app.crud.lab_categorization import lab_categorization
        from app.crud.lab_aggregation import LabAggregationCRUD
        
        # Step 1: Categorize pending lab reports
        pending_reports = lab_categorization.get_pending_categorization_entries(db, limit=100)
        
        if pending_reports:
            categorized_count = lab_categorization.categorize_and_transfer_lab_reports(db, pending_reports)
            logger.debug(f"📋 [SmartWorker] Categorized {categorized_count} lab reports")
            
            # Step 2: Trigger lab aggregations for affected users and dates
            affected_users_dates = set()
            for report in pending_reports:
                affected_users_dates.add((report.user_id, report.test_date))
            
            # Aggregate lab data for each affected user/date
            for user_id, test_date in affected_users_dates:
                try:
                    # Aggregate daily lab data
                    daily_count = LabAggregationCRUD.aggregate_daily_data(db, user_id, test_date)
                    
                    # Aggregate monthly data
                    monthly_count = LabAggregationCRUD.aggregate_monthly_data(db, user_id, test_date.year, test_date.month)
                    
                    # Aggregate quarterly data
                    quarter = ((test_date.month - 1) // 3) + 1
                    quarterly_count = LabAggregationCRUD.aggregate_quarterly_data(db, user_id, test_date.year, quarter)
                    
                    # Aggregate yearly data
                    yearly_count = LabAggregationCRUD.aggregate_yearly_data(db, user_id, test_date.year)
                    
                    logger.debug(f"📊 [SmartWorker] Created {daily_count} daily, {monthly_count} monthly, {quarterly_count} quarterly, {yearly_count} yearly lab aggregates for user {user_id}")
                    
                except Exception as e:
                    logger.error(f"❌ [SmartWorker] Lab aggregation failed for user {user_id} on {test_date}: {e}")
        
        return len(pending_reports)

    def stop(self):
        """Stop the worker"""
        self.running = False
        if self.pending_timer_task and not self.pending_timer_task.done():
            self.pending_timer_task.cancel()
        logger.info("🛑 [SmartWorker] Stop requested")
    
    def force_reset(self):
        """Force reset worker state - emergency recovery"""
        self.running = False
        if self.pending_timer_task and not self.pending_timer_task.done():
            self.pending_timer_task.cancel()
        self.start_time = None
        self.total_processed = 0
        self.batches_processed = 0
        logger.info("🔄 [SmartWorker] Force reset completed")

# Global worker instance for coordination
_global_worker = SmartDelayedAggregationWorker()

# Smart delayed functions
async def trigger_smart_aggregation(user_id: int = None, delay_seconds: int = 30, domains: list = None):
    """Trigger smart delayed aggregation - waits for data chunks to stop.
    Optionally restrict to specific domains: ['vitals'|'nutrition'|'labs']
    """
    global _global_worker
    _global_worker.delay_seconds = delay_seconds
    await _global_worker.trigger_delayed_aggregation(user_id, domains)

async def process_all_pending_aggregation():
    """Process all pending aggregation data immediately (for startup)"""
    worker = SmartDelayedAggregationWorker()
    return await worker.process_all_pending_data()

async def trigger_aggregation_from_data_submission(user_id: int = None):
    """Trigger aggregation with smart delay after data submission"""
    logger.info("📱 [SmartWorker] New data arrived from iOS - triggering smart delayed aggregation")
    
    # Use different delays for initial vs incremental loads
    # Check if this looks like a bulk initial load
    db = SessionLocal()
    try:
        pending_count = len(VitalsCRUD.get_pending_aggregation_entries(db, limit=1000))
        if pending_count > 500:
            # Looks like bulk initial load - use longer delay
            delay_seconds = settings.VITALS_AGGREGATION_DELAY_BULK
            logger.info(f"🔄 [SmartWorker] Detected bulk load ({pending_count} pending) - using {delay_seconds}s delay")
        else:
            # Incremental load - use shorter delay
            delay_seconds = settings.VITALS_AGGREGATION_DELAY_INCREMENTAL
            logger.info(f"🔄 [SmartWorker] Detected incremental load ({pending_count} pending) - using {delay_seconds}s delay")
    finally:
        db.close()

    # Trigger with appropriate delay
    await trigger_smart_aggregation(user_id, delay_seconds)

# Backward compatibility
EventDrivenVitalsAggregationWorker = SmartDelayedAggregationWorker
VitalsAggregationWorker = SmartDelayedAggregationWorker

def get_worker() -> SmartDelayedAggregationWorker:
    """Get a worker instance"""
    return SmartDelayedAggregationWorker()

def reset_worker():
    """Reset worker"""
    global _global_worker
    _global_worker.force_reset()

async def start_background_worker():
    """Start smart delayed processing"""
    return await process_all_pending_aggregation()

def stop_background_worker():
    """Stop worker"""
    pass

# Separate process worker entry point
async def run_worker_process(domains: list = None):
    """Entry point for running worker as separate process - Auto-Exit when done.
    Optionally restrict to specific domains.
    """
    logger.info("🚀 [WorkerProcess] Starting background aggregation worker")
    
    # Check if there's any work to do first - check BOTH vitals and nutrition
    db = SessionLocal()
    try:
        vitals_pending = 0
        nutrition_pending = 0
        labs_pending = 0
        if domains is None or 'vitals' in (set(domains)):
            vitals_pending = len(VitalsCRUD.get_pending_aggregation_entries(db, limit=1))
        if domains is None or 'nutrition' in (set(domains)):
            nutrition_pending = len(NutritionCRUD.get_pending_aggregation_entries(db, limit=1))
        if domains is None or 'labs' in (set(domains)):
            from app.crud.lab_categorization import lab_categorization
            labs_pending = len(lab_categorization.get_pending_categorization_entries(db, limit=1))
        total_initial_pending = vitals_pending + nutrition_pending + labs_pending
        
        if total_initial_pending == 0:
            logger.info("✅ [WorkerProcess] No pending work found - exiting immediately")
            return 0
        
        # Get total counts for logging
        total_vitals_pending = 0
        total_nutrition_pending = 0
        total_labs_pending = 0
        if domains is None or 'vitals' in (set(domains)):
            total_vitals_pending = len(VitalsCRUD.get_pending_aggregation_entries(db, limit=100000))
        if domains is None or 'nutrition' in (set(domains)):
            total_nutrition_pending = len(NutritionCRUD.get_pending_aggregation_entries(db, limit=100000))
        if domains is None or 'labs' in (set(domains)):
            from app.crud.lab_categorization import lab_categorization
            total_labs_pending = len(lab_categorization.get_pending_categorization_entries(db, limit=100000))
        logger.info(f"📊 [WorkerProcess] Found {total_vitals_pending:,} vitals + {total_nutrition_pending:,} nutrition + {total_labs_pending:,} labs = {total_vitals_pending + total_nutrition_pending + total_labs_pending:,} total pending entries")
    finally:
        db.close()
    
    worker = SmartDelayedAggregationWorker(batch_size=100, allowed_domains=set(domains) if domains else None)  # Small batches for separate process
    
    try:
        # Process all pending data until queue is empty
        total_processed = await worker.process_all_pending_data()
        
        logger.info(f"🎉 [WorkerProcess] Completed! Processed {total_processed:,} entries")
        logger.info("🚪 [WorkerProcess] Auto-exiting - all work completed")
        return total_processed
        
    except KeyboardInterrupt:
        logger.info("🛑 [WorkerProcess] Shutdown requested")
        return 0
    except Exception as e:
        logger.error(f"❌ [WorkerProcess] Worker error: {e}")
        return 0
    finally:
        worker.stop()

if __name__ == "__main__":
    """Run as separate process"""
    asyncio.run(run_worker_process())