from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, asc, String
from datetime import datetime, date, timedelta
import json

from app.crud.base import CRUDBase
from app.models.nutrition_data import (
    NutritionRawData, 
    NutritionDailyAggregate, 
    NutritionWeeklyAggregate, 
    NutritionMonthlyAggregate,
    NutritionSyncStatus,
    NutritionDataSource,
    MealType
)
from app.schemas.nutrition import (
    NutritionDataCreate, 
    NutritionDataUpdate,
    NutritionQueryParams,
    TimeGranularity
)

class CRUDNutritionData(CRUDBase[NutritionRawData, NutritionDataCreate, NutritionDataUpdate]):
    """CRUD operations for nutrition raw data"""
    
    def create_with_user(self, db: Session, *, obj_in: NutritionDataCreate, user_id: int) -> NutritionRawData:
        """Create nutrition data with user ID"""
        obj_in_data = obj_in.dict()
        obj_in_data["user_id"] = user_id
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_multi_by_user(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        params: NutritionQueryParams
    ) -> List[NutritionRawData]:
        """Get multiple nutrition records by user with filtering"""
        query = db.query(self.model).filter(self.model.user_id == user_id)
        
        # Apply filters
        if params.start_date:
            query = query.filter(self.model.meal_date >= params.start_date)
        if params.end_date:
            query = query.filter(self.model.meal_date <= params.end_date)
        if params.meal_type:
            query = query.filter(self.model.meal_type == params.meal_type.value)
        if params.data_source:
            query = query.filter(self.model.data_source == params.data_source.value)
        
        # Order by meal_time descending
        query = query.order_by(desc(self.model.meal_time))
        
        # Apply pagination
        if params.offset:
            query = query.offset(params.offset)
        if params.limit:
            query = query.limit(params.limit)
        
        return query.all()
        
    def get_pending_aggregation_entries(self, db: Session, limit: int = 1000) -> List[NutritionRawData]:
        """Get nutrition data pending aggregation"""
        return db.query(self.model).filter(
            self.model.aggregation_status == 'pending'
        ).limit(limit).all()
    
    def mark_as_aggregated(self, db: Session, *, record_ids: List[int]) -> int:
        """Mark records as aggregated"""
        updated_count = db.query(self.model).filter(
            self.model.id.in_(record_ids)
        ).update({
            "aggregation_status": "completed",
            "aggregated_at": datetime.utcnow()
        }, synchronize_session=False)
        
        db.commit()
        return updated_count

    def mark_aggregation_processing(self, db: Session, entry_ids: List[int]):
        """Mark entries as being processed for aggregation"""
        db.query(self.model).filter(
            self.model.id.in_(entry_ids)
        ).update({
            "aggregation_status": "processing",
            "updated_at": datetime.utcnow()
        }, synchronize_session=False)
        db.commit()

    def mark_aggregation_failed(self, db: Session, entry_ids: List[int], error_msg: str):
        """Mark entries as failed aggregation"""
        db.query(self.model).filter(
            self.model.id.in_(entry_ids)
        ).update({
            "aggregation_status": "failed",
            "notes": func.coalesce(self.model.notes, '') + f" | Aggregation failed: {error_msg}",
            "updated_at": datetime.utcnow()
        }, synchronize_session=False)
        db.commit()

    def get_aggregation_status_counts(self, db: Session, user_id: int) -> Dict[str, int]:
        """Get count of records by aggregation status for a user"""
        result = db.query(
            self.model.aggregation_status,
            func.count(self.model.id)
        ).filter(
            self.model.user_id == user_id
        ).group_by(self.model.aggregation_status).all()
        
        return {status: count for status, count in result}

    def aggregate_daily_data(self, db: Session, user_id: int, target_date: date) -> int:
        """Aggregate nutrition data for a specific user and date"""
        # Get all nutrition data for the target date that needs processing
        pending_data = db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.meal_date == target_date,
                self.model.aggregation_status.in_(["pending", "processing"])
            )
        ).all()

        if not pending_data:
            return 0
        
        # For accurate aggregation, get ALL records for the date (including completed ones)
        # This ensures we don't lose data when aggregation runs multiple times per day
        all_data = db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.meal_date == target_date
            )
        ).all()
        
        # Use all_data for calculations to ensure completeness
        raw_data = all_data

        # Calculate aggregated values
        total_calories = sum(record.calories for record in raw_data)
        total_protein_g = sum(record.protein_g for record in raw_data)
        total_fat_g = sum(record.fat_g for record in raw_data)
        total_carbs_g = sum(record.carbs_g for record in raw_data)
        total_fiber_g = sum(record.fiber_g for record in raw_data)
        total_sugar_g = sum(record.sugar_g for record in raw_data)
        total_sodium_mg = sum(record.sodium_mg for record in raw_data)
        
        # Calculate vitamin totals
        total_vitamin_a_mcg = sum(record.vitamin_a_mcg or 0 for record in raw_data)
        total_vitamin_c_mg = sum(record.vitamin_c_mg or 0 for record in raw_data)
        total_vitamin_d_mcg = sum(record.vitamin_d_mcg or 0 for record in raw_data)
        total_vitamin_e_mg = sum(record.vitamin_e_mg or 0 for record in raw_data)
        total_vitamin_k_mcg = sum(record.vitamin_k_mcg or 0 for record in raw_data)
        total_vitamin_b1_mg = sum(record.vitamin_b1_mg or 0 for record in raw_data)
        total_vitamin_b2_mg = sum(record.vitamin_b2_mg or 0 for record in raw_data)
        total_vitamin_b3_mg = sum(record.vitamin_b3_mg or 0 for record in raw_data)
        total_vitamin_b6_mg = sum(record.vitamin_b6_mg or 0 for record in raw_data)
        total_vitamin_b12_mcg = sum(record.vitamin_b12_mcg or 0 for record in raw_data)
        total_folate_mcg = sum(record.folate_mcg or 0 for record in raw_data)
        
        # Calculate mineral totals
        total_calcium_mg = sum(record.calcium_mg or 0 for record in raw_data)
        total_iron_mg = sum(record.iron_mg or 0 for record in raw_data)
        total_magnesium_mg = sum(record.magnesium_mg or 0 for record in raw_data)
        total_phosphorus_mg = sum(record.phosphorus_mg or 0 for record in raw_data)
        total_potassium_mg = sum(record.potassium_mg or 0 for record in raw_data)
        total_zinc_mg = sum(record.zinc_mg or 0 for record in raw_data)
        total_copper_mg = sum(record.copper_mg or 0 for record in raw_data)
        total_manganese_mg = sum(record.manganese_mg or 0 for record in raw_data)
        total_selenium_mcg = sum(record.selenium_mcg or 0 for record in raw_data)

        # Count meals by type
        meal_count = len(raw_data)
        breakfast_count = len([r for r in raw_data if r.meal_type == MealType.BREAKFAST.value])
        lunch_count = len([r for r in raw_data if r.meal_type == MealType.LUNCH.value])
        dinner_count = len([r for r in raw_data if r.meal_type == MealType.DINNER.value])
        snack_count = len([r for r in raw_data if r.meal_type == MealType.SNACK.value])

        # Calculate calories by meal type
        breakfast_calories = sum(r.calories for r in raw_data if r.meal_type == MealType.BREAKFAST.value)
        lunch_calories = sum(r.calories for r in raw_data if r.meal_type == MealType.LUNCH.value)
        dinner_calories = sum(r.calories for r in raw_data if r.meal_type == MealType.DINNER.value)
        snack_calories = sum(r.calories for r in raw_data if r.meal_type == MealType.SNACK.value)

        # Get most recent source
        latest_record = max(raw_data, key=lambda x: x.created_at)
        sources = list(set([r.data_source for r in raw_data]))

        # Check if daily aggregate already exists
        existing_aggregate = db.query(NutritionDailyAggregate).filter(
            and_(
                NutritionDailyAggregate.user_id == user_id,
                NutritionDailyAggregate.date == target_date
            )
        ).first()

        if existing_aggregate:
            # Update existing aggregate
            existing_aggregate.total_calories = total_calories
            existing_aggregate.total_protein_g = total_protein_g
            existing_aggregate.total_fat_g = total_fat_g
            existing_aggregate.total_carbs_g = total_carbs_g
            existing_aggregate.total_fiber_g = total_fiber_g
            existing_aggregate.total_sugar_g = total_sugar_g
            existing_aggregate.total_sodium_mg = total_sodium_mg
            existing_aggregate.total_vitamin_a_mcg = total_vitamin_a_mcg
            existing_aggregate.total_vitamin_c_mg = total_vitamin_c_mg
            existing_aggregate.total_vitamin_d_mcg = total_vitamin_d_mcg
            existing_aggregate.total_vitamin_e_mg = total_vitamin_e_mg
            existing_aggregate.total_vitamin_k_mcg = total_vitamin_k_mcg
            existing_aggregate.total_vitamin_b1_mg = total_vitamin_b1_mg
            existing_aggregate.total_vitamin_b2_mg = total_vitamin_b2_mg
            existing_aggregate.total_vitamin_b3_mg = total_vitamin_b3_mg
            existing_aggregate.total_vitamin_b6_mg = total_vitamin_b6_mg
            existing_aggregate.total_vitamin_b12_mcg = total_vitamin_b12_mcg
            existing_aggregate.total_folate_mcg = total_folate_mcg
            existing_aggregate.total_calcium_mg = total_calcium_mg
            existing_aggregate.total_iron_mg = total_iron_mg
            existing_aggregate.total_magnesium_mg = total_magnesium_mg
            existing_aggregate.total_phosphorus_mg = total_phosphorus_mg
            existing_aggregate.total_potassium_mg = total_potassium_mg
            existing_aggregate.total_zinc_mg = total_zinc_mg
            existing_aggregate.total_copper_mg = total_copper_mg
            existing_aggregate.total_manganese_mg = total_manganese_mg
            existing_aggregate.total_selenium_mcg = total_selenium_mcg
            existing_aggregate.meal_count = meal_count
            existing_aggregate.breakfast_count = breakfast_count
            existing_aggregate.lunch_count = lunch_count
            existing_aggregate.dinner_count = dinner_count
            existing_aggregate.snack_count = snack_count
            existing_aggregate.breakfast_calories = breakfast_calories
            existing_aggregate.lunch_calories = lunch_calories
            existing_aggregate.dinner_calories = dinner_calories
            existing_aggregate.snack_calories = snack_calories
            existing_aggregate.primary_source = latest_record.data_source
            existing_aggregate.sources_included = json.dumps(sources)
            existing_aggregate.updated_at = datetime.utcnow()
        else:
            # Create new aggregate
            new_aggregate = NutritionDailyAggregate(
                user_id=user_id,
                date=target_date,
                total_calories=total_calories,
                total_protein_g=total_protein_g,
                total_fat_g=total_fat_g,
                total_carbs_g=total_carbs_g,
                total_fiber_g=total_fiber_g,
                total_sugar_g=total_sugar_g,
                total_sodium_mg=total_sodium_mg,
                total_vitamin_a_mcg=total_vitamin_a_mcg,
                total_vitamin_c_mg=total_vitamin_c_mg,
                total_vitamin_d_mcg=total_vitamin_d_mcg,
                total_vitamin_e_mg=total_vitamin_e_mg,
                total_vitamin_k_mcg=total_vitamin_k_mcg,
                total_vitamin_b1_mg=total_vitamin_b1_mg,
                total_vitamin_b2_mg=total_vitamin_b2_mg,
                total_vitamin_b3_mg=total_vitamin_b3_mg,
                total_vitamin_b6_mg=total_vitamin_b6_mg,
                total_vitamin_b12_mcg=total_vitamin_b12_mcg,
                total_folate_mcg=total_folate_mcg,
                total_calcium_mg=total_calcium_mg,
                total_iron_mg=total_iron_mg,
                total_magnesium_mg=total_magnesium_mg,
                total_phosphorus_mg=total_phosphorus_mg,
                total_potassium_mg=total_potassium_mg,
                total_zinc_mg=total_zinc_mg,
                total_copper_mg=total_copper_mg,
                total_manganese_mg=total_manganese_mg,
                total_selenium_mcg=total_selenium_mcg,
                meal_count=meal_count,
                breakfast_count=breakfast_count,
                lunch_count=lunch_count,
                dinner_count=dinner_count,
                snack_count=snack_count,
                breakfast_calories=breakfast_calories,
                lunch_calories=lunch_calories,
                dinner_calories=dinner_calories,
                snack_calories=snack_calories,
                primary_source=latest_record.data_source,
                sources_included=json.dumps(sources)
            )
            db.add(new_aggregate)

        # Mark only the pending data as aggregated (don't re-mark completed records)
        pending_record_ids = [record.id for record in pending_data]
        self.mark_as_aggregated(db, record_ids=pending_record_ids)

        db.commit()
        return 1  # One daily aggregate created/updated

    def aggregate_weekly_data(self, db: Session, user_id: int, week_start_date: date) -> int:
        """Aggregate nutrition data for a specific user and week"""
        week_end_date = week_start_date + timedelta(days=6)
        
        # Get daily aggregates for the week
        daily_aggregates = db.query(NutritionDailyAggregate).filter(
            and_(
                NutritionDailyAggregate.user_id == user_id,
                NutritionDailyAggregate.date >= week_start_date,
                NutritionDailyAggregate.date <= week_end_date
            )
        ).all()

        if not daily_aggregates:
            return 0

        # Calculate weekly averages and totals
        days_with_data = len(daily_aggregates)
        total_weekly_calories = sum(agg.total_calories for agg in daily_aggregates)
        total_weekly_meals = sum(agg.meal_count for agg in daily_aggregates)
        
        avg_daily_calories = total_weekly_calories / days_with_data if days_with_data > 0 else 0
        avg_daily_protein_g = sum(agg.total_protein_g for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_fat_g = sum(agg.total_fat_g for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_carbs_g = sum(agg.total_carbs_g for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_fiber_g = sum(agg.total_fiber_g for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_sugar_g = sum(agg.total_sugar_g for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_sodium_mg = sum(agg.total_sodium_mg for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        
        # Calculate average daily vitamins
        avg_daily_vitamin_a_mcg = sum(getattr(agg, 'total_vitamin_a_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_c_mg = sum(getattr(agg, 'total_vitamin_c_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_d_mcg = sum(getattr(agg, 'total_vitamin_d_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_e_mg = sum(getattr(agg, 'total_vitamin_e_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_k_mcg = sum(getattr(agg, 'total_vitamin_k_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_b1_mg = sum(getattr(agg, 'total_vitamin_b1_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_b2_mg = sum(getattr(agg, 'total_vitamin_b2_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_b3_mg = sum(getattr(agg, 'total_vitamin_b3_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_b6_mg = sum(getattr(agg, 'total_vitamin_b6_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_b12_mcg = sum(getattr(agg, 'total_vitamin_b12_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_folate_mcg = sum(getattr(agg, 'total_folate_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        
        # Calculate average daily minerals
        avg_daily_calcium_mg = sum(getattr(agg, 'total_calcium_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_iron_mg = sum(getattr(agg, 'total_iron_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_magnesium_mg = sum(getattr(agg, 'total_magnesium_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_phosphorus_mg = sum(getattr(agg, 'total_phosphorus_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_potassium_mg = sum(getattr(agg, 'total_potassium_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_zinc_mg = sum(getattr(agg, 'total_zinc_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_copper_mg = sum(getattr(agg, 'total_copper_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_manganese_mg = sum(getattr(agg, 'total_manganese_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_selenium_mcg = sum(getattr(agg, 'total_selenium_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0

        # Get most recent source
        latest_aggregate = max(daily_aggregates, key=lambda x: x.updated_at)
        sources = list(set([agg.primary_source for agg in daily_aggregates if agg.primary_source]))

        # Check if weekly aggregate already exists
        existing_aggregate = db.query(NutritionWeeklyAggregate).filter(
            and_(
                NutritionWeeklyAggregate.user_id == user_id,
                NutritionWeeklyAggregate.week_start_date == week_start_date
            )
        ).first()

        if existing_aggregate:
            # Update existing aggregate
            existing_aggregate.week_end_date = week_end_date
            existing_aggregate.avg_daily_calories = avg_daily_calories
            existing_aggregate.avg_daily_protein_g = avg_daily_protein_g
            existing_aggregate.avg_daily_fat_g = avg_daily_fat_g
            existing_aggregate.avg_daily_carbs_g = avg_daily_carbs_g
            existing_aggregate.avg_daily_fiber_g = avg_daily_fiber_g
            existing_aggregate.avg_daily_sugar_g = avg_daily_sugar_g
            existing_aggregate.avg_daily_sodium_mg = avg_daily_sodium_mg
            existing_aggregate.total_weekly_calories = total_weekly_calories
            existing_aggregate.total_weekly_meals = total_weekly_meals
            existing_aggregate.days_with_data = days_with_data
            existing_aggregate.primary_source = latest_aggregate.primary_source
            existing_aggregate.sources_included = json.dumps(sources)
            existing_aggregate.updated_at = datetime.utcnow()
            
            # Update vitamin fields
            if hasattr(existing_aggregate, 'avg_daily_vitamin_a_mcg'):
                existing_aggregate.avg_daily_vitamin_a_mcg = avg_daily_vitamin_a_mcg
                existing_aggregate.avg_daily_vitamin_c_mg = avg_daily_vitamin_c_mg
                existing_aggregate.avg_daily_vitamin_d_mcg = avg_daily_vitamin_d_mcg
                existing_aggregate.avg_daily_vitamin_e_mg = avg_daily_vitamin_e_mg
                existing_aggregate.avg_daily_vitamin_k_mcg = avg_daily_vitamin_k_mcg
                existing_aggregate.avg_daily_vitamin_b1_mg = avg_daily_vitamin_b1_mg
                existing_aggregate.avg_daily_vitamin_b2_mg = avg_daily_vitamin_b2_mg
                existing_aggregate.avg_daily_vitamin_b3_mg = avg_daily_vitamin_b3_mg
                existing_aggregate.avg_daily_vitamin_b6_mg = avg_daily_vitamin_b6_mg
                existing_aggregate.avg_daily_vitamin_b12_mcg = avg_daily_vitamin_b12_mcg
                existing_aggregate.avg_daily_folate_mcg = avg_daily_folate_mcg
                
                # Update mineral fields
                existing_aggregate.avg_daily_calcium_mg = avg_daily_calcium_mg
                existing_aggregate.avg_daily_iron_mg = avg_daily_iron_mg
                existing_aggregate.avg_daily_magnesium_mg = avg_daily_magnesium_mg
                existing_aggregate.avg_daily_phosphorus_mg = avg_daily_phosphorus_mg
                existing_aggregate.avg_daily_potassium_mg = avg_daily_potassium_mg
                existing_aggregate.avg_daily_zinc_mg = avg_daily_zinc_mg
                existing_aggregate.avg_daily_copper_mg = avg_daily_copper_mg
                existing_aggregate.avg_daily_manganese_mg = avg_daily_manganese_mg
                existing_aggregate.avg_daily_selenium_mcg = avg_daily_selenium_mcg
        else:
            # Create new aggregate
            new_aggregate = NutritionWeeklyAggregate(
                user_id=user_id,
                week_start_date=week_start_date,
                week_end_date=week_end_date,
                avg_daily_calories=avg_daily_calories,
                avg_daily_protein_g=avg_daily_protein_g,
                avg_daily_fat_g=avg_daily_fat_g,
                avg_daily_carbs_g=avg_daily_carbs_g,
                avg_daily_fiber_g=avg_daily_fiber_g,
                avg_daily_sugar_g=avg_daily_sugar_g,
                avg_daily_sodium_mg=avg_daily_sodium_mg,
                total_weekly_calories=total_weekly_calories,
                total_weekly_meals=total_weekly_meals,
                days_with_data=days_with_data,
                primary_source=latest_aggregate.primary_source,
                sources_included=json.dumps(sources)
            )
            
            # Set vitamin and mineral fields if they exist
            if hasattr(new_aggregate, 'avg_daily_vitamin_a_mcg'):
                new_aggregate.avg_daily_vitamin_a_mcg = avg_daily_vitamin_a_mcg
                new_aggregate.avg_daily_vitamin_c_mg = avg_daily_vitamin_c_mg
                new_aggregate.avg_daily_vitamin_d_mcg = avg_daily_vitamin_d_mcg
                new_aggregate.avg_daily_vitamin_e_mg = avg_daily_vitamin_e_mg
                new_aggregate.avg_daily_vitamin_k_mcg = avg_daily_vitamin_k_mcg
                new_aggregate.avg_daily_vitamin_b1_mg = avg_daily_vitamin_b1_mg
                new_aggregate.avg_daily_vitamin_b2_mg = avg_daily_vitamin_b2_mg
                new_aggregate.avg_daily_vitamin_b3_mg = avg_daily_vitamin_b3_mg
                new_aggregate.avg_daily_vitamin_b6_mg = avg_daily_vitamin_b6_mg
                new_aggregate.avg_daily_vitamin_b12_mcg = avg_daily_vitamin_b12_mcg
                new_aggregate.avg_daily_folate_mcg = avg_daily_folate_mcg
                
                # Set mineral fields
                new_aggregate.avg_daily_calcium_mg = avg_daily_calcium_mg
                new_aggregate.avg_daily_iron_mg = avg_daily_iron_mg
                new_aggregate.avg_daily_magnesium_mg = avg_daily_magnesium_mg
                new_aggregate.avg_daily_phosphorus_mg = avg_daily_phosphorus_mg
                new_aggregate.avg_daily_potassium_mg = avg_daily_potassium_mg
                new_aggregate.avg_daily_zinc_mg = avg_daily_zinc_mg
                new_aggregate.avg_daily_copper_mg = avg_daily_copper_mg
                new_aggregate.avg_daily_manganese_mg = avg_daily_manganese_mg
                new_aggregate.avg_daily_selenium_mcg = avg_daily_selenium_mcg
            
            db.add(new_aggregate)

        db.commit()
        return 1  # One weekly aggregate created/updated

    def aggregate_monthly_data(self, db: Session, user_id: int, year: int, month: int) -> int:
        """Aggregate nutrition data for a specific user, year, and month"""
        # Get daily aggregates for the month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
            
        daily_aggregates = db.query(NutritionDailyAggregate).filter(
            and_(
                NutritionDailyAggregate.user_id == user_id,
                NutritionDailyAggregate.date >= start_date,
                NutritionDailyAggregate.date <= end_date
            )
        ).all()

        if not daily_aggregates:
            return 0

        # Calculate monthly averages and totals
        days_with_data = len(daily_aggregates)
        total_monthly_calories = sum(agg.total_calories for agg in daily_aggregates)
        total_monthly_meals = sum(agg.meal_count for agg in daily_aggregates)
        
        avg_daily_calories = total_monthly_calories / days_with_data if days_with_data > 0 else 0
        avg_daily_protein_g = sum(agg.total_protein_g for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_fat_g = sum(agg.total_fat_g for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_carbs_g = sum(agg.total_carbs_g for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_fiber_g = sum(agg.total_fiber_g for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_sugar_g = sum(agg.total_sugar_g for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_sodium_mg = sum(agg.total_sodium_mg for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        
        # Calculate average daily vitamins
        avg_daily_vitamin_a_mcg = sum(getattr(agg, 'total_vitamin_a_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_c_mg = sum(getattr(agg, 'total_vitamin_c_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_d_mcg = sum(getattr(agg, 'total_vitamin_d_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_e_mg = sum(getattr(agg, 'total_vitamin_e_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_k_mcg = sum(getattr(agg, 'total_vitamin_k_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_b1_mg = sum(getattr(agg, 'total_vitamin_b1_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_b2_mg = sum(getattr(agg, 'total_vitamin_b2_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_b3_mg = sum(getattr(agg, 'total_vitamin_b3_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_b6_mg = sum(getattr(agg, 'total_vitamin_b6_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_vitamin_b12_mcg = sum(getattr(agg, 'total_vitamin_b12_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_folate_mcg = sum(getattr(agg, 'total_folate_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        
        # Calculate average daily minerals
        avg_daily_calcium_mg = sum(getattr(agg, 'total_calcium_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_iron_mg = sum(getattr(agg, 'total_iron_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_magnesium_mg = sum(getattr(agg, 'total_magnesium_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_phosphorus_mg = sum(getattr(agg, 'total_phosphorus_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_potassium_mg = sum(getattr(agg, 'total_potassium_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_zinc_mg = sum(getattr(agg, 'total_zinc_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_copper_mg = sum(getattr(agg, 'total_copper_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_manganese_mg = sum(getattr(agg, 'total_manganese_mg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0
        avg_daily_selenium_mcg = sum(getattr(agg, 'total_selenium_mcg', 0) for agg in daily_aggregates) / days_with_data if days_with_data > 0 else 0

        # Get most recent source
        latest_aggregate = max(daily_aggregates, key=lambda x: x.updated_at)
        sources = list(set([agg.primary_source for agg in daily_aggregates if agg.primary_source]))

        # Check if monthly aggregate already exists
        existing_aggregate = db.query(NutritionMonthlyAggregate).filter(
            and_(
                NutritionMonthlyAggregate.user_id == user_id,
                NutritionMonthlyAggregate.year == year,
                NutritionMonthlyAggregate.month == month
            )
        ).first()

        if existing_aggregate:
            # Update existing aggregate
            existing_aggregate.avg_daily_calories = avg_daily_calories
            existing_aggregate.avg_daily_protein_g = avg_daily_protein_g
            existing_aggregate.avg_daily_fat_g = avg_daily_fat_g
            existing_aggregate.avg_daily_carbs_g = avg_daily_carbs_g
            existing_aggregate.avg_daily_fiber_g = avg_daily_fiber_g
            existing_aggregate.avg_daily_sugar_g = avg_daily_sugar_g
            existing_aggregate.avg_daily_sodium_mg = avg_daily_sodium_mg
            # Update vitamins
            existing_aggregate.avg_daily_vitamin_a_mcg = avg_daily_vitamin_a_mcg
            existing_aggregate.avg_daily_vitamin_c_mg = avg_daily_vitamin_c_mg
            existing_aggregate.avg_daily_vitamin_d_mcg = avg_daily_vitamin_d_mcg
            existing_aggregate.avg_daily_vitamin_e_mg = avg_daily_vitamin_e_mg
            existing_aggregate.avg_daily_vitamin_k_mcg = avg_daily_vitamin_k_mcg
            existing_aggregate.avg_daily_vitamin_b1_mg = avg_daily_vitamin_b1_mg
            existing_aggregate.avg_daily_vitamin_b2_mg = avg_daily_vitamin_b2_mg
            existing_aggregate.avg_daily_vitamin_b3_mg = avg_daily_vitamin_b3_mg
            existing_aggregate.avg_daily_vitamin_b6_mg = avg_daily_vitamin_b6_mg
            existing_aggregate.avg_daily_vitamin_b12_mcg = avg_daily_vitamin_b12_mcg
            existing_aggregate.avg_daily_folate_mcg = avg_daily_folate_mcg
            # Update minerals
            existing_aggregate.avg_daily_calcium_mg = avg_daily_calcium_mg
            existing_aggregate.avg_daily_iron_mg = avg_daily_iron_mg
            existing_aggregate.avg_daily_magnesium_mg = avg_daily_magnesium_mg
            existing_aggregate.avg_daily_phosphorus_mg = avg_daily_phosphorus_mg
            existing_aggregate.avg_daily_potassium_mg = avg_daily_potassium_mg
            existing_aggregate.avg_daily_zinc_mg = avg_daily_zinc_mg
            existing_aggregate.avg_daily_copper_mg = avg_daily_copper_mg
            existing_aggregate.avg_daily_manganese_mg = avg_daily_manganese_mg
            existing_aggregate.avg_daily_selenium_mcg = avg_daily_selenium_mcg
            # Update totals and metadata
            existing_aggregate.total_monthly_calories = total_monthly_calories
            existing_aggregate.total_monthly_meals = total_monthly_meals
            existing_aggregate.days_with_data = days_with_data
            existing_aggregate.primary_source = latest_aggregate.primary_source
            existing_aggregate.sources_included = json.dumps(sources)
            existing_aggregate.updated_at = datetime.utcnow()
        else:
            # Create new aggregate
            new_aggregate = NutritionMonthlyAggregate(
                user_id=user_id,
                year=year,
                month=month,
                avg_daily_calories=avg_daily_calories,
                avg_daily_protein_g=avg_daily_protein_g,
                avg_daily_fat_g=avg_daily_fat_g,
                avg_daily_carbs_g=avg_daily_carbs_g,
                avg_daily_fiber_g=avg_daily_fiber_g,
                avg_daily_sugar_g=avg_daily_sugar_g,
                avg_daily_sodium_mg=avg_daily_sodium_mg,
                # Add vitamins
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
                # Add minerals
                avg_daily_calcium_mg=avg_daily_calcium_mg,
                avg_daily_iron_mg=avg_daily_iron_mg,
                avg_daily_magnesium_mg=avg_daily_magnesium_mg,
                avg_daily_phosphorus_mg=avg_daily_phosphorus_mg,
                avg_daily_potassium_mg=avg_daily_potassium_mg,
                avg_daily_zinc_mg=avg_daily_zinc_mg,
                avg_daily_copper_mg=avg_daily_copper_mg,
                avg_daily_manganese_mg=avg_daily_manganese_mg,
                avg_daily_selenium_mcg=avg_daily_selenium_mcg,
                # Add totals and metadata
                total_monthly_calories=total_monthly_calories,
                total_monthly_meals=total_monthly_meals,
                days_with_data=days_with_data,
                primary_source=latest_aggregate.primary_source,
                sources_included=json.dumps(sources)
            )
            db.add(new_aggregate)

        db.commit()
        return 1  # One monthly aggregate created/updated

class CRUDNutritionDailyAggregate(CRUDBase[NutritionDailyAggregate, None, None]):
    """CRUD operations for nutrition daily aggregates"""
    
    def get_by_user_date_range(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        start_date: date, 
        end_date: date
    ) -> List[NutritionDailyAggregate]:
        """Get daily aggregates by user and date range"""
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.date >= start_date,
                self.model.date <= end_date
            )
        ).order_by(asc(self.model.date)).all()

class CRUDNutritionWeeklyAggregate(CRUDBase[NutritionWeeklyAggregate, None, None]):
    """CRUD operations for nutrition weekly aggregates"""
    
    def get_by_user_date_range(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        start_date: date, 
        end_date: date
    ) -> List[NutritionWeeklyAggregate]:
        """Get weekly aggregates by user and date range"""
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.week_start_date >= start_date,
                self.model.week_start_date <= end_date
            )
        ).order_by(asc(self.model.week_start_date)).all()

class CRUDNutritionMonthlyAggregate(CRUDBase[NutritionMonthlyAggregate, None, None]):
    """CRUD operations for nutrition monthly aggregates"""
    
    def get_by_user_date_range(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        start_date: date, 
        end_date: date
    ) -> List[NutritionMonthlyAggregate]:
        """Get monthly aggregates by user and date range"""
        # Convert dates to year/month for filtering
        start_year, start_month = start_date.year, start_date.month
        end_year, end_month = end_date.year, end_date.month
        
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                # Filter by year/month range
                func.concat(self.model.year, '-', 
                           func.lpad(self.model.month.cast(String), 2, '0')) >= 
                f"{start_year}-{start_month:02d}",
                func.concat(self.model.year, '-', 
                           func.lpad(self.model.month.cast(String), 2, '0')) <= 
                f"{end_year}-{end_month:02d}"
            )
        ).order_by(asc(self.model.year), asc(self.model.month)).all()

class CRUDNutritionSyncStatus:
    """CRUD operations for nutrition sync status"""
    
    @staticmethod
    def get_sync_status(db: Session, user_id: int, data_source: NutritionDataSource) -> Optional[NutritionSyncStatus]:
        """Get sync status for a user and data source"""
        return db.query(NutritionSyncStatus).filter(
            and_(
                NutritionSyncStatus.user_id == user_id,
                NutritionSyncStatus.data_source == data_source
            )
        ).first()
    
    @staticmethod
    def update_sync_status(
        db: Session,
        user_id: int,
        data_source: NutritionDataSource,
        last_sync_date: Optional[datetime] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> NutritionSyncStatus:
        """Update sync status for a user and data source"""
        sync_status = CRUDNutritionSyncStatus.get_sync_status(db, user_id, data_source)
        
        if not sync_status:
            sync_status = NutritionSyncStatus(
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
    def enable_sync(db: Session, user_id: int, data_source: NutritionDataSource) -> NutritionSyncStatus:
        """Enable sync for a user and data source"""
        sync_status = CRUDNutritionSyncStatus.get_sync_status(db, user_id, data_source)
        
        if not sync_status:
            sync_status = NutritionSyncStatus(
                user_id=user_id,
                data_source=data_source,
                sync_enabled="true"
            )
            db.add(sync_status)
        else:
            sync_status.sync_enabled = "true"
        
        sync_status.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(sync_status)
        return sync_status
    
    @staticmethod
    def disable_sync(db: Session, user_id: int, data_source: NutritionDataSource) -> NutritionSyncStatus:
        """Disable sync for a user and data source"""
        sync_status = CRUDNutritionSyncStatus.get_sync_status(db, user_id, data_source)
        
        if not sync_status:
            sync_status = NutritionSyncStatus(
                user_id=user_id,
                data_source=data_source,
                sync_enabled="false"
            )
            db.add(sync_status)
        else:
            sync_status.sync_enabled = "false"
        
        sync_status.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(sync_status)
        return sync_status

# Create instances
nutrition_data = CRUDNutritionData(NutritionRawData)
nutrition_daily_aggregate = CRUDNutritionDailyAggregate(NutritionDailyAggregate)
nutrition_weekly_aggregate = CRUDNutritionWeeklyAggregate(NutritionWeeklyAggregate)
nutrition_monthly_aggregate = CRUDNutritionMonthlyAggregate(NutritionMonthlyAggregate)
nutrition_sync_status = CRUDNutritionSyncStatus()
