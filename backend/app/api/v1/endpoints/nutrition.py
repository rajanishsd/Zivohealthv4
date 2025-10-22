from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from app.utils.timezone import now_local, today_local

from app.api import deps
from app.crud import nutrition as crud_nutrition
from app.schemas.nutrition import (
    NutritionDataCreate,
    NutritionDataResponse,
    NutritionChartData,
    NutritionChartDataPoint,
    NutritionQueryParams,
    TimeGranularity,
    MealType,
    NutritionDataSource
)
from app.models.user import User
from app.models.nutrition_data import NutritionSyncStatus
from app.utils.sqs_client import get_ml_worker_client
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/data", response_model=NutritionDataResponse)
def create_nutrition_data(
    *,
    db: Session = Depends(deps.get_db),
    nutrition_in: NutritionDataCreate,
    current_user: User = Depends(deps.get_current_active_user)
):
    """Create new nutrition data entry"""
    try:
        nutrition_data = crud_nutrition.nutrition_data.create_with_user(
            db=db, obj_in=nutrition_in, user_id=current_user.id
        )
        
        # Update sync status to track the submission
        crud_nutrition.nutrition_sync_status.update_sync_status(
            db=db,
            user_id=current_user.id,
            data_source=nutrition_in.data_source,
            last_sync_date=now_local(),
            success=True,
            error_message=None
        )
        
        # Trigger ML worker via SQS to process pending nutrition (post-commit)
        try:
            ml_worker_client = get_ml_worker_client()
            if ml_worker_client.is_enabled():
                ml_worker_client.send_nutrition_processing_trigger(user_id=current_user.id, priority='normal')
        except Exception as e:
            # Non-fatal if background trigger fails
            logger.warning(f"⚠️  Failed to trigger ML worker for nutrition: {e}")
            pass
        return nutrition_data
        
    except Exception as e:
        # Update sync status to track the failure
        try:
            crud_nutrition.nutrition_sync_status.update_sync_status(
                db=db,
                user_id=current_user.id,
                data_source=nutrition_in.data_source,
                last_sync_date=now_local(),
                success=False,
                error_message=str(e)
            )
        except Exception as sync_error:
            # Log sync error but don't fail the main operation
            pass
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create nutrition data: {str(e)}"
        )

