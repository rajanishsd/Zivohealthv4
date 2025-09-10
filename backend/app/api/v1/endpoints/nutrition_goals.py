from typing import List, Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.crud import nutrition_goals as crud
from app.crud import nutrition as crud_nutrition
from app.models.nutrition_data import NutritionMealPlan
from app.models.nutrition_goals import UserNutrientFocus, NutritionGoal
from app.schemas.nutrition_goals import (
    NutritionObjectiveOut,
    NutrientCatalogOut,
    NutritionGoalOut,
    NutritionGoalTargetOut,
    NutritionGoalTargetNutrient,
    ActiveGoalSummaryOut,
    DefaultTargetOut,
    UserNutrientFocusOut,
    ProgressItemOut,
    ProgressResponseOut,
    NutritionGoalDetailOut,
)

router = APIRouter()


@router.get("/objectives", response_model=List[NutritionObjectiveOut])
def list_objectives(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    return crud.nutrition_objectives.list(db)


@router.get("/catalog", response_model=List[NutrientCatalogOut])
def list_catalog(
    enabled: bool = Query(True),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    return crud.nutrient_catalog.list(db, enabled_only=enabled)


@router.get("/current", response_model=ActiveGoalSummaryOut)
def get_current_goal_summary(
    response: Response,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    try:
        response.headers["X-NutritionGoals-Debug-Module"] = __name__
        response.headers["X-NutritionGoals-Debug-File"] = __file__
    except Exception:
        pass
    
    goal = crud.nutrition_goals.get_active_for_user(db, current_user.id)
    if not goal:
        return ActiveGoalSummaryOut(has_active_goal=False)

    primary = sum(1 for t in goal.targets if t.priority == "primary" and t.is_active)
    secondary = sum(1 for t in goal.targets if t.priority == "secondary" and t.is_active)
    timeframes = sorted(list({t.timeframe for t in goal.targets if t.is_active}))
    
    # Get focus nutrients for this goal
    focus_nutrients = crud.user_nutrient_focus.list_for_user(db, current_user.id)
    # Filter focus nutrients that belong to this specific goal
    # Handle both cases: goal_id is set or goal_id is None (backward compatibility)
    goal_focus_nutrients = [f for f in focus_nutrients if f.goal_id == goal.id or f.goal_id is None]

    # Create goal response with objective_code for backward compatibility
    goal_data = goal.__dict__.copy()
    goal_data['objective_code'] = goal.goal_name.lower().replace(' ', '_')  # Derive from goal name
    
    # Convert datetimes to date-only for mobile app compatibility (YYYY-MM-DD)
    if 'effective_at' in goal_data and goal_data['effective_at']:
        goal_data['effective_at'] = goal_data['effective_at'].date() if hasattr(goal_data['effective_at'], 'date') else goal_data['effective_at']
    if 'expires_at' in goal_data and goal_data['expires_at']:
        goal_data['expires_at'] = goal_data['expires_at'].date() if hasattr(goal_data['expires_at'], 'date') else goal_data['expires_at']
    
    response = ActiveGoalSummaryOut(
        has_active_goal=True,
        goal=NutritionGoalOut.model_validate(goal_data),
        targets_summary={
            "total": primary + secondary,
            "primary": primary,
            "secondary": secondary,
            "timeframes": timeframes,
        },
        focus_nutrients=[UserNutrientFocusOut(
            nutrient_id=f.nutrient_id,
            nutrient_key=f.nutrient.key,
            priority=f.priority,
            is_active=f.is_active,
        ) for f in goal_focus_nutrients],
    )
    return response


@router.get("/goals", response_model=List[NutritionGoalOut])
def list_goals(
    status: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    items = crud.nutrition_goals.list_for_user(db, current_user.id, status=status)
    # Add objective_code for backward compatibility and convert to date-only
    result = []
    for item in items:
        item_data = item.__dict__.copy()
        item_data['objective_code'] = item.goal_name.lower().replace(' ', '_')
        # Convert datetimes to date-only for mobile app compatibility (YYYY-MM-DD)
        if 'effective_at' in item_data and item_data['effective_at']:
            item_data['effective_at'] = item_data['effective_at'].date() if hasattr(item_data['effective_at'], 'date') else item_data['effective_at']
        if 'expires_at' in item_data and item_data['expires_at']:
            item_data['expires_at'] = item_data['expires_at'].date() if hasattr(item_data['expires_at'], 'date') else item_data['expires_at']
        result.append(NutritionGoalOut.model_validate(item_data))
    return result


@router.get("/goals/{goal_id}")
def get_goal_with_targets(
    goal_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    goal = crud.nutrition_goals.get_with_targets(db, goal_id, current_user.id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    targets: List[NutritionGoalTargetOut] = []
    for t in goal.targets:
        if not t.is_active:
            continue
        nutrient = t.nutrient
        targets.append(NutritionGoalTargetOut(
            id=t.id,
            timeframe=t.timeframe,
            target_type=t.target_type,
            target_min=t.target_min,
            target_max=t.target_max,
            priority=t.priority,
            is_active=t.is_active,
            nutrient=NutritionGoalTargetNutrient(id=nutrient.id, key=nutrient.key, display_name=nutrient.display_name, category=nutrient.category),
        ))

    # Add objective_code for backward compatibility and convert to date-only
    goal_data = goal.__dict__.copy()
    goal_data['objective_code'] = goal.goal_name.lower().replace(' ', '_')
    # Convert datetimes to date-only for mobile app compatibility (YYYY-MM-DD)
    if 'effective_at' in goal_data and goal_data['effective_at']:
        goal_data['effective_at'] = goal_data['effective_at'].date() if hasattr(goal_data['effective_at'], 'date') else goal_data['effective_at']
    if 'expires_at' in goal_data and goal_data['expires_at']:
        goal_data['expires_at'] = goal_data['expires_at'].date() if hasattr(goal_data['expires_at'], 'date') else goal_data['expires_at']
    
    return {
        "goal": NutritionGoalOut.model_validate(goal_data),
        "targets": targets,
    }


@router.get("/current/detail", response_model=NutritionGoalDetailOut)
def get_current_goal_detail(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    goal = crud.nutrition_goals.get_active_for_user(db, current_user.id)
    if not goal:
        raise HTTPException(status_code=404, detail="No active goal")

    # Build targets list with normalized target_type values
    targets: List[NutritionGoalTargetOut] = []
    for t in goal.targets:
        if not t.is_active:
            continue
        nutrient = t.nutrient
        # Normalize/derive effective target type when unexpected value (e.g., "daily")
        allowed_types = {"exact", "min", "max", "range"}
        effective_type = t.target_type if t.target_type in allowed_types else None
        if effective_type is None:
            if t.target_min is not None and t.target_max is not None:
                effective_type = "exact" if abs(t.target_max - t.target_min) < 1e-6 else "range"
            elif t.target_min is not None:
                effective_type = "min"
            elif t.target_max is not None:
                effective_type = "max"
        targets.append(NutritionGoalTargetOut(
            id=t.id,
            timeframe=t.timeframe,
            target_type=effective_type or t.target_type,
            target_min=t.target_min,
            target_max=t.target_max,
            priority=t.priority,
            is_active=t.is_active,
            nutrient=NutritionGoalTargetNutrient(id=nutrient.id, key=nutrient.key, display_name=nutrient.display_name, category=nutrient.category),
        ))

    # Normalize goal fields for mobile compatibility (objective_code and date-only)
    goal_data = goal.__dict__.copy()
    goal_data['objective_code'] = goal.goal_name.lower().replace(' ', '_')
    if 'effective_at' in goal_data and goal_data['effective_at']:
        goal_data['effective_at'] = goal_data['effective_at'].date() if hasattr(goal_data['effective_at'], 'date') else goal_data['effective_at']
    if 'expires_at' in goal_data and goal_data['expires_at']:
        goal_data['expires_at'] = goal_data['expires_at'].date() if hasattr(goal_data['expires_at'], 'date') else goal_data['expires_at']

    # Fetch meal plan JSON record if exists
    meal_plan_row = db.query(crud_nutrition.NutritionMealPlan).filter(crud_nutrition.NutritionMealPlan.goal_id == goal.id).order_by(crud_nutrition.NutritionMealPlan.id.desc()).first() if hasattr(crud_nutrition, 'NutritionMealPlan') else None

    # Fallback to ORM import if not available via crud module
    if meal_plan_row is None:
        try:
            from app.models.nutrition_data import NutritionMealPlan as ORMMealPlan
            meal_plan_row = db.query(ORMMealPlan).filter(ORMMealPlan.goal_id == goal.id).order_by(ORMMealPlan.id.desc()).first()
        except Exception:
            meal_plan_row = None

    meal_plan: dict | None = None
    if meal_plan_row is not None:
        import json as _json
        def parse_json_field(value):
            try:
                return _json.loads(value) if value else None
            except Exception:
                return None
        meal_plan = {
            "breakfast": parse_json_field(getattr(meal_plan_row, 'breakfast', None)),
            "lunch": parse_json_field(getattr(meal_plan_row, 'lunch', None)),
            "dinner": parse_json_field(getattr(meal_plan_row, 'dinner', None)),
            "snacks": parse_json_field(getattr(meal_plan_row, 'snacks', None)),
            "total_calories_kcal": getattr(meal_plan_row, 'total_calories_kcal', None),
        }

    return NutritionGoalDetailOut(
        goal=NutritionGoalOut.model_validate(goal_data),
        targets=targets,
        meal_plan=meal_plan,
    )


@router.patch("/goals/{goal_id}/activate")
def activate_goal(
    goal_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    # Ensure the goal belongs to the user
    goal = crud.nutrition_goals.get_with_targets(db, goal_id, current_user.id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Perform atomic status switch using direct UPDATEs to avoid stale ORM states
    from datetime import datetime
    # Deactivate all current actives for this user
    db.query(NutritionGoal).filter(NutritionGoal.user_id == current_user.id, NutritionGoal.status == "active").update({"status": "inactive"}, synchronize_session=False)
    # Activate requested goal
    db.query(NutritionGoal).filter(NutritionGoal.id == goal.id, NutritionGoal.user_id == current_user.id).update({"status": "active", "effective_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()
    # Refresh goal instance
    goal = crud.nutrition_goals.get_with_targets(db, goal_id, current_user.id)

    # Return updated active goal summary
    primary = sum(1 for t in goal.targets if t.priority == "primary" and t.is_active)
    secondary = sum(1 for t in goal.targets if t.priority == "secondary" and t.is_active)
    timeframes = sorted(list({t.timeframe for t in goal.targets if t.is_active}))

    goal_data = goal.__dict__.copy()
    goal_data['objective_code'] = goal.goal_name.lower().replace(' ', '_')
    if 'effective_at' in goal_data and goal_data['effective_at']:
        goal_data['effective_at'] = goal_data['effective_at'].date() if hasattr(goal_data['effective_at'], 'date') else goal_data['effective_at']
    if 'expires_at' in goal_data and goal_data['expires_at']:
        goal_data['expires_at'] = goal_data['expires_at'].date() if hasattr(goal_data['expires_at'], 'date') else goal_data['expires_at']

    return ActiveGoalSummaryOut(
        has_active_goal=True,
        goal=NutritionGoalOut.model_validate(goal_data),
        targets_summary={
            "total": primary + secondary,
            "primary": primary,
            "secondary": secondary,
            "timeframes": timeframes,
        },
        focus_nutrients=[],
    )


@router.delete("/goals/{goal_id}")
def delete_goal(
    goal_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    # Verify goal ownership
    goal = crud.nutrition_goals.get_with_targets(db, goal_id, current_user.id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Prevent deleting active goal without confirmation; client is expected to switch first
    if goal.status == "active":
        raise HTTPException(status_code=400, detail="Cannot delete active goal. Activate another goal first.")

    # Delete user focus rows for this goal to avoid FK orphans
    db.query(UserNutrientFocus).filter(UserNutrientFocus.goal_id == goal.id).delete(synchronize_session=False)
    # Delete meal plans for this goal
    db.query(NutritionMealPlan).filter(NutritionMealPlan.goal_id == goal.id).delete(synchronize_session=False)
    # Deleting the goal cascades to targets via ORM relationship
    db.delete(goal)
    db.commit()
    return {"success": True}


@router.get("/defaults", response_model=List[DefaultTargetOut])
def list_defaults(
    objective_code: str = Query(...),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    defaults = crud.objective_defaults.list_for_objective(db, objective_code)
    items: List[DefaultTargetOut] = []
    for d in defaults:
        items.append(DefaultTargetOut(
            objective_code=d.objective_code,
            timeframe=d.timeframe,
            target_type=d.target_type,
            target_min=d.target_min,
            target_max=d.target_max,
            priority=d.priority,
            nutrient=NutritionGoalTargetNutrient(id=d.nutrient.id, key=d.nutrient.key, display_name=d.nutrient.display_name),
        ))
    return items


@router.get("/focus", response_model=List[UserNutrientFocusOut])
def list_user_focus(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    focuses = crud.user_nutrient_focus.list_for_user(db, current_user.id)
    return [UserNutrientFocusOut(
        nutrient_id=f.nutrient_id,
        nutrient_key=f.nutrient.key,
        priority=f.priority,
        is_active=f.is_active,
    ) for f in focuses]


@router.get("/progress/active", response_model=ProgressResponseOut)
def get_active_goal_progress(
    response: Response,
    timeframe: str = Query("daily"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    try:
        response.headers["X-NutritionGoals-Debug-Module"] = __name__
        response.headers["X-NutritionGoals-Debug-File"] = __file__
    except Exception:
        pass
    goal = crud.nutrition_goals.get_active_for_user(db, current_user.id)
    if not goal:
        return ProgressResponseOut(objective_code=None, timeframe=timeframe, start_date=start_date or date.today(), end_date=end_date or date.today(), items=[])

    # Pick aggregate table accessor
    if timeframe == "daily":
        # Use daily aggregates between dates
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="start_date and end_date are required for daily timeframe")
        aggregates = crud_nutrition.nutrition_daily_aggregate.get_by_user_date_range(db, user_id=current_user.id, start_date=start_date, end_date=end_date)
        aggregate_row = aggregates[-1] if aggregates else None
        prefix = "total_"
    elif timeframe == "weekly":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="start_date and end_date are required for weekly timeframe")
        aggregates = crud_nutrition.nutrition_weekly_aggregate.get_by_user_date_range(db, user_id=current_user.id, start_date=start_date, end_date=end_date)
        aggregate_row = aggregates[-1] if aggregates else None
        prefix = "avg_daily_"
    elif timeframe == "monthly":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="start_date and end_date are required for monthly timeframe")
        aggregates = crud_nutrition.nutrition_monthly_aggregate.get_by_user_date_range(db, user_id=current_user.id, start_date=start_date, end_date=end_date)
        aggregate_row = aggregates[-1] if aggregates else None
        prefix = "avg_daily_"
    else:
        raise HTTPException(status_code=400, detail="Invalid timeframe")

    items: List[ProgressItemOut] = []
    for t in goal.targets:
        if not t.is_active:
            continue
        # Prefer explicit aggregate field override when provided; fall back to key when null
        key = t.nutrient.aggregate_field or t.nutrient.key
        unit = t.nutrient.unit
        display_name = t.nutrient.display_name
        col_name = f"{prefix}{key}"
        current_value = None
        if aggregate_row is not None and hasattr(aggregate_row, col_name):
            current_value = getattr(aggregate_row, col_name)
        # Fallback: if no aggregate in the requested window, try the most recent daily aggregate in the last 7 days
        if current_value is None and timeframe == "daily":
            fallback_start = (end_date or date.today()) - timedelta(days=7)
            aggregates_fb = crud_nutrition.nutrition_daily_aggregate.get_by_user_date_range(db, user_id=current_user.id, start_date=fallback_start, end_date=end_date or date.today())
            if aggregates_fb:
                latest = aggregates_fb[-1]
                if hasattr(latest, col_name):
                    current_value = getattr(latest, col_name)

        # Compute status
        status = "no_data"
        percent = None
        # Normalize/derive an effective target type in case data contains an unexpected value (e.g., "daily")
        allowed_types = {"exact", "min", "max", "range"}
        effective_type = t.target_type if t.target_type in allowed_types else None
        if effective_type is None:
            if t.target_min is not None and t.target_max is not None:
                effective_type = "exact" if abs(t.target_max - t.target_min) < 1e-6 else "range"
            elif t.target_min is not None:
                effective_type = "min"
            elif t.target_max is not None:
                effective_type = "max"

        if current_value is not None and effective_type is not None:
            if effective_type == "exact" and t.target_min is not None:
                target = t.target_min
                tolerance = 0.05 * target if target else 0
                status = "within" if abs(current_value - target) <= tolerance else ("below" if current_value < target else "above")
                percent = (current_value / target) if target else None
            elif effective_type == "min" and t.target_min is not None:
                status = "below" if current_value < t.target_min else "above"
                percent = (current_value / t.target_min) if t.target_min else None
            elif effective_type == "max" and t.target_max is not None:
                status = "within" if current_value <= t.target_max else "above"
                percent = (current_value / t.target_max) if t.target_max else None
            elif effective_type == "range" and t.target_min is not None and t.target_max is not None:
                status = "within" if (t.target_min <= current_value <= t.target_max) else ("below" if current_value < t.target_min else "above")
                target = (t.target_min + t.target_max) / 2.0
                percent = (current_value / target) if target else None

        items.append(ProgressItemOut(
            nutrient_key=key,
            display_name=display_name,
            unit=unit,
            priority=t.priority,
            # Return the normalized target type so clients don't see unexpected values like "daily"
            target_type=effective_type or t.target_type,
            target_min=t.target_min,
            target_max=t.target_max,
            current_value=current_value,
            percent_of_target=percent,
            status=status,
        ))


    # Derive objective_code from goal name for consistency
    objective_code = goal.goal_name.lower().replace(' ', '_') if goal else None
    
    response = ProgressResponseOut(
        objective_code=objective_code,
        timeframe=timeframe,
        start_date=start_date or date.today(),
        end_date=end_date or date.today(),
        items=items,
    )
    return response
