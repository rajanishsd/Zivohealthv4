from datetime import date, datetime, timedelta
from app.utils.timezone import now_local, today_local
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.api import deps
from app.crud.vitals import VitalsCRUD
from app.utils.unit_converter import VitalUnitConverter, UnitConversionError
from app.schemas.vitals import (
    VitalDataSubmission,
    VitalBulkSubmission,
    VitalDataQuery,
    VitalMetricSummary,
    VitalsDashboard,
    VitalsSyncStatusResponse,
    ChartData,
    ChartDataPoint,
    VitalMetricsChartsResponse,
    VitalSubmissionResponse,
    VitalMetricType,
    VitalDataSource,
    TimeGranularity,
    VitalAggregateData,
    WeightUpdateRequest,
    WeightUpdateResponse
)
from app.models.user import User
from app.models.vitals_data import VitalsRawData, VitalsSyncStatus, VitalsDailyAggregate
import logging
import uuid
from app.core.sync_state import sync_state_manager
from app.utils.sqs_client import get_ml_worker_client
import asyncio

router = APIRouter()

logger = logging.getLogger(__name__)

def standardize_vital_data(data: VitalDataSubmission) -> VitalDataSubmission:
    """
    Standardize vital data by converting units to standard format
    
    Args:
        data: The vital data submission to standardize
        
    Returns:
        VitalDataSubmission with standardized units
        
    Raises:
        UnitConversionError: If conversion fails
    """
    try:
        # Convert to standard unit
        converted_value, standard_unit = VitalUnitConverter.convert_to_standard_unit(
            data.value, data.unit, data.metric_type
        )
        
        # Create new submission with standardized values
        return VitalDataSubmission(
            metric_type=data.metric_type,
            value=converted_value,
            unit=standard_unit,
            start_date=data.start_date,
            end_date=data.end_date,
            data_source=data.data_source,
            notes=data.notes,
            source_device=data.source_device,
            confidence_score=data.confidence_score
        )
    except UnitConversionError as e:
        # Log the error but don't fail the submission - use original data
        logger.warning(f"Unit conversion failed for {data.metric_type.value}: {e}")
        # Add conversion error to notes
        notes = f"{data.notes or ''} [Unit conversion failed: {e}]".strip()
        return VitalDataSubmission(
            metric_type=data.metric_type,
            value=data.value,
            unit=data.unit,
            start_date=data.start_date,
            end_date=data.end_date,
            data_source=data.data_source,
            notes=notes,
            source_device=data.source_device,
            confidence_score=data.confidence_score
        )

