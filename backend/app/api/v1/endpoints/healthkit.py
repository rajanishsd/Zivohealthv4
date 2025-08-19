from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.crud.healthkit import HealthKitCRUD
from app.schemas.healthkit import (
    HealthKitDataSubmission,
    HealthKitBulkSubmission,
    HealthKitDataQuery,
    HealthKitMetricSummary,
    HealthKitDashboard,
    HealthKitSyncStatusResponse,
    ChartData,
    ChartDataPoint,
    HealthMetricsChartsResponse,
    HealthKitSubmissionResponse,
    HealthKitMetricType,
    TimeGranularity,
    HealthKitAggregateData
)
from app.models.user import User
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/submit", response_model=HealthKitSubmissionResponse)
def submit_healthkit_data(
    data: HealthKitDataSubmission,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Submit a single HealthKit data point"""
    try:
        # Create raw data entry
        raw_data = HealthKitCRUD.create_raw_data(db, current_user.id, data)
        
        # Create/update daily aggregate
        target_date = data.start_date.date()
        HealthKitCRUD.create_or_update_daily_aggregate(
            db, current_user.id, data.metric_type, target_date
        )
        
        # Update sync status
        HealthKitCRUD.update_sync_status(
            db, current_user.id, data.metric_type, success=True
        )
        
        return HealthKitSubmissionResponse(
            success=True,
            message="Data submitted successfully",
            processed_count=1
        )
        
    except Exception as e:
        # Update sync status with error
        HealthKitCRUD.update_sync_status(
            db, current_user.id, data.metric_type, success=False, error_message=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit data: {str(e)}"
        )

@router.post("/submit-bulk", response_model=HealthKitSubmissionResponse)
def submit_bulk_healthkit_data(
    bulk_data: HealthKitBulkSubmission,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Submit multiple HealthKit data points in bulk"""
    try:
        # Debug logging - log first few data points received
        logger.info(f"Backend: Received bulk submission with {len(bulk_data.data)} data points")
        for i, data_point in enumerate(bulk_data.data[:3]):  # Log first 3 data points
            logger.info(f"Backend: Data point {i+1} - Type: {data_point.metric_type}, Value: {data_point.value}, Start: {data_point.start_date}, End: {data_point.end_date}, Source: {data_point.source_device}")
        
        # Create raw data entries
        raw_entries = HealthKitCRUD.bulk_create_raw_data(db, current_user.id, bulk_data.data)
        
        # Debug logging - log what was actually stored in database
        for i, raw_entry in enumerate(raw_entries[:3]):  # Log first 3 stored entries
            logger.info(f"Backend: Stored entry {i+1} - ID: {raw_entry.id}, Type: {raw_entry.metric_type}, Value: {raw_entry.value}, Start: {raw_entry.start_date}, End: {raw_entry.end_date}, Source: {raw_entry.source_device}")
        
        # Group by metric type and date for aggregation
        metrics_by_date = {}
        for data_point in bulk_data.data:
            key = (data_point.metric_type, data_point.start_date.date())
            if key not in metrics_by_date:
                metrics_by_date[key] = []
            metrics_by_date[key].append(data_point)
        
        # Create/update daily aggregates
        for (metric_type, target_date), _ in metrics_by_date.items():
            HealthKitCRUD.create_or_update_daily_aggregate(
                db, current_user.id, metric_type, target_date
            )
        
        # Update sync status
        unique_metrics = set(data.metric_type for data in bulk_data.data)
        for metric_type in unique_metrics:
            HealthKitCRUD.update_sync_status(
                db, current_user.id, metric_type, success=True
            )
        
        return HealthKitSubmissionResponse(
            success=True,
            message=f"Bulk data submitted successfully",
            processed_count=len(bulk_data.data)
        )
        
    except Exception as e:
        logger.error(f"Backend: Error in bulk submission: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit bulk data: {str(e)}"
        )

@router.get("/dashboard", response_model=HealthKitDashboard)
def get_health_dashboard(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get complete health dashboard data"""
    
    # Get sync status
    sync_status = HealthKitCRUD.get_or_create_sync_status(db, current_user.id)
    
    # Get latest data for each metric
    latest_data = HealthKitCRUD.get_latest_data_by_metric(db, current_user.id)
    
    # Build metric summaries
    metrics = []
    for metric_type in HealthKitMetricType:
        if metric_type in latest_data:
            latest = latest_data[metric_type]
            
            # Get recent daily aggregates (last 30 days)
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            daily_data = HealthKitCRUD.get_daily_aggregates(
                db, current_user.id, metric_type, start_date, end_date
            )
            
            # Convert daily aggregates to data points for the dashboard
            data_points = []
            for d in daily_data:
                # Parse workout breakdown if available
                workout_breakdown = None
                if metric_type == HealthKitMetricType.WORKOUTS and d.notes:
                    try:
                        import json
                        enhanced_data = json.loads(d.notes)
                        # Extract just the workout types and durations for backward compatibility
                        if "workouts" in enhanced_data:
                            workout_breakdown = {
                                workout_type: details["duration"] 
                                for workout_type, details in enhanced_data["workouts"].items()
                            }
                        else:
                            # Fallback for simple format
                            workout_breakdown = enhanced_data
                    except:
                        workout_breakdown = None
                
                data_point = HealthKitAggregateData(
                    metric_type=metric_type,
                    date=d.date.isoformat() if d.date else None,  # Convert date to string
                    week_start_date=d.week_start_date.isoformat() if hasattr(d, 'week_start_date') and d.week_start_date else None,
                    year=getattr(d, 'year', None),
                    month=getattr(d, 'month', None),
                    total_value=d.total_value,
                    average_value=d.average_value,
                    min_value=d.min_value,
                    max_value=d.max_value,
                    count=d.count,
                    duration_minutes=d.duration_minutes,
                    unit=d.unit,
                    notes=d.notes,
                    workout_breakdown=workout_breakdown
                )
                data_points.append(data_point)
            
            metric_summary = HealthKitMetricSummary(
                metric_type=metric_type,
                unit=latest.unit,
                latest_value=latest.value,
                latest_date=latest.start_date,
                data_points=data_points
            )
            metrics.append(metric_summary)
    
    return HealthKitDashboard(
        user_id=current_user.id,
        last_sync=sync_status.last_successful_sync,
        metrics=metrics
    )

@router.get("/charts/{metric_type}", response_model=ChartData)
def get_metric_chart_data(
    metric_type: HealthKitMetricType,
    granularity: TimeGranularity = Query(TimeGranularity.DAILY),
    days: int = Query(30, description="Number of days to look back"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get chart data for a specific metric type"""
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Get data based on granularity
    if granularity == TimeGranularity.DAILY:
        data = HealthKitCRUD.get_daily_aggregates(db, current_user.id, metric_type, start_date, end_date)
        chart_points = [
            ChartDataPoint(
                date=d.date.isoformat(),
                value=d.average_value or d.total_value or 0,
                label=d.notes
            ) for d in data
        ]
    elif granularity == TimeGranularity.WEEKLY:
        data = HealthKitCRUD.get_weekly_aggregates(db, current_user.id, metric_type, start_date, end_date)
        chart_points = [
            ChartDataPoint(
                date=d.week_start_date.isoformat() if d.week_start_date else "",
                value=d.average_value or d.total_value or 0,
                label=d.notes
            ) for d in data
        ]
    elif granularity == TimeGranularity.MONTHLY:
        data = HealthKitCRUD.get_monthly_aggregates(db, current_user.id, metric_type, start_date.year, end_date.year)
        chart_points = [
            ChartDataPoint(
                date=f"{d.year}-{d.month:02d}-01",
                value=d.average_value or d.total_value or 0,
                label=d.notes
            ) for d in data
        ]
    else:
        chart_points = []
    
    # Calculate chart metadata
    values = [p.value for p in chart_points if p.value > 0]
    unit = data[0].unit if data else ""
    
    return ChartData(
        metric_type=metric_type,
        unit=unit,
        granularity=granularity,
        data_points=chart_points,
        min_value=min(values) if values else None,
        max_value=max(values) if values else None,
        average_value=sum(values) / len(values) if values else None,
        total_value=sum(values) if values else None
    )

@router.get("/charts/multi", response_model=HealthMetricsChartsResponse)
def get_multiple_metric_charts(
    metric_types: List[HealthKitMetricType] = Query(...),
    granularity: TimeGranularity = Query(TimeGranularity.DAILY),
    days: int = Query(30),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get chart data for multiple metric types"""
    
    charts = []
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    for metric_type in metric_types:
        # Get chart data for each metric
        chart_data = get_metric_chart_data(
            metric_type, granularity, days, db, current_user
        )
        charts.append(chart_data)
    
    return HealthMetricsChartsResponse(
        user_id=current_user.id,
        charts=charts,
        date_range={
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }
    )

@router.get("/sync-status", response_model=HealthKitSyncStatusResponse)
def get_sync_status(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get HealthKit sync status for current user"""
    
    sync_status = HealthKitCRUD.get_or_create_sync_status(db, current_user.id)
    
    return HealthKitSyncStatusResponse(
        user_id=current_user.id,
        sync_enabled=sync_status.sync_enabled,
        last_sync_date=sync_status.last_sync_date,
        last_successful_sync=sync_status.last_successful_sync,
        last_error=sync_status.last_error,
        error_count=sync_status.error_count
    )

@router.post("/enable-sync")
def enable_sync(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Enable HealthKit sync for current user"""
    
    sync_status = HealthKitCRUD.get_or_create_sync_status(db, current_user.id)
    sync_status.sync_enabled = "true"
    db.commit()
    
    return {"message": "HealthKit sync enabled"}

@router.post("/disable-sync")
def disable_sync(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Disable HealthKit sync for current user"""
    
    sync_status = HealthKitCRUD.get_or_create_sync_status(db, current_user.id)
    sync_status.sync_enabled = "false"
    db.commit()
    
    return {"message": "HealthKit sync disabled"}

@router.get("/metrics/latest")
def get_latest_metrics(
    metric_types: List[HealthKitMetricType] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get latest values for specified metrics"""
    
    latest_data = HealthKitCRUD.get_latest_data_by_metric(db, current_user.id)
    
    # Filter by requested metric types if specified
    if metric_types:
        filtered_data = {k: v for k, v in latest_data.items() if k in metric_types}
    else:
        filtered_data = latest_data
    
    return {
        "user_id": current_user.id,
        "latest_metrics": {
            metric_type.value: {
                "value": data.value,
                "unit": data.unit,
                "date": data.start_date,
                "notes": data.notes
            } for metric_type, data in filtered_data.items()
        }
    } 