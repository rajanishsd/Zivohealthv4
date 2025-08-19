from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from app.models.healthkit_data import (
    HealthKitRawData, 
    HealthKitDailyAggregate, 
    HealthKitWeeklyAggregate, 
    HealthKitMonthlyAggregate, 
    HealthKitSyncStatus,
    HealthKitMetricType
)
from app.schemas.healthkit import HealthKitDataSubmission, TimeGranularity
import calendar

class HealthKitCRUD:
    
    @staticmethod
    def create_raw_data(db: Session, user_id: int, data: HealthKitDataSubmission) -> HealthKitRawData:
        """Create a new raw HealthKit data entry"""
        db_data = HealthKitRawData(
            user_id=user_id,
            metric_type=data.metric_type,
            value=data.value,
            unit=data.unit,
            start_date=data.start_date,
            end_date=data.end_date,
            notes=data.notes,
            source_device=data.source_device
        )
        db.add(db_data)
        db.commit()
        db.refresh(db_data)
        return db_data
    
    @staticmethod
    def bulk_create_raw_data(db: Session, user_id: int, data_list: List[HealthKitDataSubmission]) -> List[HealthKitRawData]:
        """Bulk create raw HealthKit data entries"""
        db_entries = []
        for data in data_list:
            db_data = HealthKitRawData(
                user_id=user_id,
                metric_type=data.metric_type,
                value=data.value,
                unit=data.unit,
                start_date=data.start_date,
                end_date=data.end_date,
                notes=data.notes,
                source_device=data.source_device
            )
            db_entries.append(db_data)
        
        db.add_all(db_entries)
        db.commit()
        for entry in db_entries:
            db.refresh(entry)
        return db_entries
    
    @staticmethod
    def get_raw_data(
        db: Session, 
        user_id: int, 
        metric_type: Optional[HealthKitMetricType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[HealthKitRawData]:
        """Get raw HealthKit data with filters"""
        query = db.query(HealthKitRawData).filter(HealthKitRawData.user_id == user_id)
        
        if metric_type:
            query = query.filter(HealthKitRawData.metric_type == metric_type)
        
        if start_date:
            query = query.filter(HealthKitRawData.start_date >= start_date)
        
        if end_date:
            query = query.filter(HealthKitRawData.end_date <= end_date)
        
        return query.order_by(desc(HealthKitRawData.start_date)).limit(limit).all()
    
    @staticmethod
    def get_daily_aggregates(
        db: Session, 
        user_id: int, 
        metric_type: HealthKitMetricType,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[HealthKitDailyAggregate]:
        """Get daily aggregated data"""
        query = db.query(HealthKitDailyAggregate).filter(
            and_(
                HealthKitDailyAggregate.user_id == user_id,
                HealthKitDailyAggregate.metric_type == metric_type
            )
        )
        
        if start_date:
            query = query.filter(HealthKitDailyAggregate.date >= start_date)
        
        if end_date:
            query = query.filter(HealthKitDailyAggregate.date <= end_date)
        
        return query.order_by(asc(HealthKitDailyAggregate.date)).all()
    
    @staticmethod
    def get_weekly_aggregates(
        db: Session, 
        user_id: int, 
        metric_type: HealthKitMetricType,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[HealthKitWeeklyAggregate]:
        """Get weekly aggregated data"""
        query = db.query(HealthKitWeeklyAggregate).filter(
            and_(
                HealthKitWeeklyAggregate.user_id == user_id,
                HealthKitWeeklyAggregate.metric_type == metric_type
            )
        )
        
        if start_date:
            query = query.filter(HealthKitWeeklyAggregate.week_start_date >= start_date)
        
        if end_date:
            query = query.filter(HealthKitWeeklyAggregate.week_end_date <= end_date)
        
        return query.order_by(asc(HealthKitWeeklyAggregate.week_start_date)).all()
    
    @staticmethod
    def get_monthly_aggregates(
        db: Session, 
        user_id: int, 
        metric_type: HealthKitMetricType,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> List[HealthKitMonthlyAggregate]:
        """Get monthly aggregated data"""
        query = db.query(HealthKitMonthlyAggregate).filter(
            and_(
                HealthKitMonthlyAggregate.user_id == user_id,
                HealthKitMonthlyAggregate.metric_type == metric_type
            )
        )
        
        if start_year:
            query = query.filter(HealthKitMonthlyAggregate.year >= start_year)
        
        if end_year:
            query = query.filter(HealthKitMonthlyAggregate.year <= end_year)
        
        return query.order_by(asc(HealthKitMonthlyAggregate.year), asc(HealthKitMonthlyAggregate.month)).all()
    
    @staticmethod
    def create_or_update_daily_aggregate(
        db: Session, 
        user_id: int, 
        metric_type: HealthKitMetricType, 
        target_date: date
    ) -> HealthKitDailyAggregate:
        """Create or update daily aggregate for a specific date"""
        
        # Get all raw data for this date
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        raw_data = db.query(HealthKitRawData).filter(
            and_(
                HealthKitRawData.user_id == user_id,
                HealthKitRawData.metric_type == metric_type,
                HealthKitRawData.start_date >= start_datetime,
                HealthKitRawData.start_date <= end_datetime
            )
        ).all()
        
        if not raw_data:
            return None
        
        # Calculate aggregations
        values = [d.value for d in raw_data]
        total_value = sum(values)
        average_value = total_value / len(values)
        min_value = min(values)
        max_value = max(values)
        count = len(values)
        
        # Calculate duration for time-based metrics
        duration_minutes = None
        if metric_type in [HealthKitMetricType.WORKOUTS, HealthKitMetricType.WORKOUT_DURATION, HealthKitMetricType.SLEEP]:
            duration_minutes = sum([(d.end_date - d.start_date).total_seconds() / 60 for d in raw_data])
        
        # Get unit from first data point
        unit = raw_data[0].unit
        
        # Create summary notes
        notes = None
        if metric_type == HealthKitMetricType.WORKOUTS:
            # Group workouts by type and calculate detailed metrics for each type
            workout_breakdown = {}
            total_calories = 0
            total_distance = 0
            
            for d in raw_data:
                # Parse workout details from notes (JSON format from frontend)
                import json
                try:
                    workout_details = json.loads(d.notes) if d.notes else {}
                    workout_type = workout_details.get("type", "Unknown")
                    duration_minutes = workout_details.get("duration", d.value)
                    calories = workout_details.get("calories", 0)
                    distance = workout_details.get("distance", 0)
                except (json.JSONDecodeError, AttributeError):
                    # Fallback for old format (just workout type)
                    workout_type = d.notes or "Unknown"
                    duration_minutes = d.value
                    calories = 0
                    distance = 0
                
                # Aggregate by workout type
                if workout_type in workout_breakdown:
                    workout_breakdown[workout_type]["duration"] += duration_minutes
                    workout_breakdown[workout_type]["calories"] += calories
                    workout_breakdown[workout_type]["distance"] += distance
                    workout_breakdown[workout_type]["count"] += 1
                else:
                    workout_breakdown[workout_type] = {
                        "duration": duration_minutes,
                        "calories": calories,
                        "distance": distance,
                        "count": 1
                    }
                
                total_calories += calories
                total_distance += distance
            
            # Store enhanced breakdown as JSON string in notes
            enhanced_breakdown = {
                "workouts": workout_breakdown,
                "totals": {
                    "calories": total_calories,
                    "distance": total_distance,
                    "duration": sum(d.value for d in raw_data)
                }
            }
            notes = json.dumps(enhanced_breakdown)
        elif metric_type in [HealthKitMetricType.WORKOUT_DURATION, HealthKitMetricType.WORKOUT_CALORIES, HealthKitMetricType.WORKOUT_DISTANCE]:
            # For individual workout components, collect workout types
            workout_types = [d.notes for d in raw_data if d.notes]
            if workout_types:
                unique_types = list(set(workout_types))
                notes = f"Workout types: {', '.join(unique_types)}"
        elif metric_type == HealthKitMetricType.SLEEP:
            sleep_stages = [d.notes for d in raw_data if d.notes]
            if sleep_stages:
                notes = f"Sleep stages: {', '.join(set(sleep_stages))}"
        
        # Check if aggregate already exists
        existing = db.query(HealthKitDailyAggregate).filter(
            and_(
                HealthKitDailyAggregate.user_id == user_id,
                HealthKitDailyAggregate.metric_type == metric_type,
                HealthKitDailyAggregate.date == target_date
            )
        ).first()
        
        if existing:
            # Update existing
            existing.total_value = total_value
            existing.average_value = average_value
            existing.min_value = min_value
            existing.max_value = max_value
            existing.count = count
            existing.duration_minutes = duration_minutes
            existing.unit = unit
            existing.notes = notes
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            # Create new
            new_aggregate = HealthKitDailyAggregate(
                user_id=user_id,
                metric_type=metric_type,
                date=target_date,
                total_value=total_value,
                average_value=average_value,
                min_value=min_value,
                max_value=max_value,
                count=count,
                duration_minutes=duration_minutes,
                unit=unit,
                notes=notes
            )
            db.add(new_aggregate)
            db.commit()
            db.refresh(new_aggregate)
            return new_aggregate
    
    @staticmethod
    def get_latest_data_by_metric(db: Session, user_id: int) -> Dict[HealthKitMetricType, HealthKitRawData]:
        """Get the latest data point for each metric type"""
        latest_data = {}
        
        for metric_type in HealthKitMetricType:
            latest = db.query(HealthKitRawData).filter(
                and_(
                    HealthKitRawData.user_id == user_id,
                    HealthKitRawData.metric_type == metric_type
                )
            ).order_by(desc(HealthKitRawData.start_date)).first()
            
            if latest:
                latest_data[metric_type] = latest
        
        return latest_data
    
    @staticmethod
    def get_or_create_sync_status(db: Session, user_id: int) -> HealthKitSyncStatus:
        """Get or create sync status for user"""
        sync_status = db.query(HealthKitSyncStatus).filter(
            HealthKitSyncStatus.user_id == user_id
        ).first()
        
        if not sync_status:
            sync_status = HealthKitSyncStatus(user_id=user_id)
            db.add(sync_status)
            db.commit()
            db.refresh(sync_status)
        
        return sync_status
    
    @staticmethod
    def update_sync_status(
        db: Session, 
        user_id: int, 
        metric_type: Optional[HealthKitMetricType] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> HealthKitSyncStatus:
        """Update sync status after sync operation"""
        sync_status = HealthKitCRUD.get_or_create_sync_status(db, user_id)
        
        now = datetime.utcnow()
        sync_status.last_sync_date = now
        
        if success:
            sync_status.last_successful_sync = now
            sync_status.error_count = 0
            sync_status.last_error = None
            
            # Update specific metric sync time
            if metric_type:
                metric_field_map = {
                    HealthKitMetricType.HEART_RATE: "heart_rate_last_sync",
                    HealthKitMetricType.BLOOD_PRESSURE_SYSTOLIC: "blood_pressure_last_sync",
                    HealthKitMetricType.BLOOD_PRESSURE_DIASTOLIC: "blood_pressure_last_sync",
                    HealthKitMetricType.BLOOD_SUGAR: "blood_sugar_last_sync",
                    HealthKitMetricType.BODY_TEMPERATURE: "temperature_last_sync",
                    HealthKitMetricType.BODY_MASS: "weight_last_sync",
                    HealthKitMetricType.STEP_COUNT: "steps_last_sync",
                    HealthKitMetricType.STAND_TIME: "stand_time_last_sync",
                    HealthKitMetricType.ACTIVE_ENERGY: "active_energy_last_sync",
                    HealthKitMetricType.FLIGHTS_CLIMBED: "flights_climbed_last_sync",
                    HealthKitMetricType.WORKOUTS: "workouts_last_sync",
                    HealthKitMetricType.WORKOUT_DURATION: "workouts_last_sync",
                    HealthKitMetricType.WORKOUT_CALORIES: "workouts_last_sync", 
                    HealthKitMetricType.WORKOUT_DISTANCE: "workouts_last_sync",
                    HealthKitMetricType.SLEEP: "sleep_last_sync",
                }
                
                field_name = metric_field_map.get(metric_type)
                if field_name and hasattr(sync_status, field_name):
                    setattr(sync_status, field_name, now)
        else:
            sync_status.error_count += 1
            sync_status.last_error = error_message
        
        db.commit()
        db.refresh(sync_status)
        return sync_status
    
    @staticmethod
    def get_metrics_for_period(
        db: Session, 
        user_id: int, 
        metric_types: List[HealthKitMetricType],
        start_date: date,
        end_date: date,
        granularity: TimeGranularity = TimeGranularity.DAILY
    ) -> Dict[HealthKitMetricType, List[Any]]:
        """Get metrics data for a specific period with specified granularity"""
        results = {}
        
        for metric_type in metric_types:
            if granularity == TimeGranularity.DAILY:
                data = HealthKitCRUD.get_daily_aggregates(db, user_id, metric_type, start_date, end_date)
            elif granularity == TimeGranularity.WEEKLY:
                data = HealthKitCRUD.get_weekly_aggregates(db, user_id, metric_type, start_date, end_date)
            elif granularity == TimeGranularity.MONTHLY:
                data = HealthKitCRUD.get_monthly_aggregates(db, user_id, metric_type, start_date.year, end_date.year)
            else:
                data = []
            
            results[metric_type] = data
        
        return results 