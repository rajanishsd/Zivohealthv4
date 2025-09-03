import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.crud.healthkit import HealthKitCRUD
from app.models.healthkit_data import HealthKitMetricType, HealthKitRawData
from app.schemas.healthkit import HealthKitDataSubmission
from app.utils.timezone import now_local

logger = logging.getLogger(__name__)

class HealthKitBackendManager:
    """Backend service for managing HealthKit data sync and aggregation"""
    
    def __init__(self):
        self.db = SessionLocal()
        self.sync_intervals = {
            "full_sync": timedelta(hours=6),  # Full sync every 6 hours
            "incremental_sync": timedelta(minutes=15),  # Incremental sync every 15 minutes
            "aggregation": timedelta(hours=1),  # Aggregate data every hour
        }
        self.last_sync_times = {}
    
    async def start_background_sync(self):
        """Start background sync tasks"""
        logger.info("Starting HealthKit background sync services")
        
        # Start multiple sync tasks concurrently
        tasks = [
            self.incremental_sync_loop(),
            self.aggregation_loop(),
            self.cleanup_loop()
        ]
        
        await asyncio.gather(*tasks)
    
    async def incremental_sync_loop(self):
        """Continuous incremental sync loop"""
        while True:
            try:
                await self.run_incremental_sync()
                await asyncio.sleep(self.sync_intervals["incremental_sync"].total_seconds())
            except Exception as e:
                logger.error(f"Error in incremental sync loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def aggregation_loop(self):
        """Continuous aggregation loop"""
        while True:
            try:
                await self.run_daily_aggregation()
                await asyncio.sleep(self.sync_intervals["aggregation"].total_seconds())
            except Exception as e:
                logger.error(f"Error in aggregation loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def cleanup_loop(self):
        """Daily cleanup of old data"""
        while True:
            try:
                # Run cleanup once per day at 2 AM
                now = now_local()
                next_cleanup = now.replace(hour=2, minute=0, second=0, microsecond=0)
                if next_cleanup <= now:
                    next_cleanup += timedelta(days=1)
                
                wait_seconds = (next_cleanup - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                
                await self.cleanup_old_data()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error
    
    async def run_incremental_sync(self):
        """Run incremental sync for all users"""
        logger.info("Running incremental HealthKit sync")
        
        # This would typically be called by mobile apps submitting new data
        # For now, we'll just update aggregations for recent data
        with SessionLocal() as db:
            # Get all users with recent sync activity
            recent_syncs = db.query(HealthKitRawData.user_id).filter(
                HealthKitRawData.created_at >= now_local() - timedelta(hours=1)
            ).distinct().all()
            
            for (user_id,) in recent_syncs:
                try:
                    await self.update_user_aggregations(db, user_id)
                except Exception as e:
                    logger.error(f"Error updating aggregations for user {user_id}: {e}")
    
    async def run_daily_aggregation(self):
        """Run daily aggregation for all users and metrics"""
        logger.info("Running daily HealthKit aggregation")
        
        with SessionLocal() as db:
            # Get all users with HealthKit data
            users_with_data = db.query(HealthKitRawData.user_id).distinct().all()
            
            for (user_id,) in users_with_data:
                try:
                    await self.update_user_daily_aggregates(db, user_id)
                except Exception as e:
                    logger.error(f"Error in daily aggregation for user {user_id}: {e}")
    
    async def update_user_aggregations(self, db: Session, user_id: int):
        """Update aggregations for a specific user"""
        
        # Get all metric types for this user
        metric_types = db.query(HealthKitRawData.metric_type).filter(
            HealthKitRawData.user_id == user_id
        ).distinct().all()
        
        for (metric_type,) in metric_types:
            # Update aggregations for the last 7 days
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            
            current_date = start_date
            while current_date <= end_date:
                try:
                    HealthKitCRUD.create_or_update_daily_aggregate(
                        db, user_id, metric_type, current_date
                    )
                except Exception as e:
                    logger.error(f"Error updating daily aggregate for user {user_id}, "
                               f"metric {metric_type}, date {current_date}: {e}")
                
                current_date += timedelta(days=1)
    
    async def update_user_daily_aggregates(self, db: Session, user_id: int):
        """Update daily aggregates for a specific user"""
        
        # Get all metric types for this user
        metric_types = db.query(HealthKitRawData.metric_type).filter(
            HealthKitRawData.user_id == user_id
        ).distinct().all()
        
        # Update aggregates for the last 30 days
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        for (metric_type,) in metric_types:
            current_date = start_date
            while current_date <= end_date:
                try:
                    HealthKitCRUD.create_or_update_daily_aggregate(
                        db, user_id, metric_type, current_date
                    )
                    
                    # Update weekly and monthly aggregates as needed
                    await self.update_weekly_monthly_aggregates(
                        db, user_id, metric_type, current_date
                    )
                    
                except Exception as e:
                    logger.error(f"Error updating aggregates for user {user_id}, "
                               f"metric {metric_type}, date {current_date}: {e}")
                
                current_date += timedelta(days=1)
    
    async def update_weekly_monthly_aggregates(
        self, 
        db: Session, 
        user_id: int, 
        metric_type: HealthKitMetricType, 
        target_date: date
    ):
        """Update weekly and monthly aggregates for a specific date"""
        
        # Weekly aggregates (every Sunday)
        if target_date.weekday() == 6:  # Sunday
            week_start = target_date - timedelta(days=6)  # Monday
            week_end = target_date  # Sunday
            
            try:
                await self.create_weekly_aggregate(
                    db, user_id, metric_type, week_start, week_end
                )
            except Exception as e:
                logger.error(f"Error creating weekly aggregate: {e}")
        
        # Monthly aggregates (last day of month)
        if target_date.month != (target_date + timedelta(days=1)).month:
            try:
                await self.create_monthly_aggregate(
                    db, user_id, metric_type, target_date.year, target_date.month
                )
            except Exception as e:
                logger.error(f"Error creating monthly aggregate: {e}")
    
    async def create_weekly_aggregate(
        self, 
        db: Session, 
        user_id: int, 
        metric_type: HealthKitMetricType, 
        week_start: date, 
        week_end: date
    ):
        """Create or update weekly aggregate"""
        from app.models.healthkit_data import HealthKitWeeklyAggregate, HealthKitDailyAggregate
        
        # Get daily aggregates for the week
        daily_data = db.query(HealthKitDailyAggregate).filter(
            HealthKitDailyAggregate.user_id == user_id,
            HealthKitDailyAggregate.metric_type == metric_type,
            HealthKitDailyAggregate.date >= week_start,
            HealthKitDailyAggregate.date <= week_end
        ).all()
        
        if not daily_data:
            return
        
        # Calculate weekly aggregations
        total_values = [d.total_value for d in daily_data if d.total_value is not None]
        avg_values = [d.average_value for d in daily_data if d.average_value is not None]
        min_values = [d.min_value for d in daily_data if d.min_value is not None]
        max_values = [d.max_value for d in daily_data if d.max_value is not None]
        durations = [d.duration_minutes for d in daily_data if d.duration_minutes is not None]
        
        # Check if weekly aggregate already exists
        existing = db.query(HealthKitWeeklyAggregate).filter(
            HealthKitWeeklyAggregate.user_id == user_id,
            HealthKitWeeklyAggregate.metric_type == metric_type,
            HealthKitWeeklyAggregate.week_start_date == week_start
        ).first()
        
        if existing:
            # Update existing
            existing.total_value = sum(total_values) if total_values else None
            existing.average_value = sum(avg_values) / len(avg_values) if avg_values else None
            existing.min_value = min(min_values) if min_values else None
            existing.max_value = max(max_values) if max_values else None
            existing.days_with_data = len(daily_data)
            existing.total_duration_minutes = sum(durations) if durations else None
            existing.updated_at = now_local()
        else:
            # Create new
            weekly_aggregate = HealthKitWeeklyAggregate(
                user_id=user_id,
                metric_type=metric_type,
                week_start_date=week_start,
                week_end_date=week_end,
                total_value=sum(total_values) if total_values else None,
                average_value=sum(avg_values) / len(avg_values) if avg_values else None,
                min_value=min(min_values) if min_values else None,
                max_value=max(max_values) if max_values else None,
                days_with_data=len(daily_data),
                total_duration_minutes=sum(durations) if durations else None,
                unit=daily_data[0].unit
            )
            db.add(weekly_aggregate)
        
        db.commit()
    
    async def create_monthly_aggregate(
        self, 
        db: Session, 
        user_id: int, 
        metric_type: HealthKitMetricType, 
        year: int, 
        month: int
    ):
        """Create or update monthly aggregate"""
        from app.models.healthkit_data import HealthKitMonthlyAggregate, HealthKitDailyAggregate
        
        # Get daily aggregates for the month
        daily_data = db.query(HealthKitDailyAggregate).filter(
            HealthKitDailyAggregate.user_id == user_id,
            HealthKitDailyAggregate.metric_type == metric_type,
            db.extract('year', HealthKitDailyAggregate.date) == year,
            db.extract('month', HealthKitDailyAggregate.date) == month
        ).all()
        
        if not daily_data:
            return
        
        # Calculate monthly aggregations (similar to weekly)
        total_values = [d.total_value for d in daily_data if d.total_value is not None]
        avg_values = [d.average_value for d in daily_data if d.average_value is not None]
        min_values = [d.min_value for d in daily_data if d.min_value is not None]
        max_values = [d.max_value for d in daily_data if d.max_value is not None]
        durations = [d.duration_minutes for d in daily_data if d.duration_minutes is not None]
        
        # Check if monthly aggregate already exists
        existing = db.query(HealthKitMonthlyAggregate).filter(
            HealthKitMonthlyAggregate.user_id == user_id,
            HealthKitMonthlyAggregate.metric_type == metric_type,
            HealthKitMonthlyAggregate.year == year,
            HealthKitMonthlyAggregate.month == month
        ).first()
        
        if existing:
            # Update existing
            existing.total_value = sum(total_values) if total_values else None
            existing.average_value = sum(avg_values) / len(avg_values) if avg_values else None
            existing.min_value = min(min_values) if min_values else None
            existing.max_value = max(max_values) if max_values else None
            existing.days_with_data = len(daily_data)
            existing.total_duration_minutes = sum(durations) if durations else None
            existing.updated_at = now_local()
        else:
            # Create new
            monthly_aggregate = HealthKitMonthlyAggregate(
                user_id=user_id,
                metric_type=metric_type,
                year=year,
                month=month,
                total_value=sum(total_values) if total_values else None,
                average_value=sum(avg_values) / len(avg_values) if avg_values else None,
                min_value=min(min_values) if min_values else None,
                max_value=max(max_values) if max_values else None,
                days_with_data=len(daily_data),
                total_duration_minutes=sum(durations) if durations else None,
                unit=daily_data[0].unit
            )
            db.add(monthly_aggregate)
        
        db.commit()
    
    async def cleanup_old_data(self):
        """Clean up old raw data and maintain data retention policy"""
        logger.info("Running HealthKit data cleanup")
        
        with SessionLocal() as db:
            # Delete raw data older than 90 days
            cutoff_date = now_local() - timedelta(days=90)
            
            deleted_count = db.query(HealthKitRawData).filter(
                HealthKitRawData.created_at < cutoff_date
            ).delete()
            
            db.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old HealthKit raw data records")
    
    def close(self):
        """Close database connection"""
        self.db.close()

# Global instance
healthkit_manager = HealthKitBackendManager()

# Startup function for FastAPI
async def start_healthkit_background_service():
    """Start the HealthKit background service"""
    logger.info("Starting HealthKit background service")
    await healthkit_manager.start_background_sync()

# Shutdown function for FastAPI
async def stop_healthkit_background_service():
    """Stop the HealthKit background service"""
    logger.info("Stopping HealthKit background service")
    healthkit_manager.close() 