@router.get("/data", response_model=List[NutritionDataResponse])
def read_nutrition_data(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    start_date: Optional[date] = Query(None, description="Start date for filtering"),
    end_date: Optional[date] = Query(None, description="End date for filtering"),
    meal_type: Optional[MealType] = Query(None, description="Filter by meal type"),
    data_source: Optional[NutritionDataSource] = Query(None, description="Filter by data source"),
    granularity: TimeGranularity = Query(TimeGranularity.DAILY, description="Data granularity"),
    limit: int = Query(100, ge=1, le=1000, description="Limit number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Retrieve nutrition data with filtering options"""
    params = NutritionQueryParams(
        start_date=start_date,
        end_date=end_date,
        meal_type=meal_type,
        data_source=data_source,
        granularity=granularity,
        limit=limit,
        offset=offset
    )
    
    nutrition_data = crud_nutrition.nutrition_data.get_multi_by_user(
        db=db, user_id=current_user.id, params=params
    )
    return nutrition_data

@router.get("/chart", response_model=NutritionChartData)
def get_nutrition_chart_data(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    start_date: Optional[date] = Query(None, description="Start date for chart data"),
    end_date: Optional[date] = Query(None, description="End date for chart data"),
    granularity: TimeGranularity = Query(TimeGranularity.DAILY, description="Chart granularity")
):
    """Get nutrition data formatted for charts"""
    # Default to last 30 days if no dates provided
    if not end_date:
        end_date = today_local()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Get aggregated data based on granularity
    if granularity == TimeGranularity.DAILY:
        aggregates = crud_nutrition.nutrition_daily_aggregate.get_by_user_date_range(
            db=db, user_id=current_user.id, start_date=start_date, end_date=end_date
        )
        
        # Convert to chart data points
        data_points = []
        for aggregate in aggregates:
            data_points.append(NutritionChartDataPoint(
                date=aggregate.date,
                calories=aggregate.total_calories,
                protein_g=aggregate.total_protein_g,
                fat_g=aggregate.total_fat_g,
                carbs_g=aggregate.total_carbs_g,
                fiber_g=aggregate.total_fiber_g,
                sugar_g=aggregate.total_sugar_g,
                sodium_mg=aggregate.total_sodium_mg,
                meal_count=aggregate.meal_count,
                # Vitamins
                vitamin_a_mcg=getattr(aggregate, 'total_vitamin_a_mcg', 0.0),
                vitamin_c_mg=getattr(aggregate, 'total_vitamin_c_mg', 0.0),
                vitamin_d_mcg=getattr(aggregate, 'total_vitamin_d_mcg', 0.0),
                vitamin_e_mg=getattr(aggregate, 'total_vitamin_e_mg', 0.0),
                vitamin_k_mcg=getattr(aggregate, 'total_vitamin_k_mcg', 0.0),
                vitamin_b1_mg=getattr(aggregate, 'total_vitamin_b1_mg', 0.0),
                vitamin_b2_mg=getattr(aggregate, 'total_vitamin_b2_mg', 0.0),
                vitamin_b3_mg=getattr(aggregate, 'total_vitamin_b3_mg', 0.0),
                vitamin_b6_mg=getattr(aggregate, 'total_vitamin_b6_mg', 0.0),
                vitamin_b12_mcg=getattr(aggregate, 'total_vitamin_b12_mcg', 0.0),
                folate_mcg=getattr(aggregate, 'total_folate_mcg', 0.0),
                # Minerals
                calcium_mg=getattr(aggregate, 'total_calcium_mg', 0.0),
                iron_mg=getattr(aggregate, 'total_iron_mg', 0.0),
                magnesium_mg=getattr(aggregate, 'total_magnesium_mg', 0.0),
                phosphorus_mg=getattr(aggregate, 'total_phosphorus_mg', 0.0),
                potassium_mg=getattr(aggregate, 'total_potassium_mg', 0.0),
                zinc_mg=getattr(aggregate, 'total_zinc_mg', 0.0),
                copper_mg=getattr(aggregate, 'total_copper_mg', 0.0),
                manganese_mg=getattr(aggregate, 'total_manganese_mg', 0.0),
                selenium_mcg=getattr(aggregate, 'total_selenium_mcg', 0.0)
            ))
    elif granularity == TimeGranularity.WEEKLY:
        aggregates = crud_nutrition.nutrition_weekly_aggregate.get_by_user_date_range(
            db=db, user_id=current_user.id, start_date=start_date, end_date=end_date
        )
        
        # Convert to chart data points
        data_points = []
        for aggregate in aggregates:
            data_points.append(NutritionChartDataPoint(
                date=aggregate.week_start_date,
                calories=aggregate.avg_daily_calories,
                protein_g=aggregate.avg_daily_protein_g,
                fat_g=aggregate.avg_daily_fat_g,
                carbs_g=aggregate.avg_daily_carbs_g,
                fiber_g=aggregate.avg_daily_fiber_g,
                sugar_g=aggregate.avg_daily_sugar_g,
                sodium_mg=aggregate.avg_daily_sodium_mg,
                meal_count=aggregate.total_weekly_meals,
                # Vitamins
                vitamin_a_mcg=getattr(aggregate, 'avg_daily_vitamin_a_mcg', 0.0),
                vitamin_c_mg=getattr(aggregate, 'avg_daily_vitamin_c_mg', 0.0),
                vitamin_d_mcg=getattr(aggregate, 'avg_daily_vitamin_d_mcg', 0.0),
                vitamin_e_mg=getattr(aggregate, 'avg_daily_vitamin_e_mg', 0.0),
                vitamin_k_mcg=getattr(aggregate, 'avg_daily_vitamin_k_mcg', 0.0),
                vitamin_b1_mg=getattr(aggregate, 'avg_daily_vitamin_b1_mg', 0.0),
                vitamin_b2_mg=getattr(aggregate, 'avg_daily_vitamin_b2_mg', 0.0),
                vitamin_b3_mg=getattr(aggregate, 'avg_daily_vitamin_b3_mg', 0.0),
                vitamin_b6_mg=getattr(aggregate, 'avg_daily_vitamin_b6_mg', 0.0),
                vitamin_b12_mcg=getattr(aggregate, 'avg_daily_vitamin_b12_mcg', 0.0),
                folate_mcg=getattr(aggregate, 'avg_daily_folate_mcg', 0.0),
                # Minerals
                calcium_mg=getattr(aggregate, 'avg_daily_calcium_mg', 0.0),
                iron_mg=getattr(aggregate, 'avg_daily_iron_mg', 0.0),
                magnesium_mg=getattr(aggregate, 'avg_daily_magnesium_mg', 0.0),
                phosphorus_mg=getattr(aggregate, 'avg_daily_phosphorus_mg', 0.0),
                potassium_mg=getattr(aggregate, 'avg_daily_potassium_mg', 0.0),
                zinc_mg=getattr(aggregate, 'avg_daily_zinc_mg', 0.0),
                copper_mg=getattr(aggregate, 'avg_daily_copper_mg', 0.0),
                manganese_mg=getattr(aggregate, 'avg_daily_manganese_mg', 0.0),
                selenium_mcg=getattr(aggregate, 'avg_daily_selenium_mcg', 0.0)
            ))
    elif granularity == TimeGranularity.MONTHLY:
        aggregates = crud_nutrition.nutrition_monthly_aggregate.get_by_user_date_range(
            db=db, user_id=current_user.id, start_date=start_date, end_date=end_date
        )
        
        # Convert to chart data points
        data_points = []
        for aggregate in aggregates:
            # Create a date from year and month (first day of month)
            month_date = date(aggregate.year, aggregate.month, 1)
            data_points.append(NutritionChartDataPoint(
                date=month_date,
                calories=aggregate.avg_daily_calories,
                protein_g=aggregate.avg_daily_protein_g,
                fat_g=aggregate.avg_daily_fat_g,
                carbs_g=aggregate.avg_daily_carbs_g,
                fiber_g=aggregate.avg_daily_fiber_g,
                sugar_g=aggregate.avg_daily_sugar_g,
                sodium_mg=aggregate.avg_daily_sodium_mg,
                meal_count=aggregate.total_monthly_meals,
                # Vitamins
                vitamin_a_mcg=getattr(aggregate, 'avg_daily_vitamin_a_mcg', 0.0),
                vitamin_c_mg=getattr(aggregate, 'avg_daily_vitamin_c_mg', 0.0),
                vitamin_d_mcg=getattr(aggregate, 'avg_daily_vitamin_d_mcg', 0.0),
                vitamin_e_mg=getattr(aggregate, 'avg_daily_vitamin_e_mg', 0.0),
                vitamin_k_mcg=getattr(aggregate, 'avg_daily_vitamin_k_mcg', 0.0),
                vitamin_b1_mg=getattr(aggregate, 'avg_daily_vitamin_b1_mg', 0.0),
                vitamin_b2_mg=getattr(aggregate, 'avg_daily_vitamin_b2_mg', 0.0),
                vitamin_b3_mg=getattr(aggregate, 'avg_daily_vitamin_b3_mg', 0.0),
                vitamin_b6_mg=getattr(aggregate, 'avg_daily_vitamin_b6_mg', 0.0),
                vitamin_b12_mcg=getattr(aggregate, 'avg_daily_vitamin_b12_mcg', 0.0),
                folate_mcg=getattr(aggregate, 'avg_daily_folate_mcg', 0.0),
                # Minerals
                calcium_mg=getattr(aggregate, 'avg_daily_calcium_mg', 0.0),
                iron_mg=getattr(aggregate, 'avg_daily_iron_mg', 0.0),
                magnesium_mg=getattr(aggregate, 'avg_daily_magnesium_mg', 0.0),
                phosphorus_mg=getattr(aggregate, 'avg_daily_phosphorus_mg', 0.0),
                potassium_mg=getattr(aggregate, 'avg_daily_potassium_mg', 0.0),
                zinc_mg=getattr(aggregate, 'avg_daily_zinc_mg', 0.0),
                copper_mg=getattr(aggregate, 'avg_daily_copper_mg', 0.0),
                manganese_mg=getattr(aggregate, 'avg_daily_manganese_mg', 0.0),
                selenium_mcg=getattr(aggregate, 'avg_daily_selenium_mcg', 0.0)
            ))
    else:
        # Fallback to empty data
        data_points = []
    
    # Calculate summary statistics
    total_days = len(data_points)
    total_meals = sum(dp.meal_count for dp in data_points)
    
    # Macronutrients
    avg_daily_calories = sum(dp.calories for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_protein_g = sum(dp.protein_g for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_fat_g = sum(dp.fat_g for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_carbs_g = sum(dp.carbs_g for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_fiber_g = sum(dp.fiber_g for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_sugar_g = sum(dp.sugar_g for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_sodium_mg = sum(dp.sodium_mg for dp in data_points) / total_days if total_days > 0 else 0
    
    # Vitamins
    avg_daily_vitamin_a_mcg = sum(dp.vitamin_a_mcg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_vitamin_c_mg = sum(dp.vitamin_c_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_vitamin_d_mcg = sum(dp.vitamin_d_mcg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_vitamin_e_mg = sum(dp.vitamin_e_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_vitamin_k_mcg = sum(dp.vitamin_k_mcg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_vitamin_b1_mg = sum(dp.vitamin_b1_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_vitamin_b2_mg = sum(dp.vitamin_b2_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_vitamin_b3_mg = sum(dp.vitamin_b3_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_vitamin_b6_mg = sum(dp.vitamin_b6_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_vitamin_b12_mcg = sum(dp.vitamin_b12_mcg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_folate_mcg = sum(dp.folate_mcg for dp in data_points) / total_days if total_days > 0 else 0
    
    # Minerals
    avg_daily_calcium_mg = sum(dp.calcium_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_iron_mg = sum(dp.iron_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_magnesium_mg = sum(dp.magnesium_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_phosphorus_mg = sum(dp.phosphorus_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_potassium_mg = sum(dp.potassium_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_zinc_mg = sum(dp.zinc_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_copper_mg = sum(dp.copper_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_manganese_mg = sum(dp.manganese_mg for dp in data_points) / total_days if total_days > 0 else 0
    avg_daily_selenium_mcg = sum(dp.selenium_mcg for dp in data_points) / total_days if total_days > 0 else 0
    
    return NutritionChartData(
        data_points=data_points,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        total_days=total_days,
        # Macronutrients
        avg_daily_calories=avg_daily_calories,
        avg_daily_protein_g=avg_daily_protein_g,
        avg_daily_fat_g=avg_daily_fat_g,
        avg_daily_carbs_g=avg_daily_carbs_g,
        avg_daily_fiber_g=avg_daily_fiber_g,
        avg_daily_sugar_g=avg_daily_sugar_g,
        avg_daily_sodium_mg=avg_daily_sodium_mg,
        # Vitamins
        avg_daily_vitamin_a_mcg=avg_daily_vitamin_a_mcg,
        avg_daily_vitamin_c_mg=avg_daily_vitamin_c_mg,
        avg_daily_vitamin_d_mcg=avg_daily_vitamin_d_mcg,
        avg_daily_vitamin_e_mg=avg_daily_vitamin_e_mg,
        avg_daily_vitamin_k_mcg=avg_daily_vitamin_k_mcg,
        avg_daily_vitamin_b1_mg=avg_daily_vitamin_b1_mg,
        avg_daily_vitamin_b2_mg=avg_daily_vitamin_b2_mg,
        avg_daily_vitamin_b3_mg=avg_daily_vitamin_b3_mg,
        avg_daily_vitamin_b6_mg=avg_daily_vitamin_b6_mg,
        avg_daily_vitamin_b12_mcg=avg_daily_vitamin_b12_mcg,
        avg_daily_folate_mcg=avg_daily_folate_mcg,
        # Minerals
        avg_daily_calcium_mg=avg_daily_calcium_mg,
        avg_daily_iron_mg=avg_daily_iron_mg,
        avg_daily_magnesium_mg=avg_daily_magnesium_mg,
        avg_daily_phosphorus_mg=avg_daily_phosphorus_mg,
        avg_daily_potassium_mg=avg_daily_potassium_mg,
        avg_daily_zinc_mg=avg_daily_zinc_mg,
        avg_daily_copper_mg=avg_daily_copper_mg,
        avg_daily_manganese_mg=avg_daily_manganese_mg,
        avg_daily_selenium_mcg=avg_daily_selenium_mcg,
        total_meals=total_meals
    )

@router.get("/{nutrition_id}", response_model=NutritionDataResponse)
def read_nutrition_data_by_id(
    *,
    db: Session = Depends(deps.get_db),
    nutrition_id: int,
    current_user: User = Depends(deps.get_current_active_user)
):
    """Get specific nutrition data by ID"""
    nutrition_data = crud_nutrition.nutrition_data.get(db=db, id=nutrition_id)
    if not nutrition_data:
        raise HTTPException(status_code=404, detail="Nutrition data not found")
    if nutrition_data.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return nutrition_data

@router.delete("/{nutrition_id}")
def delete_nutrition_data(
    *,
    db: Session = Depends(deps.get_db),
    nutrition_id: int,
    current_user: User = Depends(deps.get_current_active_user)
):
    """Delete nutrition data entry"""
    nutrition_data = crud_nutrition.nutrition_data.get(db=db, id=nutrition_id)
    if not nutrition_data:
        raise HTTPException(status_code=404, detail="Nutrition data not found")
    
    if nutrition_data.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    crud_nutrition.nutrition_data.remove(db=db, id=nutrition_id)
    return {"message": "Nutrition data deleted successfully"}


# MARK: - Sync Status Management Endpoints

@router.get("/sync-status/{data_source}")
def get_nutrition_sync_status(
    data_source: NutritionDataSource,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db)
):
    """Get nutrition sync status for a specific data source"""
    try:
        sync_status = crud_nutrition.nutrition_sync_status.get_sync_status(
            db, current_user.id, data_source
        )
        
        if not sync_status:
            # Create default sync status
            sync_status = NutritionSyncStatus(
                user_id=current_user.id,
                data_source=data_source,
                sync_enabled="false"
            )
        
        return {
            "user_id": current_user.id,
            "data_source": data_source,
            "sync_enabled": sync_status.sync_enabled,
            "last_sync_date": sync_status.last_sync_date,
            "last_successful_sync": sync_status.last_successful_sync,
            "last_error": sync_status.last_error,
            "error_count": sync_status.error_count or 0
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get nutrition sync status: {str(e)}"
        )


@router.post("/sync-status/{data_source}/enable")
def enable_nutrition_sync(
    data_source: NutritionDataSource,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db)
):
    """Enable nutrition sync for a specific data source"""
    try:
        sync_status = crud_nutrition.nutrition_sync_status.enable_sync(
            db, current_user.id, data_source
        )
        
        return {"message": f"Nutrition sync enabled for {data_source}"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enable nutrition sync: {str(e)}"
        )


@router.post("/sync-status/{data_source}/disable")
def disable_nutrition_sync(
    data_source: NutritionDataSource,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db)
):
    """Disable nutrition sync for a specific data source"""
    try:
        sync_status = crud_nutrition.nutrition_sync_status.disable_sync(
            db, current_user.id, data_source
        )
        
        return {"message": f"Nutrition sync disabled for {data_source}"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disable nutrition sync: {str(e)}"
        )
