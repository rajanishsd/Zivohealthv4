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
from sqlalchemy import text as _sa_text
from datetime import datetime as _dt
from typing import Dict, Optional
import json
from app.core.config import settings
from zoneinfo import ZoneInfo
import os
import requests

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


@router.get("/goals/{goal_id}/reminders")
def list_goal_reminders(
    goal_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Return reminder configurations and identifiers for a specific nutrition goal."""
    # Ensure goal belongs to the user
    goal = crud.nutrition_goals.get_with_targets(db, goal_id, current_user.id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    rows = db.execute(
        _sa_text(
            """
            SELECT external_id, key, active, config_json
            FROM user_reminder_configs
            WHERE user_id = :uid AND context = 'nutrition_goal' AND context_id = :gid
            ORDER BY key
            """
        ),
        {"uid": str(current_user.id), "gid": str(goal_id)},
    ).mappings().all()

    if not rows:
        return {
            "group_id": f"v1:{current_user.id}:nutrition_goal:{goal_id}",
            "timezone": getattr(getattr(goal, 'timezone', None), 'name', None) or None,
            "items": [],
        }

    # Use the first row's config_json as the base preferences
    try:
        base_cfg = rows[0]["config_json"] or {}
    except Exception:
        base_cfg = {}
    tz = base_cfg.get("timezone")
    reminders = base_cfg.get("reminders") or []
    meal_to_cfg = {}
    for it in reminders:
        meal = str(it.get("meal", "")).lower()
        if meal:
            meal_to_cfg[meal] = it

    # Build items from stored rows merged with base config
    items = []
    for r in rows:
        key = str(r["key"]).lower()
        cfg = meal_to_cfg.get(key, {})
        items.append({
            "meal": key,
            "time_local": cfg.get("time_local"),
            "frequency": cfg.get("frequency"),
            "external_id": r["external_id"],
            "status": "active" if r["active"] else "disabled",
        })

    return {
        "group_id": f"v1:{current_user.id}:nutrition_goal:{goal_id}",
        "timezone": tz,
        "items": items,
    }


@router.get("/current/reminders")
def list_current_goal_reminders(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Return reminder configurations for the CURRENT active nutrition goal only."""
    goal = crud.nutrition_goals.get_active_for_user(db, current_user.id)
    if not goal:
        raise HTTPException(status_code=404, detail="No active goal")

    rows = db.execute(
        _sa_text(
            """
            SELECT external_id, key, active, config_json
            FROM user_reminder_configs
            WHERE user_id = :uid AND context = 'nutrition_goal' AND context_id = :gid
            ORDER BY key
            """
        ),
        {"uid": str(current_user.id), "gid": str(goal.id)},
    ).mappings().all()

    if not rows:
        return {
            "group_id": f"v1:{current_user.id}:nutrition_goal:{goal.id}",
            "timezone": None,
            "items": [],
        }

    try:
        base_cfg = rows[0]["config_json"] or {}
    except Exception:
        base_cfg = {}
    tz = base_cfg.get("timezone")
    reminders = base_cfg.get("reminders") or []
    meal_to_cfg = {}
    for it in reminders:
        meal = str(it.get("meal", "")).lower()
        if meal:
            meal_to_cfg[meal] = it

    items = []
    for r in rows:
        key = str(r["key"]).lower()
        cfg = meal_to_cfg.get(key, {})
        items.append({
            "meal": key,
            "time_local": cfg.get("time_local"),
            "frequency": cfg.get("frequency"),
            "external_id": r["external_id"],
            "status": "active" if r["active"] else "disabled",
        })

    return {
        "group_id": f"v1:{current_user.id}:nutrition_goal:{goal.id}",
        "timezone": tz,
        "items": items,
    }


@router.patch("/current/reminders/{meal}")
def update_current_goal_reminder(
    meal: str,
    time_local: Optional[str] = Query(None, description="HH:MM in user's timezone"),
    frequency: Optional[str] = Query(None, description="daily|every_2_days|weekly"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Update time/frequency for a specific meal reminder of the current goal.
    This updates:
    - user_reminder_configs.config_json (single JSON with timezone/reminders array)
    - reminders (recurring template) via Reminders service using the stored external_id
    """
    meal_key = str(meal).lower()
    goal = crud.nutrition_goals.get_active_for_user(db, current_user.id)
    if not goal:
        raise HTTPException(status_code=404, detail="No active goal")

    # Fetch existing rows
    rows = db.execute(
        _sa_text(
            """
            SELECT id, external_id, key, active, config_json
            FROM user_reminder_configs
            WHERE user_id = :uid AND context = 'nutrition_goal' AND context_id = :gid AND key = :key
            """
        ),
        {"uid": str(current_user.id), "gid": str(goal.id), "key": meal_key},
    ).mappings().all()

    if not rows:
        raise HTTPException(status_code=404, detail="Reminder config not found for meal")

    # Use the first row's config_json as the base preferences and upsert the change
    try:
        base_cfg: Dict = rows[0]["config_json"] or {}
    except Exception:
        base_cfg = {}

    reminders_cfg = base_cfg.get("reminders") or []
    updated = False
    for it in reminders_cfg:
        if str(it.get("meal", "")).lower() == meal_key:
            if time_local is not None:
                it["time_local"] = time_local
            if frequency is not None:
                it["frequency"] = frequency
            updated = True
            break
    if not updated:
        # insert if missing
        entry = {"meal": meal_key}
        if time_local is not None:
            entry["time_local"] = time_local
        if frequency is not None:
            entry["frequency"] = frequency
        reminders_cfg.append(entry)
    base_cfg["reminders"] = reminders_cfg

    # Persist JSON back to user_reminder_configs for all rows in the group (keep them consistent)
    from sqlalchemy.dialects.postgresql import JSONB
    db.execute(
        _sa_text(
            """
            UPDATE user_reminder_configs
            SET config_json = CAST(:cfg AS JSONB), updated_at = now()
            WHERE user_id = :uid AND context = 'nutrition_goal' AND context_id = :gid
            """
        ),
        {"cfg": json.dumps(base_cfg), "uid": str(current_user.id), "gid": str(goal.id)},
    )
    db.commit()

    # Update recurring template in reminders service using external_id
    external_id = rows[0]["external_id"]

    # Reminders service configuration is handled by the shared client

    # Look up reminder by external_id, then PATCH it
    try:
        from app.reminders.client import push_list_reminders, push_update_reminder
        # List to find id by external_id
        items = push_list_reminders(str(current_user.id))
        match = next((i for i in items if i.get("external_id") == external_id), None)
        if not match:
            # If not found, we cannot update the reminders table now; continue after config update
            return {"updated": True, "warning": "reminder template not found; config saved"}

        reminder_id = match["id"]
        payload: Dict[str, object] = {}
        if time_local is not None:
            # Keep the same anchor date but update HH:mm and zero seconds
            try:
                from datetime import datetime as _dt_
                dt_str = match.get("reminder_time")
                tz_name = base_cfg.get("timezone") or getattr(settings, "DEFAULT_TIMEZONE", "UTC")
                tz = None
                try:
                    tz = ZoneInfo(tz_name)
                except Exception:
                    tz = None
                if isinstance(dt_str, str):
                    base_dt = _dt_.fromisoformat(dt_str)
                else:
                    base_dt = _dt_.utcnow()
                # Convert base to user's local timezone before applying HH:mm
                if tz is not None:
                    if base_dt.tzinfo is None:
                        base_local = base_dt.replace(tzinfo=tz)
                    else:
                        base_local = base_dt.astimezone(tz)
                else:
                    base_local = base_dt
                hh, mm = [int(x) for x in time_local.split(":")] if ":" in time_local else (0, 0)
                new_local = base_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
                payload["reminder_time"] = new_local.isoformat()
            except Exception:
                pass
        if frequency is not None and match.get("is_recurring"):
            # Map frequency string to recurrence pattern
            interval = 1 if frequency == "daily" else (2 if frequency == "every_2_days" else 7)
            payload["recurrence_pattern"] = {"type": "daily", "interval": interval}

        if payload:
            pr = push_update_reminder(reminder_id, payload, timeout=10)
            pr.raise_for_status()
    except Exception as e:
        # Best-effort: configuration JSON persisted even if reminders service update fails
        return {"updated": True, "warning": f"partial update: {e}"}

    return {"updated": True}


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
    # Capture the currently active goal ids so we can pause their reminders
    active_ids = [g.id for g in db.query(NutritionGoal.id).filter(NutritionGoal.user_id == current_user.id, NutritionGoal.status == "active").all()]
    db.query(NutritionGoal).filter(NutritionGoal.user_id == current_user.id, NutritionGoal.status == "active").update({"status": "inactive"}, synchronize_session=False)
    # Activate requested goal
    db.query(NutritionGoal).filter(NutritionGoal.id == goal.id, NutritionGoal.user_id == current_user.id).update({"status": "active", "effective_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()
    
    # Pause reminders linked to previously active goals: mark user_reminder_configs inactive and set reminders is_active=false
    try:
        if active_ids:
            gid_strs = [str(x) for x in active_ids]
            # Mark configs inactive
            db.execute(
                _sa_text(
                    """
                    UPDATE user_reminder_configs
                    SET active = false, updated_at = now()
                    WHERE user_id = :uid AND context = 'nutrition_goal' AND context_id = ANY(:gids)
                    """
                ),
                {"uid": str(current_user.id), "gids": gid_strs},
            )
            # Fetch external_ids to pause
            rows = db.execute(
                _sa_text(
                    """
                    SELECT external_id
                    FROM user_reminder_configs
                    WHERE user_id = :uid AND context = 'nutrition_goal' AND context_id = ANY(:gids)
                    """
                ),
                {"uid": str(current_user.id), "gids": gid_strs},
            ).mappings().all()
            external_ids = [r["external_id"] for r in rows if r.get("external_id")]
        else:
            external_ids = []
        # Persist inactive flag immediately
        db.commit()
    except Exception:
        external_ids = []

    # Best-effort call to reminders service
    try:
        if external_ids:
            from app.reminders.client import push_list_reminders, push_update_reminder
            items = push_list_reminders(str(current_user.id))
            ext_to_item = {i.get("external_id"): i for i in items if i.get("external_id")}
            for ext in external_ids:
                it = ext_to_item.get(ext)
                if not it:
                    continue
                rid = it.get("id")
                if rid:
                    try:
                        push_update_reminder(rid, {"is_active": False}, timeout=8)
                    except Exception:
                        pass
    except Exception:
        pass

    # Reactivate configs and reminders for the newly activated goal
    try:
        # Mark configs for target goal active=true
        db.execute(
            _sa_text(
                """
                UPDATE user_reminder_configs
                SET active = true, updated_at = now()
                WHERE user_id = :uid AND context = 'nutrition_goal' AND context_id = :gid
                """
            ),
            {"uid": str(current_user.id), "gid": str(goal.id)},
        )
        # Fetch external_ids for target goal
        rows2 = db.execute(
            _sa_text(
                """
                SELECT external_id
                FROM user_reminder_configs
                WHERE user_id = :uid AND context = 'nutrition_goal' AND context_id = :gid
                """
            ),
            {"uid": str(current_user.id), "gid": str(goal.id)},
        ).mappings().all()
        to_activate = [r["external_id"] for r in rows2 if r.get("external_id")]
        db.commit()
    except Exception:
        to_activate = []

    try:
        if to_activate:
            from app.reminders.client import push_list_reminders, push_update_reminder
            items = push_list_reminders(str(current_user.id))
            ext_to_item = {i.get("external_id"): i for i in items if i.get("external_id")}
            for ext in to_activate:
                it = ext_to_item.get(ext)
                if not it:
                    continue
                rid = it.get("id")
                if rid:
                    try:
                        push_update_reminder(rid, {"is_active": True}, timeout=8)
                    except Exception:
                        pass
    except Exception:
        pass
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

    # Gather reminder external_ids for this goal before removing configs
    external_ids: list[str] = []
    try:
        rows = db.execute(
            _sa_text(
                """
                SELECT external_id
                FROM user_reminder_configs
                WHERE user_id = :uid AND context = 'nutrition_goal' AND context_id = :gid
                """
            ),
            {"uid": str(current_user.id), "gid": goal.id},
        ).mappings().all()
        external_ids = [r["external_id"] for r in rows if r.get("external_id")]
    except Exception:
        external_ids = []

    # Delete user focus rows for this goal to avoid FK orphans
    db.query(UserNutrientFocus).filter(UserNutrientFocus.goal_id == goal.id).delete(synchronize_session=False)
    # Delete meal plans for this goal
    db.query(NutritionMealPlan).filter(NutritionMealPlan.goal_id == goal.id).delete(synchronize_session=False)
    # Delete reminder configs for this goal
    try:
        db.execute(
            _sa_text(
                """
                DELETE FROM user_reminder_configs
                WHERE user_id = :uid AND context = 'nutrition_goal' AND context_id = :gid
                """
            ),
            {"uid": str(current_user.id), "gid": goal.id},
        )
    except Exception:
        pass
    # Deleting the goal cascades to targets via ORM relationship
    db.delete(goal)
    db.commit()

    # Best-effort: delete reminders in reminders service for this plan
    try:
        if external_ids:
            from app.reminders.client import push_list_reminders, push_delete_reminder
            items = push_list_reminders(str(current_user.id))
            ext_to_item = {i.get("external_id"): i for i in items if i.get("external_id")}
            for ext in external_ids:
                it = ext_to_item.get(ext)
                if not it:
                    continue
                rid = it.get("id")
                if rid:
                    try:
                        push_delete_reminder(rid, timeout=8)
                    except Exception:
                        pass
    except Exception:
        pass
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
        # Do not fallback to previous days for daily timeframe.
        # If today's aggregate doesn't exist (no meals logged yet), keep current_value as None
        # so clients can display a clear "No Data" state for today instead of showing yesterday's values.

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
