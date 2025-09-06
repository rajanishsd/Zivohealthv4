from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc, text
from sqlalchemy.exc import IntegrityError
from app.models.vitals_data import (
    VitalsRawData, 
    VitalsHourlyAggregate, 
    VitalsDailyAggregate, 
    VitalsWeeklyAggregate, 
    VitalsMonthlyAggregate, 
    VitalsSyncStatus,
    VitalMetricType,
    VitalDataSource,
    TimeGranularity,
    VitalsRawCategorized
)
from app.schemas.vitals import VitalDataSubmission
from app.utils.timezone import now_local, to_local_naive
import calendar
import json
import logging

logger = logging.getLogger(__name__)

class VitalsCRUD:
    
    @staticmethod
    def create_raw_data(db: Session, user_id: int, data: VitalDataSubmission) -> VitalsRawData:
        """Create a new raw vitals data entry"""
        db_data = VitalsRawData(
            user_id=user_id,
            metric_type=data.metric_type,
            value=data.value,
            unit=data.unit,
            start_date=to_local_naive(data.start_date),
            end_date=to_local_naive(data.end_date),
            data_source=data.data_source,
            notes=data.notes,
            source_device=data.source_device,
            confidence_score=data.confidence_score
        )
        db.add(db_data)
        db.commit()
        db.refresh(db_data)
        return db_data
    
    @staticmethod
    def bulk_create_raw_data(db: Session, user_id: int, data_list: List[VitalDataSubmission]) -> List[VitalsRawData]:
        """Bulk create raw vitals data entries with duplicate handling"""
        from sqlalchemy.dialects.postgresql import insert

        # Prepare data for bulk insert
        insert_data = []
        for data in data_list:
            insert_data.append({
                'user_id': user_id,
                'metric_type': data.metric_type,
                'value': data.value,
                'unit': data.unit,
                'start_date': to_local_naive(data.start_date),
                'end_date': to_local_naive(data.end_date),
                'data_source': data.data_source,
                'notes': data.notes,
                'source_device': data.source_device,
                'confidence_score': data.confidence_score,
                'aggregation_status': 'pending'
            })

        try:
            # Use PostgreSQL's INSERT ... ON CONFLICT DO NOTHING to handle duplicates
            stmt = insert(VitalsRawData).values(insert_data)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=['user_id', 'metric_type', 'unit', 'start_date', 'data_source', 
                   text("COALESCE(notes, '')")]
            )

            # Execute the upsert
            result = db.execute(stmt)
            db.commit()

            # Get the inserted records (this won't include duplicates that were ignored)
            inserted_count = result.rowcount
            logger.info(f"✅ [VitalsCRUD] Inserted {inserted_count} new records out of {len(data_list)} submitted (duplicates ignored)")

            # Return empty list since we can't easily get the inserted records with ON CONFLICT DO NOTHING
            # The caller should use the count from the response instead
            return []

        except IntegrityError as e:
            db.rollback()
            logger.error(f"❌ [VitalsCRUD] Integrity error during bulk insert: {str(e)}")
            # Fallback: insert one by one and skip duplicates
            return VitalsCRUD._fallback_individual_insert(db, user_id, data_list)
        except Exception as e:
            db.rollback()
            logger.error(f"❌ [VitalsCRUD] Unexpected error during bulk insert: {str(e)}")
            raise
    
    @staticmethod
    def _fallback_individual_insert(db: Session, user_id: int, data_list: List[VitalDataSubmission]) -> List[VitalsRawData]:
        """Fallback method to insert records one by one, skipping duplicates"""
        inserted_records = []
        skipped_count = 0

        for data in data_list:
            try:
                db_data = VitalsRawData(
                    user_id=user_id,
                    metric_type=data.metric_type,
                    value=data.value,
                    unit=data.unit,
                    start_date=to_local_naive(data.start_date),
                    end_date=to_local_naive(data.end_date),
                    data_source=data.data_source,
                    notes=data.notes,
                    source_device=data.source_device,
                    confidence_score=data.confidence_score,
                        aggregation_status='pending'
                )
            
                db.add(db_data)
                db.commit()
                db.refresh(db_data)
                inserted_records.append(db_data)

            except IntegrityError:
                db.rollback()
                skipped_count += 1
                logger.debug(f"Skipped duplicate record: {data.metric_type} at {data.start_date}")
                continue
            except Exception as e:
                db.rollback()
                logger.error(f"Error inserting individual record: {str(e)}")
                continue

        logger.info(f"✅ [VitalsCRUD] Fallback insert completed: {len(inserted_records)} inserted, {skipped_count} duplicates skipped")
        return inserted_records
    
    @staticmethod
    def get_raw_data(
        db: Session,
        user_id: int,
        metric_types: Optional[List[VitalMetricType]] = None,
        data_sources: Optional[List[VitalDataSource]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[VitalsRawData]:
        """Get raw vitals data with filters"""
        query = db.query(VitalsRawData).filter(VitalsRawData.user_id == user_id)
        
        if metric_types:
            query = query.filter(VitalsRawData.metric_type.in_(metric_types))
        
        if data_sources:
            query = query.filter(VitalsRawData.data_source.in_(data_sources))
            
        if start_date:
            query = query.filter(VitalsRawData.start_date >= start_date)
            
        if end_date:
            query = query.filter(VitalsRawData.end_date <= end_date)
        
        return query.order_by(desc(VitalsRawData.start_date)).limit(limit).all()
    
    @staticmethod
    def get_latest_value(
        db: Session,
        user_id: int,
        metric_type: VitalMetricType,
        data_source: Optional[VitalDataSource] = None
    ) -> Optional[VitalsRawData]:
        """Get the latest value for a specific metric"""
        query = db.query(VitalsRawData).filter(
            and_(
                VitalsRawData.user_id == user_id,
                VitalsRawData.metric_type == metric_type
            )
        )
        
        if data_source:
            query = query.filter(VitalsRawData.data_source == data_source)
        
        return query.order_by(desc(VitalsRawData.start_date)).first()
    
    @staticmethod
    def _aggregate_sleep_data(categorized_entries: List[VitalsRawCategorized]) -> Dict[str, Any]:
        """
        Specialized sleep aggregation that handles:
        1. Unit normalization (convert all to hours)
        2. Sleep stage filtering (exclude awake periods)
        3. Deduplication of overlapping periods
        """
        if not categorized_entries:
            return {"total_hours": 0, "average_hours": 0, "count": 0, "min_hours": 0, "max_hours": 0}
        
        # Step 1: Normalize units and filter valid sleep periods
        normalized_periods = []
        for entry in categorized_entries:
            # Skip awake periods - only count actual sleep
            if entry.notes and 'awake' in entry.notes.lower():
                continue
                
            # Normalize value to hours
            value_hours = entry.value
            if entry.unit == 'minutes':
                value_hours = entry.value / 60.0
            elif entry.unit == 'seconds':
                value_hours = entry.value / 3600.0
            # If unit is already 'hours', keep as is
            
            # Only include reasonable sleep durations (0.1 to 16 hours)
            if 0.1 <= value_hours <= 16.0:
                normalized_periods.append({
                    'start': entry.start_date,
                    'end': entry.end_date,
                    'duration_hours': value_hours,
                    'notes': entry.notes or ''
                })
        
        if not normalized_periods:
            return {"total_hours": 0, "average_hours": 0, "count": 0, "min_hours": 0, "max_hours": 0}
        
        # Step 2: Remove overlapping periods (keep the longest one for each overlap)
        # Sort by start time
        normalized_periods.sort(key=lambda x: x['start'])
        
        deduplicated_periods = []
        for period in normalized_periods:
            # Check if this period overlaps with any existing period
            overlaps = False
            for i, existing in enumerate(deduplicated_periods):
                if (period['start'] < existing['end'] and period['end'] > existing['start']):
                    # Overlapping - keep the one with longer duration
                    if period['duration_hours'] > existing['duration_hours']:
                        deduplicated_periods[i] = period
                    overlaps = True
                    break
            
            if not overlaps:
                deduplicated_periods.append(period)
        
        # Step 3: Calculate final aggregates
        durations = [p['duration_hours'] for p in deduplicated_periods]
        
        return {
            "total_hours": sum(durations),
            "average_hours": sum(durations) / len(durations),
            "count": len(durations),
            "min_hours": min(durations),
            "max_hours": max(durations)
        }
    
    @staticmethod
    def aggregate_hourly_data(db: Session, user_id: int, target_date: date) -> int:
        """Aggregate categorized data into hourly aggregates for a specific date (optimized)"""
        aggregated_count = 0
        
        # Get all categorized data for the target date in one query
        categorized_data_query = db.query(VitalsRawCategorized).filter(
            and_(
                VitalsRawCategorized.user_id == user_id,
                func.date(VitalsRawCategorized.start_date) == target_date
            )
        ).all()
        
        if not categorized_data_query:
            return 0
        
        # Group data by metric type and hour
        hourly_groups = {}
        for entry in categorized_data_query:
            hour_start = to_local_naive(entry.start_date).replace(minute=0, second=0, microsecond=0)
            key = (entry.metric_type, hour_start)
            
            if key not in hourly_groups:
                hourly_groups[key] = []
            hourly_groups[key].append(entry)
        
        # Get existing hourly aggregates for this date in one query
        existing_aggregates = {}
        if hourly_groups:
            existing_query = db.query(VitalsHourlyAggregate).filter(
                    and_(
                    VitalsHourlyAggregate.user_id == user_id,
                    func.date(VitalsHourlyAggregate.hour_start) == target_date
                    )
                ).all()
                
            for agg in existing_query:
                key = (agg.metric_type, agg.hour_start)
                existing_aggregates[key] = agg
        
        # Process each hourly group
        new_aggregates = []
        for (metric_type, hour_start), categorized_entries in hourly_groups.items():
            sources = list(set([r.data_source for r in categorized_entries]))
            latest_entry = max(categorized_entries, key=lambda x: to_local_naive(x.start_date))
            
            # Get LOINC code from the latest entry (all entries in group should have same LOINC code)
            loinc_code = latest_entry.loinc_code
            
            # Special handling for sleep data
            if metric_type == VitalMetricType.SLEEP:
                sleep_stats = VitalsCRUD._aggregate_sleep_data(categorized_entries)
                total_value = sleep_stats["total_hours"]
                average_value = sleep_stats["average_hours"] 
                min_value = sleep_stats["min_hours"]
                max_value = sleep_stats["max_hours"]
                count = sleep_stats["count"]
                unit = "hours"  # Standardize sleep unit to hours
            else:
                # Standard aggregation for other metrics
                values = [r.value for r in categorized_entries]
                total_value = sum(values) if metric_type in [VitalMetricType.STEP_COUNT, VitalMetricType.ACTIVE_ENERGY, VitalMetricType.WORKOUT_DURATION, VitalMetricType.WORKOUT_CALORIES, VitalMetricType.WORKOUT_DISTANCE] else None
                average_value = sum(values) / len(values)
                min_value = min(values)
                max_value = max(values)
                count = len(values)
                unit = latest_entry.unit
            
            key = (metric_type, hour_start)
            if key in existing_aggregates:
                # Update existing aggregate
                existing = existing_aggregates[key]
                existing.total_value = total_value
                existing.average_value = average_value
                existing.min_value = min_value
                existing.max_value = max_value
                existing.count = count
                existing.unit = unit
                existing.loinc_code = loinc_code  # Copy LOINC code
                existing.primary_source = latest_entry.data_source
                existing.sources_included = json.dumps([str(s) for s in sources])
                existing.updated_at = datetime.utcnow()
            else:
                # Create new aggregate
                aggregate = VitalsHourlyAggregate(
                    user_id=user_id,
                    metric_type=metric_type,
                    loinc_code=loinc_code,  # Copy LOINC code
                    hour_start=hour_start,
                    total_value=total_value,
                    average_value=average_value,
                    min_value=min_value,
                    max_value=max_value,
                    count=count,
                    unit=unit,
                    primary_source=latest_entry.data_source,
                    sources_included=json.dumps([str(s) for s in sources])
                )
                new_aggregates.append(aggregate)
                aggregated_count += 1
        
        # Bulk add new aggregates using upsert to handle duplicates
        if new_aggregates:
            try:
                db.add_all(new_aggregates)
                db.commit()
            except Exception as e:
                db.rollback()
                # If bulk insert fails due to duplicates, insert one by one with upsert
                for aggregate in new_aggregates:
                    existing = db.query(VitalsHourlyAggregate).filter(
                        and_(
                            VitalsHourlyAggregate.user_id == aggregate.user_id,
                            VitalsHourlyAggregate.metric_type == aggregate.metric_type,
                            VitalsHourlyAggregate.hour_start == aggregate.hour_start,
                            VitalsHourlyAggregate.primary_source == aggregate.primary_source
                        )
                    ).first()
                    
                    if not existing:
                        db.add(aggregate)
                        aggregated_count += 1
                db.commit()
        else:
            db.commit()
        
        return aggregated_count
    
    @staticmethod
    def aggregate_daily_data(db: Session, user_id: int, target_date: date) -> int:
        """Aggregate hourly data into daily aggregates"""
        aggregated_count = 0
        
        # Get all metric types for the user on this date
        metric_types = db.query(VitalsHourlyAggregate.metric_type).filter(
            and_(
                VitalsHourlyAggregate.user_id == user_id,
                func.date(VitalsHourlyAggregate.hour_start) == target_date
            )
        ).distinct().all()
        
        for (metric_type,) in metric_types:
            # Get hourly data for this date
            hourly_data = db.query(VitalsHourlyAggregate).filter(
                and_(
                    VitalsHourlyAggregate.user_id == user_id,
                    VitalsHourlyAggregate.metric_type == metric_type,
                    func.date(VitalsHourlyAggregate.hour_start) == target_date
                )
            ).all()
            
            if not hourly_data:
                continue
            
            # Calculate daily aggregates with special handling for sleep
            if metric_type == VitalMetricType.SLEEP:
                # For sleep, sum the total hours and calculate proper daily metrics
                total_values = [h.total_value for h in hourly_data if h.total_value is not None]
                avg_values = [h.average_value for h in hourly_data if h.average_value is not None]
                min_values = [h.min_value for h in hourly_data if h.min_value is not None]
                max_values = [h.max_value for h in hourly_data if h.max_value is not None]
                
                # For sleep: total is sum of all sleep periods, average is total/1 (since it's daily total)
                daily_total = sum(total_values) if total_values else 0
                daily_average = daily_total  # Daily total sleep
                daily_min = min(min_values) if min_values else 0
                daily_max = max(max_values) if max_values else 0
            else:
                # Standard aggregation for other metrics
                total_values = [h.total_value for h in hourly_data if h.total_value is not None]
                avg_values = [h.average_value for h in hourly_data if h.average_value is not None]
                min_values = [h.min_value for h in hourly_data if h.min_value is not None]
                max_values = [h.max_value for h in hourly_data if h.max_value is not None]
                    
                daily_total = sum(total_values) if total_values else None
                daily_average = sum(avg_values) / len(avg_values) if avg_values else None
                daily_min = min(min_values) if min_values else None
                daily_max = max(max_values) if max_values else None
            
            sources = set()
            for h in hourly_data:
                if h.sources_included:
                    try:
                        sources.update(json.loads(h.sources_included))
                    except (json.JSONDecodeError, TypeError):
                        pass
            
            latest_entry = max(hourly_data, key=lambda x: to_local_naive(x.hour_start))
            
            # Check if daily aggregate already exists
            existing = db.query(VitalsDailyAggregate).filter(
                and_(
                    VitalsDailyAggregate.user_id == user_id,
                    VitalsDailyAggregate.metric_type == metric_type,
                    VitalsDailyAggregate.date == target_date
                )
            ).first()
            
            # Get LOINC code from the latest hourly entry (all entries should have same LOINC code)
            loinc_code = latest_entry.loinc_code
            
            if existing:
                # Update existing aggregate
                existing.total_value = daily_total
                existing.average_value = daily_average
                existing.min_value = daily_min
                existing.max_value = daily_max
                existing.count = sum([h.count for h in hourly_data])
                existing.unit = "hours" if metric_type == VitalMetricType.SLEEP else latest_entry.unit
                existing.loinc_code = loinc_code  # Copy LOINC code
                existing.primary_source = latest_entry.primary_source
                existing.sources_included = json.dumps(list(sources))
                existing.updated_at = datetime.utcnow()
            else:
                # Create new daily aggregate
                aggregate = VitalsDailyAggregate(
                    user_id=user_id,
                    metric_type=metric_type,
                    loinc_code=loinc_code,  # Copy LOINC code
                    date=target_date,
                    total_value=daily_total,
                    average_value=daily_average,
                    min_value=daily_min,
                    max_value=daily_max,
                    count=sum([h.count for h in hourly_data]),
                    unit="hours" if metric_type == VitalMetricType.SLEEP else latest_entry.unit,
                    primary_source=latest_entry.primary_source,
                    sources_included=json.dumps(list(sources))
                )
                db.add(aggregate)
                aggregated_count += 1
        
        db.commit()
        return aggregated_count
    
    @staticmethod
    def get_daily_aggregates(
        db: Session,
        user_id: int,
        metric_type: VitalMetricType,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[VitalsDailyAggregate]:
        """Get daily aggregated data"""
        query = db.query(VitalsDailyAggregate).filter(
            and_(
                VitalsDailyAggregate.user_id == user_id,
                VitalsDailyAggregate.metric_type == metric_type
            )
        )
        
        if start_date:
            query = query.filter(VitalsDailyAggregate.date >= start_date)
        
        if end_date:
            query = query.filter(VitalsDailyAggregate.date <= end_date)
        
        return query.order_by(asc(VitalsDailyAggregate.date)).all()

    @staticmethod
    def get_weekly_aggregates(
        db: Session,
        user_id: int,
        metric_type: VitalMetricType,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[VitalsWeeklyAggregate]:
        """Get weekly aggregated data"""
        query = db.query(VitalsWeeklyAggregate).filter(
            and_(
                VitalsWeeklyAggregate.user_id == user_id,
                VitalsWeeklyAggregate.metric_type == metric_type
            )
        )
        
        if start_date:
            query = query.filter(VitalsWeeklyAggregate.week_start_date >= start_date)
        
        if end_date:
            query = query.filter(VitalsWeeklyAggregate.week_end_date <= end_date)
        
        return query.order_by(asc(VitalsWeeklyAggregate.week_start_date)).all()

    @staticmethod
    def get_monthly_aggregates(
        db: Session,
        user_id: int,
        metric_type: VitalMetricType,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> List[VitalsMonthlyAggregate]:
        """Get monthly aggregated data"""
        query = db.query(VitalsMonthlyAggregate).filter(
            and_(
                VitalsMonthlyAggregate.user_id == user_id,
                VitalsMonthlyAggregate.metric_type == metric_type
            )
        )
        
        if start_year:
            query = query.filter(VitalsMonthlyAggregate.year >= start_year)
        
        if end_year:
            query = query.filter(VitalsMonthlyAggregate.year <= end_year)
        
        return query.order_by(asc(VitalsMonthlyAggregate.year), asc(VitalsMonthlyAggregate.month)).all()
    
    @staticmethod
    def get_sync_status(db: Session, user_id: int, data_source: VitalDataSource) -> Optional[VitalsSyncStatus]:
        """Get sync status for a user and data source"""
        return db.query(VitalsSyncStatus).filter(
            and_(
                VitalsSyncStatus.user_id == user_id,
                VitalsSyncStatus.data_source == data_source
            )
        ).first()
    
    @staticmethod
    def update_sync_status(
        db: Session,
        user_id: int,
        data_source: VitalDataSource,
        last_sync_date: Optional[datetime] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> VitalsSyncStatus:
        """Update sync status for a user and data source"""
        sync_status = VitalsCRUD.get_sync_status(db, user_id, data_source)
        
        if not sync_status:
            sync_status = VitalsSyncStatus(
                user_id=user_id,
                data_source=data_source
            )
            db.add(sync_status)
        
        if last_sync_date:
            sync_status.last_sync_date = last_sync_date
            
        if success:
            sync_status.last_successful_sync = last_sync_date or datetime.utcnow()
            sync_status.error_count = 0
            sync_status.last_error = None
        else:
            sync_status.error_count = (sync_status.error_count or 0) + 1
            sync_status.last_error = error_message
        
        sync_status.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(sync_status)
        return sync_status
    
    @staticmethod
    def get_dashboard_data(
        db: Session,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get dashboard data for a user"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Get latest values for each metric type
        dashboard_data = {
            "user_id": user_id,
            "metrics": []
        }
        
        # Get all metric types the user has data for
        metric_types = db.query(VitalsRawData.metric_type).filter(
            VitalsRawData.user_id == user_id
        ).distinct().all()
        
        for (metric_type,) in metric_types:
            latest = VitalsCRUD.get_latest_value(db, user_id, metric_type)
            
            # Get daily aggregates for the period
            daily_data = db.query(VitalsDailyAggregate).filter(
                and_(
                    VitalsDailyAggregate.user_id == user_id,
                    VitalsDailyAggregate.metric_type == metric_type,
                    VitalsDailyAggregate.date >= start_date,
                    VitalsDailyAggregate.date <= end_date
                )
            ).order_by(VitalsDailyAggregate.date).all()
            
            metric_summary = {
                "metric_type": metric_type,
                "unit": latest.unit if latest else "",
                "latest_value": latest.value if latest else None,
                "latest_date": latest.start_date if latest else None,
                "latest_source": latest.data_source if latest else None,
                "data_points": []
            }
            
            for daily in daily_data:
                metric_summary["data_points"].append({
                    "metric_type": daily.metric_type,
                    "date": daily.date.isoformat(),
                    "average_value": daily.average_value,
                    "min_value": daily.min_value,
                    "max_value": daily.max_value,
                    "total_value": daily.total_value,
                    "count": daily.count,
                    "unit": daily.unit,
                    "primary_source": daily.primary_source
                })
            
            dashboard_data["metrics"].append(metric_summary)
        
        return dashboard_data

    # Aggregation Status Management Methods
    @staticmethod
    def mark_aggregation_processing(db: Session, entry_ids: List[int]):
        """Mark entries as being processed for aggregation"""
        db.query(VitalsRawData).filter(
            VitalsRawData.id.in_(entry_ids)
        ).update({
            "aggregation_status": "processing",
            "updated_at": datetime.utcnow()
        }, synchronize_session=False)
        db.commit()

    @staticmethod
    def mark_aggregation_completed(db: Session, entry_ids: List[int]):
        """Mark entries as successfully aggregated"""
        db.query(VitalsRawData).filter(
            VitalsRawData.id.in_(entry_ids)
        ).update({
            "aggregation_status": "completed",
            "aggregated_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }, synchronize_session=False)
        db.commit()

    @staticmethod
    def copy_raw_to_categorized_with_loinc(db: Session, user_id: int, target_date: date) -> int:
        """Copy raw vitals data to categorized table with LOINC code mapping"""
        try:
            # Get raw vitals data for the specific date that hasn't been categorized yet
            raw_data_query = db.query(VitalsRawData).filter(
                and_(
                    VitalsRawData.user_id == user_id,
                    func.date(VitalsRawData.start_date) == target_date,
                    VitalsRawData.aggregation_status.in_(["pending", "processing"])
                )
            ).all()

            if not raw_data_query:
                logger.info(f"ℹ️ [VitalsCategorization] No pending raw data found for user {user_id}, date {target_date}")
                return 0

            logger.info(f"📊 [VitalsCategorization] Processing {len(raw_data_query)} raw vitals records for categorization")

            # Initialize LOINC mapper for vitals
            loinc_mapper = None
            try:
                if 'LabTestLOINCMapper' in globals():
                    from app.crud.lab_categorization import LabTestLOINCMapper
                    loinc_mapper = LabTestLOINCMapper()
                    logger.info("🔧 [VitalsCategorization] LOINC mapper initialized for vitals processing")
            except Exception as e:
                logger.warning(f"⚠️ [VitalsCategorization] Failed to initialize LOINC mapper: {e}")

            categorized_count = 0
            failed_record_ids = []
            
            for raw_record in raw_data_query:
                try:
                    # Check if already exists in categorized table
                    existing_categorized = db.query(VitalsRawCategorized).filter(
                        and_(
                            VitalsRawCategorized.user_id == raw_record.user_id,
                            VitalsRawCategorized.metric_type == raw_record.metric_type,
                            VitalsRawCategorized.unit == raw_record.unit,
                            VitalsRawCategorized.start_date == raw_record.start_date,
                            VitalsRawCategorized.data_source == raw_record.data_source,
                            VitalsRawCategorized.notes == raw_record.notes
                        )
                    ).first()

                    if existing_categorized:
                        logger.debug(f"⏭️ [VitalsCategorization] Skipping duplicate record for {raw_record.metric_type}")
                        # Mark as categorized since it already exists
                        raw_record.aggregation_status = "categorized"
                        raw_record.updated_at = datetime.utcnow()
                        continue

                    # Step 1: Try to find LOINC code in vitals_mappings table
                    loinc_code = None
                    loinc_source = None

                    # Query vitals_mappings table for matching vital sign
                    vitals_mapping = db.execute(text("""
                        SELECT loinc_code, vital_sign, loinc_source 
                        FROM vitals_mappings 
                        WHERE vital_sign ILIKE :metric_type
                        OR vital_sign ILIKE :metric_type_with_percent
                        OR vital_sign ILIKE :metric_type_with_parens
                    """), {
                        "metric_type": f"%{raw_record.metric_type}%",
                        "metric_type_with_percent": f"%{raw_record.metric_type}%",
                        "metric_type_with_parens": f"%{raw_record.metric_type}%"
                    }).fetchone()

                    if vitals_mapping and vitals_mapping.loinc_code:
                        loinc_code = vitals_mapping.loinc_code
                        loinc_source = vitals_mapping.loinc_source
                        logger.debug(f"✅ [VitalsCategorization] Found LOINC code '{loinc_code}' in vitals_mappings for '{raw_record.metric_type}'")
                    else:
                        # Step 2: If not found in vitals_mappings, try to get LOINC code using the lab categorization method
                        if loinc_mapper:
                            logger.info(f"🔍 [VitalsCategorization] Looking up LOINC code for vital sign: {raw_record.metric_type}")
                            
                            # Use the lab categorization method to get LOINC code
                            from app.crud.lab_categorization import LabCategorizationCRUD
                            loinc_code, loinc_source = LabCategorizationCRUD.get_loinc_code_for_test(
                                test_name=raw_record.metric_type,
                                test_category="Vital Signs",
                                test_unit=raw_record.unit,
                                reference_range=None,
                                loinc_mapper=loinc_mapper
                            )

                            if loinc_code:
                                logger.info(f"✅ [VitalsCategorization] Found LOINC code '{loinc_code}' for vital sign '{raw_record.metric_type}'")
                                
                                # Add the new mapping to vitals_mappings table
                                try:
                                    db.execute(text("""
                                        INSERT INTO vitals_mappings (vital_sign, loinc_code, property, units, system, description, loinc_source)
                                        VALUES (:vital_sign, :loinc_code, :property, :units, :system, :description, :loinc_source)
                                        ON CONFLICT (vital_sign) DO UPDATE SET
                                            loinc_code = EXCLUDED.loinc_code,
                                            property = EXCLUDED.property,
                                            units = EXCLUDED.units,
                                            system = EXCLUDED.system,
                                            description = EXCLUDED.description,
                                            loinc_source = EXCLUDED.loinc_source
                                    """), {
                                        "vital_sign": raw_record.metric_type,
                                        "loinc_code": loinc_code,
                                        "property": "Vital Sign",
                                        "units": raw_record.unit,
                                        "system": "Body",
                                        "description": f"Auto-generated from vital sign: {raw_record.metric_type}",
                                        "loinc_source": loinc_source
                                    })
                                    logger.info(f"✅ [VitalsCategorization] Added new mapping to vitals_mappings: '{raw_record.metric_type}' -> '{loinc_code}'")
                                except Exception as e:
                                    logger.warning(f"⚠️ [VitalsCategorization] Failed to add mapping to vitals_mappings: {e}")
                            else:
                                logger.warning(f"⚠️ [VitalsCategorization] No LOINC code found for vital sign: {raw_record.metric_type}")
                        else:
                            logger.warning(f"⚠️ [VitalsCategorization] LOINC mapper not available for vital sign: {raw_record.metric_type}")

                    # Create categorized record
                    categorized_record = VitalsRawCategorized(
                        user_id=raw_record.user_id,
                        metric_type=raw_record.metric_type,
                        value=raw_record.value,
                        unit=raw_record.unit,
                        start_date=raw_record.start_date,
                        end_date=raw_record.end_date,
                        data_source=raw_record.data_source,
                        source_device=raw_record.source_device,
                        loinc_code=loinc_code,
                        notes=raw_record.notes,
                        confidence_score=raw_record.confidence_score,
                        aggregation_status="pending",
                        created_at=raw_record.created_at,
                        updated_at=datetime.utcnow()
                    )

                    db.add(categorized_record)
                    categorized_count += 1

                    # Mark original record as categorized
                    raw_record.aggregation_status = "categorized"
                    raw_record.updated_at = datetime.utcnow()

                except Exception as e:
                    logger.error(f"❌ [VitalsCategorization] Error processing record {raw_record.id}: {e}")
                    failed_record_ids.append(raw_record.id)
                    continue

            db.commit()
            
            # Mark failed records as failed (instead of leaving them in "processing" status)
            if failed_record_ids:
                VitalsCRUD.mark_aggregation_failed(db, failed_record_ids, "Categorization failed")
                logger.warning(f"⚠️ [VitalsCategorization] Marked {len(failed_record_ids)} records as failed due to categorization errors")
            
            logger.info(f"✅ [VitalsCategorization] Successfully categorized {categorized_count} vitals records with LOINC codes")
            return categorized_count

        except Exception as e:
            logger.error(f"❌ [VitalsCategorization] Error in vitals categorization: {e}")
            db.rollback()
            return 0

    @staticmethod
    def mark_aggregation_failed(db: Session, entry_ids: List[int], error_msg: str):
        """Mark entries as failed aggregation"""
        db.query(VitalsRawData).filter(
            VitalsRawData.id.in_(entry_ids)
        ).update({
            "aggregation_status": "failed",
            "notes": func.coalesce(VitalsRawData.notes, '') + f" | Aggregation failed: {error_msg}",
            "updated_at": datetime.utcnow()
        }, synchronize_session=False)
        db.commit()

    @staticmethod
    def mark_aggregation_queued(db: Session, entry_ids: List[int]):
        """Mark entries as queued for background processing"""
        db.query(VitalsRawData).filter(
            VitalsRawData.id.in_(entry_ids)
        ).update({
            "aggregation_status": "queued",
            "updated_at": datetime.utcnow()
        }, synchronize_session=False)
        db.commit()

    @staticmethod
    def get_pending_aggregation_entries(db: Session, limit: int = 1000) -> List[VitalsRawData]:
        """Get entries that need aggregation processing"""
        return db.query(VitalsRawData).filter(
            VitalsRawData.aggregation_status.in_(["pending", "queued", "failed"])
        ).order_by(VitalsRawData.created_at).limit(limit).all()

    @staticmethod
    def mark_categorized_aggregation_completed(db: Session, user_id: int, target_date: date):
        """Mark categorized vitals records as aggregated after aggregation completes"""
        try:
            # Update aggregation status for categorized vitals records
            updated_count = db.query(VitalsRawCategorized).filter(
                and_(
                    VitalsRawCategorized.user_id == user_id,
                    func.date(VitalsRawCategorized.start_date) == target_date,
                    VitalsRawCategorized.aggregation_status == "pending"
                )
            ).update({
                "aggregation_status": "aggregated",
                "aggregated_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }, synchronize_session=False)
            
            db.commit()
            logger.debug(f"✅ [VitalsAggregation] Marked {updated_count} categorized vitals records as aggregated for user {user_id}, date {target_date}")
            return updated_count
            
        except Exception as e:
            logger.error(f"❌ [VitalsAggregation] Error marking categorized records as aggregated: {e}")
            db.rollback()
            return 0

    @staticmethod
    def get_aggregation_status_counts(db: Session, user_id: int) -> Dict[str, int]:
        """Get count of records by aggregation status for a user"""
        result = db.query(
            VitalsRawData.aggregation_status,
            func.count(VitalsRawData.id)
        ).filter(
            VitalsRawData.user_id == user_id
        ).group_by(VitalsRawData.aggregation_status).all()
        
        return {status: count for status, count in result}

    @staticmethod
    def aggregate_weekly_data(db: Session, user_id: int, target_week_start: date) -> int:
        """Aggregate daily data into weekly aggregates"""
        aggregated_count = 0
        
        # Calculate week end date (Sunday)
        target_week_end = target_week_start + timedelta(days=6)
        
        # Get all metric types for the user in this week
        metric_types = db.query(VitalsDailyAggregate.metric_type).filter(
            and_(
                VitalsDailyAggregate.user_id == user_id,
                VitalsDailyAggregate.date >= target_week_start,
                VitalsDailyAggregate.date <= target_week_end
            )
        ).distinct().all()
        
        for (metric_type,) in metric_types:
            # Get daily data for this week
            daily_data = db.query(VitalsDailyAggregate).filter(
                and_(
                    VitalsDailyAggregate.user_id == user_id,
                    VitalsDailyAggregate.metric_type == metric_type,
                    VitalsDailyAggregate.date >= target_week_start,
                    VitalsDailyAggregate.date <= target_week_end
                )
            ).all()
            
            if not daily_data:
                continue
            
            # Calculate weekly aggregates
            total_values = [d.total_value for d in daily_data if d.total_value is not None]
            avg_values = [d.average_value for d in daily_data if d.average_value is not None]
            min_values = [d.min_value for d in daily_data if d.min_value is not None]
            max_values = [d.max_value for d in daily_data if d.max_value is not None]
            
            sources = set()
            for d in daily_data:
                if d.sources_included:
                    try:
                        sources.update(json.loads(d.sources_included))
                    except:
                        pass
            
            latest_entry = max(daily_data, key=lambda x: x.date)
            
            # Check if weekly aggregate already exists
            existing = db.query(VitalsWeeklyAggregate).filter(
                and_(
                    VitalsWeeklyAggregate.user_id == user_id,
                    VitalsWeeklyAggregate.metric_type == metric_type,
                    VitalsWeeklyAggregate.week_start_date == target_week_start
                )
            ).first()
            
            # Get LOINC code from the latest daily entry (all entries should have same LOINC code)
            loinc_code = latest_entry.loinc_code
            
            if existing:
                # Update existing aggregate
                existing.total_value = sum(total_values) if total_values else None
                existing.average_value = sum(avg_values) / len(avg_values) if avg_values else None
                existing.min_value = min(min_values) if min_values else None
                existing.max_value = max(max_values) if max_values else None
                existing.days_with_data = len(daily_data)
                existing.loinc_code = loinc_code  # Copy LOINC code
                existing.primary_source = latest_entry.primary_source
                existing.sources_included = json.dumps(list(sources))
                existing.updated_at = datetime.utcnow()
            else:
                # Create new weekly aggregate
                aggregate = VitalsWeeklyAggregate(
                    user_id=user_id,
                    metric_type=metric_type,
                    loinc_code=loinc_code,  # Copy LOINC code
                    week_start_date=target_week_start,
                    week_end_date=target_week_end,
                    total_value=sum(total_values) if total_values else None,
                    average_value=sum(avg_values) / len(avg_values) if avg_values else None,
                    min_value=min(min_values) if min_values else None,
                    max_value=max(max_values) if max_values else None,
                    days_with_data=len(daily_data),
                    unit=latest_entry.unit,
                    primary_source=latest_entry.primary_source,
                    sources_included=json.dumps(list(sources))
                )
                db.add(aggregate)
                aggregated_count += 1
        
        db.commit()
        return aggregated_count
    
    @staticmethod
    def aggregate_monthly_data(db: Session, user_id: int, target_year: int, target_month: int) -> int:
        """Aggregate daily data into monthly aggregates"""
        aggregated_count = 0
        
        # Calculate month start and end dates
        month_start = date(target_year, target_month, 1)
        if target_month == 12:
            month_end = date(target_year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(target_year, target_month + 1, 1) - timedelta(days=1)
        
        # Get all metric types for the user in this month
        metric_types = db.query(VitalsDailyAggregate.metric_type).filter(
            and_(
                VitalsDailyAggregate.user_id == user_id,
                VitalsDailyAggregate.date >= month_start,
                VitalsDailyAggregate.date <= month_end
            )
        ).distinct().all()
        
        for (metric_type,) in metric_types:
            # Get daily data for this month
            daily_data = db.query(VitalsDailyAggregate).filter(
                and_(
                    VitalsDailyAggregate.user_id == user_id,
                    VitalsDailyAggregate.metric_type == metric_type,
                    VitalsDailyAggregate.date >= month_start,
                    VitalsDailyAggregate.date <= month_end
                )
            ).all()
            
            if not daily_data:
                continue
            
            # Calculate monthly aggregates
            total_values = [d.total_value for d in daily_data if d.total_value is not None]
            avg_values = [d.average_value for d in daily_data if d.average_value is not None]
            min_values = [d.min_value for d in daily_data if d.min_value is not None]
            max_values = [d.max_value for d in daily_data if d.max_value is not None]
            
            sources = set()
            for d in daily_data:
                if d.sources_included:
                    try:
                        sources.update(json.loads(d.sources_included))
                    except:
                        pass
            
            latest_entry = max(daily_data, key=lambda x: x.date)
            
            # Check if monthly aggregate already exists
            existing = db.query(VitalsMonthlyAggregate).filter(
                and_(
                    VitalsMonthlyAggregate.user_id == user_id,
                    VitalsMonthlyAggregate.metric_type == metric_type,
                    VitalsMonthlyAggregate.year == target_year,
                    VitalsMonthlyAggregate.month == target_month
                )
            ).first()
            
            # Get LOINC code from the latest daily entry (all entries should have same LOINC code)
            loinc_code = latest_entry.loinc_code
            
            if existing:
                # Update existing aggregate
                existing.total_value = sum(total_values) if total_values else None
                existing.average_value = sum(avg_values) / len(avg_values) if avg_values else None
                existing.min_value = min(min_values) if min_values else None
                existing.max_value = max(max_values) if max_values else None
                existing.days_with_data = len(daily_data)
                existing.loinc_code = loinc_code  # Copy LOINC code
                existing.primary_source = latest_entry.primary_source
                existing.sources_included = json.dumps(list(sources))
                existing.updated_at = datetime.utcnow()
            else:
                # Create new monthly aggregate
                aggregate = VitalsMonthlyAggregate(
                    user_id=user_id,
                    metric_type=metric_type,
                    loinc_code=loinc_code,  # Copy LOINC code
                    year=target_year,
                    month=target_month,
                    total_value=sum(total_values) if total_values else None,
                    average_value=sum(avg_values) / len(avg_values) if avg_values else None,
                    min_value=min(min_values) if min_values else None,
                    max_value=max(max_values) if max_values else None,
                    days_with_data=len(daily_data),
                    unit=latest_entry.unit,
                    primary_source=latest_entry.primary_source,
                    sources_included=json.dumps(list(sources))
                )
                db.add(aggregate)
                aggregated_count += 1
        
        db.commit()
        return aggregated_count 