@router.post("/submit", response_model=VitalSubmissionResponse)
async def submit_vital_data(
    data: VitalDataSubmission,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Submit a single vital data point"""
    try:
        # Standardize units before storage
        standardized_data = standardize_vital_data(data)
        
        db_data = VitalsCRUD.create_raw_data(db, current_user.id, standardized_data)
        
        # Update sync status to track the submission
        VitalsCRUD.update_sync_status(
            db=db,
            user_id=current_user.id,
            data_source=data.data_source,
            last_sync_date=now_local(),
            success=True,
            error_message=None
        )
        
        # Trigger ML worker via SQS to process pending vitals (fire-and-forget)
        try:
            ml_worker_client = get_ml_worker_client()
            if ml_worker_client.is_enabled():
                ml_worker_client.send_vitals_processing_trigger(user_id=current_user.id, priority='normal')
        except Exception as e:
            logger.warning(f"⚠️  Failed to trigger ML worker for vitals: {e}")
        
        return VitalSubmissionResponse(
            success=True,
            message="Vital data submitted successfully - separate worker process triggered",
            processed_count=1,
            aggregation_status="triggered",
            errors=None
        )
    except Exception as e:
        logger.error(f"Error submitting vital data: {str(e)}")
        
        # Update sync status to track the failure
        try:
            VitalsCRUD.update_sync_status(
                db=db,
                user_id=current_user.id,
                data_source=data.data_source,
                last_sync_date=now_local(),
                success=False,
                error_message=str(e)
            )
        except Exception as sync_error:
            logger.error(f"Failed to update sync status: {sync_error}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit vital data: {str(e)}"
        )

@router.post("/bulk-submit", response_model=VitalSubmissionResponse)
async def bulk_submit_vital_data(
    data: VitalBulkSubmission,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Submit multiple vital data points with event-driven aggregation"""
    # Extract chunk information
    chunk_info = data.chunk_info
    is_chunked_submission = chunk_info is not None
    is_final_chunk = chunk_info.get('is_final_chunk', True) if is_chunked_submission else True
    session_id = chunk_info.get('session_id', f"single_{uuid.uuid4().hex[:8]}") if is_chunked_submission else f"single_{uuid.uuid4().hex[:8]}"
    chunk_number = chunk_info.get('chunk_number', 1) if is_chunked_submission else 1
    total_chunks = chunk_info.get('total_chunks', 1) if is_chunked_submission else 1
    
    # Generate operation ID based on session and chunk
    operation_id = f"bulk_submit_{session_id}_chunk_{chunk_number}"
    
    try:
        # Register the start of sync operation
        sync_state_manager.start_sync_operation(current_user.id, operation_id)
        
        # Standardize units for all data points before storage
        standardized_data = [standardize_vital_data(vital_data) for vital_data in data.data]
        
        # Insert raw data (fast operation)
        db_entries = VitalsCRUD.bulk_create_raw_data(db, current_user.id, standardized_data)
        batch_size = len(db_entries)
        
        # Update sync status for each data source in this batch
        data_sources = {item.data_source for item in data.data}
        for data_source in data_sources:
            VitalsCRUD.update_sync_status(
                db=db,
                user_id=current_user.id,
                data_source=data_source,
                last_sync_date=now_local(),
                success=True,
                error_message=None
            )
        
        if is_chunked_submission:
            logger.info(f"📱 [BulkSubmit] Chunk {chunk_number}/{total_chunks} submitted: {batch_size} data points for user {current_user.id} (session: {session_id})")
        else:
            logger.info(f"📱 [BulkSubmit] Single submission: {batch_size} data points for user {current_user.id}")
        
        # Only trigger aggregation if this is the final chunk or a single submission
        should_trigger_aggregation = is_final_chunk
        
        if should_trigger_aggregation:
            logger.info(f"🚀 [BulkSubmit] Final chunk received - triggering coalesced vitals aggregation for session {session_id}")
            # Trigger ML worker via SQS (fire-and-forget)
            try:
                ml_worker_client = get_ml_worker_client()
                if ml_worker_client.is_enabled():
                    ml_worker_client.send_vitals_processing_trigger(user_id=current_user.id, priority='normal')
            except Exception as e:
                logger.warning(f"⚠️  Failed to trigger ML worker for vitals: {e}") 
        else:
            logger.info(f"⏳ [BulkSubmit] Intermediate chunk {chunk_number}/{total_chunks} - aggregation deferred until final chunk")
        
        aggregation_status = "triggered" if should_trigger_aggregation else "deferred"
        message_suffix = f"Aggregation {'triggered' if should_trigger_aggregation else 'deferred until final chunk'}."
        
        response = VitalSubmissionResponse(
            success=True,
            message=f"Successfully submitted {batch_size} data points. {message_suffix}",
            processed_count=batch_size,
            aggregation_status=aggregation_status
        )
        
        # Register the end of sync operation
        sync_state_manager.end_sync_operation(current_user.id, operation_id)
        
        return response
            
    except Exception as e:
        # Make sure to end the sync operation even on error
        sync_state_manager.end_sync_operation(current_user.id, operation_id)
        
        # Update sync status to track the failure for all data sources in this batch
        try:
            data_sources = {item.data_source for item in data.data}
            for data_source in data_sources:
                VitalsCRUD.update_sync_status(
                    db=db,
                    user_id=current_user.id,
                    data_source=data_source,
                    last_sync_date=now_local(),
                    success=False,
                    error_message=str(e)
                )
        except Exception as sync_error:
            logger.error(f"Failed to update sync status: {sync_error}")
        
        logger.error(f"❌ [BulkSubmit] Error bulk submitting vital data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk submit vital data: {str(e)}"
        )

@router.get("/dashboard", response_model=VitalsDashboard)
async def get_vitals_dashboard(
    days: int = Query(30, description="Number of days to include in dashboard"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Get vitals dashboard data for the current user"""
    try:
        dashboard_data = VitalsCRUD.get_dashboard_data(db, current_user.id, days)
        return VitalsDashboard(**dashboard_data)
    except Exception as e:
        logger.error(f"Error getting vitals dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vitals dashboard: {str(e)}"
        )

@router.get("/charts", response_model=VitalMetricsChartsResponse)
async def get_vitals_charts(
    metric_types: List[VitalMetricType] = Query(None, description="Metric types to include"),
    granularity: TimeGranularity = Query(TimeGranularity.DAILY, description="Data granularity"),
    days: int = Query(30, description="Number of days to include"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Get chart data for vital metrics"""
    try:
        end_date = today_local()
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"📊 [VitalsCharts] Request for user {current_user.id}: metric_types={[mt.value for mt in metric_types]}, granularity={granularity.value}, days={days}")
        
        # If no metric types specified, get all available for user
        if not metric_types:
            available_metrics = db.query(VitalsRawData.metric_type).filter(
                VitalsRawData.user_id == current_user.id
            ).distinct().all()
            metric_types = [m[0] for m in available_metrics]
            logger.info(f"📊 [VitalsCharts] No metric types specified, found available: {[mt.value for mt in metric_types]}")
        
        charts = []
        for metric_type in metric_types:
            logger.info(f"📊 [VitalsCharts] Processing metric: {metric_type.value}")
            chart_data = await get_chart_data(
                db, current_user.id, metric_type, granularity, start_date, end_date
            )
            if chart_data:
                logger.info(f"📊 [VitalsCharts] Found {len(chart_data.data_points)} data points for {metric_type.value}")
                charts.append(chart_data)
            else:
                logger.info(f"📊 [VitalsCharts] No data found for {metric_type.value}")
        
        logger.info(f"📊 [VitalsCharts] Returning {len(charts)} charts for user {current_user.id}")
        return VitalMetricsChartsResponse(
            user_id=current_user.id,
            charts=charts,
            date_range={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Error getting vitals charts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vitals charts: {str(e)}"
        )

@router.get("/aggregation-status")
async def get_aggregation_status(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Get aggregation status for user's data"""
    try:
        status_counts = VitalsCRUD.get_aggregation_status_counts(db, current_user.id)
        
        # Calculate total records
        total_records = sum(status_counts.values())
        
        # Calculate completion percentage
        completed_count = status_counts.get('completed', 0)
        completion_percentage = (completed_count / total_records * 100) if total_records > 0 else 100
        
        return {
            "user_id": current_user.id,
            "aggregation_status": status_counts,
            "total_records": total_records,
            "completion_percentage": round(completion_percentage, 2),
            "pending_aggregation": status_counts.get('pending', 0) + status_counts.get('queued', 0) + status_counts.get('failed', 0)
        }
    except Exception as e:
        logger.error(f"Error getting aggregation status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get aggregation status: {str(e)}"
        )

@router.get("/data-count", response_model=dict)
async def get_vitals_data_count(
    metric_types: List[VitalMetricType] = Query(None, description="Metric types to count"),
    days: int = Query(30, description="Number of days to look back"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Get count of vitals data by metric type for checking sync status"""
    try:
        end_date = now_local()
        start_date = end_date - timedelta(days=days)
        
        # If no metric types specified, get counts for all available metrics
        if not metric_types:
            metric_types = list(VitalMetricType)
        
        counts = {}
        total_count = 0
        
        for metric_type in metric_types:
            count = db.query(VitalsRawData).filter(
                VitalsRawData.user_id == current_user.id,
                VitalsRawData.metric_type == metric_type.value,
                VitalsRawData.start_date >= start_date,
                VitalsRawData.start_date <= end_date
            ).count()
            
            counts[metric_type.value] = count
            total_count += count
        
        # Get the most recent data point timestamp
        latest_data = db.query(VitalsRawData).filter(
            VitalsRawData.user_id == current_user.id
        ).order_by(VitalsRawData.start_date.desc()).first()
        
        return {
            "user_id": current_user.id,
            "total_count": total_count,
            "counts_by_metric": counts,
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            },
            "latest_data_timestamp": latest_data.start_date.isoformat() if latest_data else None
        }
    except Exception as e:
        logger.error(f"Error getting vitals data count: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vitals data count: {str(e)}"
        )

@router.get("/sync-status/{data_source}", response_model=VitalsSyncStatusResponse)
async def get_sync_status(
    data_source: VitalDataSource,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Get sync status for a specific data source"""
    try:
        sync_status = VitalsCRUD.get_sync_status(db, current_user.id, data_source)
        
        if not sync_status:
            # Create default sync status
            sync_status = VitalsSyncStatus(
                user_id=current_user.id,
                data_source=data_source,
                sync_enabled="false"
            )
        
        return VitalsSyncStatusResponse(
            user_id=current_user.id,
            data_source=data_source,
            sync_enabled=sync_status.sync_enabled,
            last_sync_date=sync_status.last_sync_date,
            last_successful_sync=sync_status.last_successful_sync,
            last_error=sync_status.last_error,
            error_count=sync_status.error_count or 0
        )
    except Exception as e:
        logger.error(f"Error getting sync status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}"
        )

@router.post("/sync-status/{data_source}/enable")
async def enable_sync(
    data_source: VitalDataSource,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Enable sync for a specific data source"""
    try:
        sync_status = VitalsCRUD.update_sync_status(
            db, current_user.id, data_source, success=True
        )
        sync_status.sync_enabled = "true"
        db.commit()
        
        return {"message": f"Sync enabled for {data_source}"}
    except Exception as e:
        logger.error(f"Error enabling sync: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable sync: {str(e)}"
        )

@router.post("/weight", response_model=WeightUpdateResponse)
async def update_weight(
    weight_data: WeightUpdateRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Update weight - backward compatibility endpoint"""
    try:
        measurement_date = weight_data.measurement_date or now_local()
        
        vital_data = VitalDataSubmission(
            metric_type=VitalMetricType.BODY_MASS,
            value=weight_data.weight,
            unit=weight_data.unit,
            start_date=measurement_date,
            end_date=measurement_date,
            data_source=VitalDataSource.MANUAL_ENTRY,
            notes=weight_data.notes
        )
        
        db_data = VitalsCRUD.create_raw_data(db, current_user.id, vital_data)
        
        # Trigger ML worker via SQS to process pending vitals (fire-and-forget)
        try:
            ml_worker_client = get_ml_worker_client()
            if ml_worker_client.is_enabled():
                ml_worker_client.send_vitals_processing_trigger(user_id=current_user.id, priority='normal')
        except Exception as e:
            logger.warning(f"⚠️  Failed to trigger ML worker for vitals: {e}") 
        
        return WeightUpdateResponse(
            success=True,
            message="Weight updated successfully",
            weight_id=db_data.id,
            weight_value=db_data.value,
            unit=db_data.unit,
            measurement_date=db_data.start_date
        )
    except Exception as e:
        logger.error(f"Error updating weight: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update weight: {str(e)}"
        )

@router.post("/aggregate/{target_date}")
async def trigger_manual_aggregation(
    target_date: date,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Manually trigger aggregation for a specific date"""
    try:
        hourly_count = VitalsCRUD.aggregate_hourly_data(db, current_user.id, target_date)
        daily_count = VitalsCRUD.aggregate_daily_data(db, current_user.id, target_date)
        
        # Calculate week start (Monday) for weekly aggregation
        days_since_monday = target_date.weekday()
        week_start = target_date - timedelta(days=days_since_monday)
        
        # Aggregate weekly data
        weekly_count = VitalsCRUD.aggregate_weekly_data(db, current_user.id, week_start)
        
        # Aggregate monthly data
        monthly_count = VitalsCRUD.aggregate_monthly_data(db, current_user.id, target_date.year, target_date.month)
        
        return {
            "message": f"Aggregation completed for {target_date}",
            "hourly_aggregates_created": hourly_count,
            "daily_aggregates_created": daily_count,
            "weekly_aggregates_created": weekly_count,
            "monthly_aggregates_created": monthly_count
        }
    except Exception as e:
        logger.error(f"Error triggering aggregation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger aggregation: {str(e)}"
        )

# Helper functions
async def trigger_sync_aggregation(db: Session, user_id: int, target_date: date):
    """Trigger synchronous aggregation for small batches"""
    try:
        # Aggregate hourly data first
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
        
        logger.debug(f"📊 [SyncAggregation] Created {hourly_count} hourly, {daily_count} daily, {weekly_count} weekly, {monthly_count} monthly aggregates for {target_date}")
    except Exception as e:
        logger.error(f"❌ [SyncAggregation] Error in synchronous aggregation: {str(e)}")
        raise e

async def trigger_aggregation(db: Session, user_id: int, target_date: date):
    """Trigger background aggregation for a specific date (legacy function)"""
    try:
        # Aggregate hourly data first
        VitalsCRUD.aggregate_hourly_data(db, user_id, target_date)
        # Then aggregate daily data
        VitalsCRUD.aggregate_daily_data(db, user_id, target_date)
    except Exception as e:
        logger.error(f"Error in background aggregation: {str(e)}")

async def get_chart_data(
    db: Session, 
    user_id: int, 
    metric_type: VitalMetricType, 
    granularity: TimeGranularity,
    start_date: date,
    end_date: date
) -> Optional[ChartData]:
    """Get chart data for a specific metric"""
    try:
        logger.info(f"📊 [get_chart_data] Getting data for {metric_type.value}, user {user_id}, {start_date} to {end_date}")
        data_points = []
        unit = ""
        
        if granularity == TimeGranularity.DAILY:
            # Get daily aggregates
            daily_data = VitalsCRUD.get_daily_aggregates(
                db, user_id, metric_type, start_date, end_date
            )
            logger.info(f"📊 [get_chart_data] Found {len(daily_data)} daily aggregates for {metric_type.value}")
            
            for daily in daily_data:
                logger.info(f"📊 [get_chart_data] Daily data: date={daily.date}, avg={daily.average_value}, total={daily.total_value}, min={daily.min_value}, max={daily.max_value}")
                # For heart rate, include min/max values to show daily range
                if metric_type == VitalMetricType.HEART_RATE:
                    data_points.append(ChartDataPoint(
                        date=daily.date.isoformat(),
                        value=daily.average_value or daily.total_value or 0,
                        min_value=daily.min_value,
                        max_value=daily.max_value,
                        source=daily.primary_source
                    ))
                else:
                    data_points.append(ChartDataPoint(
                        date=daily.date.isoformat(),
                        value=daily.average_value or daily.total_value or 0,
                        source=daily.primary_source
                    ))
            
            unit = daily_data[0].unit if daily_data else ""
            
        elif granularity == TimeGranularity.WEEKLY:
            # Get weekly aggregates
            weekly_data = VitalsCRUD.get_weekly_aggregates(
                db, user_id, metric_type, start_date, end_date
            )
            
            for weekly in weekly_data:
                if metric_type == VitalMetricType.HEART_RATE:
                    data_points.append(ChartDataPoint(
                        date=weekly.week_start_date.isoformat(),
                        value=weekly.average_value or weekly.total_value or 0,
                        min_value=weekly.min_value,
                        max_value=weekly.max_value,
                        source=weekly.primary_source
                    ))
                else:
                    data_points.append(ChartDataPoint(
                        date=weekly.week_start_date.isoformat(),
                        value=weekly.average_value or weekly.total_value or 0,
                        source=weekly.primary_source
                    ))
            
            unit = weekly_data[0].unit if weekly_data else ""
            
        elif granularity == TimeGranularity.MONTHLY:
            # Get monthly aggregates
            start_year = start_date.year
            end_year = end_date.year
            monthly_data = VitalsCRUD.get_monthly_aggregates(
                db, user_id, metric_type, start_year, end_year
            )
            
            # Filter monthly data by date range
            filtered_monthly = []
            for monthly in monthly_data:
                month_date = date(monthly.year, monthly.month, 1)
                if start_date <= month_date <= end_date:
                    filtered_monthly.append(monthly)
            
            for monthly in filtered_monthly:
                # Create date as first day of month
                month_date = date(monthly.year, monthly.month, 1)
                if metric_type == VitalMetricType.HEART_RATE:
                    data_points.append(ChartDataPoint(
                        date=month_date.isoformat(),
                        value=monthly.average_value or monthly.total_value or 0,
                        min_value=monthly.min_value,
                        max_value=monthly.max_value,
                        source=monthly.primary_source
                    ))
                else:
                    data_points.append(ChartDataPoint(
                        date=month_date.isoformat(),
                        value=monthly.average_value or monthly.total_value or 0,
                        source=monthly.primary_source
                    ))
            
            unit = filtered_monthly[0].unit if filtered_monthly else ""
        
        if not data_points:
            logger.info(f"📊 [get_chart_data] No data points found for {metric_type.value}")
            return None
        
        # Calculate chart metadata
        values = [dp.value for dp in data_points if dp.value is not None]
        logger.info(f"📊 [get_chart_data] Returning {len(data_points)} data points for {metric_type.value}, values: {values[:5]}...")
        
        return ChartData(
            metric_type=metric_type,
            unit=unit,
            granularity=granularity,
            data_points=data_points,
            min_value=min(values) if values else None,
            max_value=max(values) if values else None,
            average_value=sum(values) / len(values) if values else None,
            total_value=sum(values) if values else None
        )
    except Exception as e:
        logger.error(f"Error getting chart data: {str(e)}")
        return None

@router.get("/sync-state")
async def get_sync_state(
    current_user: User = Depends(deps.get_current_user)
):
    """Get current sync state and worker status"""
    from app.core.sync_state import sync_state_manager
    
    try:
        status = sync_state_manager.get_status()
        return {
            "user_id": current_user.id,
            "sync_state": status,
            "message": "Sync state retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting sync state: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync state: {str(e)}"
        )

@router.post("/start-aggregation-worker")
async def start_aggregation_worker(
    current_user: User = Depends(deps.get_current_user)
):
    """Manually start the aggregation worker using separate process"""
    import subprocess
    import os
    
    try:
        # Trigger separate worker process for true isolation
        logger.info(f"🚀 [StartWorker] Triggering separate worker process for true isolation")
        
        worker_script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", "aggregation", "worker_process.py")
        process = subprocess.Popen(
            ["python", worker_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(worker_script)
        )
        
        logger.info(f"✅ [StartWorker] Separate worker process triggered successfully (PID: {process.pid})")
        
        return {
            "success": True,
            "message": "Separate worker process started successfully",
            "worker_started": True,
            "worker_pid": process.pid
        }
            
    except Exception as e:
        logger.error(f"❌ [StartWorker] Failed to trigger separate worker process: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start worker process: {str(e)}"
        )

@router.post("/trigger-worker-process")
async def trigger_worker_process(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Trigger separate worker process to handle aggregation queue"""
    import subprocess
    import os
    
    try:
        # Check if there's pending work
        pending_count = len(VitalsCRUD.get_pending_aggregation_entries(db, limit=1))
        
        if pending_count == 0:
            return {
                "status": "success",
                "message": "No pending work - worker not needed",
                "worker_triggered": False,
                "pending_entries": 0
            }
        
        # Get total pending count for reporting
        total_pending = len(VitalsCRUD.get_pending_aggregation_entries(db, limit=100000))
        
        # Trigger worker process in background
        worker_script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", "aggregation", "worker_process.py")
        
        # Start worker process (non-blocking)
        process = subprocess.Popen(
            ["python", worker_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(worker_script)
        )
        
        logger.info(f"🚀 [API] Triggered worker process (PID: {process.pid}) for {total_pending:,} pending entries")
        
        return {
            "status": "success",
            "message": f"Worker process triggered successfully for {total_pending:,} pending entries",
            "worker_triggered": True,
            "worker_pid": process.pid,
            "pending_entries": total_pending
        }
    
    except Exception as e:
        logger.error(f"Failed to trigger worker process: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger worker: {str(e)}") 