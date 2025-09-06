from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.crud import nutrition_goals as crud
from app.crud import nutrition as crud_nutrition
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
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    goal = crud.nutrition_goals.get_active_for_user(db, current_user.id)
    if not goal:
        return ActiveGoalSummaryOut(has_active_goal=False)

    primary = sum(1 for t in goal.targets if t.priority == "primary" and t.is_active)
    secondary = sum(1 for t in goal.targets if t.priority == "secondary" and t.is_active)
    timeframes = sorted(list({t.timeframe for t in goal.targets if t.is_active}))

    return ActiveGoalSummaryOut(
        has_active_goal=True,
        goal=NutritionGoalOut.model_validate(goal),
        targets_summary={
            "total": primary + secondary,
            "primary": primary,
            "secondary": secondary,
            "timeframes": timeframes,
        },
    )


@router.get("/goals", response_model=List[NutritionGoalOut])
def list_goals(
    status: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    items = crud.nutrition_goals.list_for_user(db, current_user.id, status=status)
    return [NutritionGoalOut.model_validate(i) for i in items]


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
            nutrient=NutritionGoalTargetNutrient(id=nutrient.id, key=nutrient.key, display_name=nutrient.display_name),
        ))

    return {
        "goal": NutritionGoalOut.model_validate(goal),
        "targets": targets,
    }


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
    timeframe: str = Query("daily"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
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
        key = t.nutrient.key
        unit = t.nutrient.unit
        display_name = t.nutrient.display_name
        col_name = f"{prefix}{key}"
        current_value = None
        if aggregate_row is not None and hasattr(aggregate_row, col_name):
            current_value = getattr(aggregate_row, col_name)

        # Compute status
        status = "no_data"
        percent = None
        if current_value is not None:
            if t.target_type == "exact" and t.target_min is not None:
                target = t.target_min
                tolerance = 0.05 * target if target else 0
                status = "within" if abs(current_value - target) <= tolerance else ("below" if current_value < target else "above")
                percent = (current_value / target) if target else None
            elif t.target_type == "min" and t.target_min is not None:
                status = "below" if current_value < t.target_min else "above"
                percent = (current_value / t.target_min) if t.target_min else None
            elif t.target_type == "max" and t.target_max is not None:
                status = "within" if current_value <= t.target_max else "above"
                percent = (current_value / t.target_max) if t.target_max else None
            elif t.target_type == "range" and t.target_min is not None and t.target_max is not None:
                status = "within" if (t.target_min <= current_value <= t.target_max) else ("below" if current_value < t.target_min else "above")
                target = (t.target_min + t.target_max) / 2.0
                percent = (current_value / target) if target else None

        items.append(ProgressItemOut(
            nutrient_key=key,
            display_name=display_name,
            unit=unit,
            priority=t.priority,
            target_type=t.target_type,
            target_min=t.target_min,
            target_max=t.target_max,
            current_value=current_value,
            percent_of_target=percent,
            status=status,
        ))

    return ProgressResponseOut(
        objective_code=None,
        timeframe=timeframe,
        start_date=start_date or date.today(),
        end_date=end_date or date.today(),
        items=items,
    )
