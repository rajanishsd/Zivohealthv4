from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.mental_health import (
    MentalHealthEntryCreate,
    MentalHealthEntryResponse,
    MentalHealthRollupResponse,
    MentalHealthDailyPoint,
    NameCount,
)
from app.crud import mental_health as crud_mh
from app.core.config import settings
from app.models.mental_health import (
    MentalHealthPleasantnessDictionary,
    MentalHealthEntryTypeDictionary,
    MentalHealthDailyAggregate,
)
from app.services.mental_health_aggregator import recompute_daily_for_user
from app.models.user import User

router = APIRouter()


@router.post("/entries", response_model=MentalHealthEntryResponse)
def create_entry(
    *,
    db: Session = Depends(deps.get_db),
    body: MentalHealthEntryCreate,
    current_user: User = Depends(deps.get_current_active_user)
):
    try:
        # Validate pleasantness and resolve canonical label
        pl = (
            db.query(MentalHealthPleasantnessDictionary)
            .filter(MentalHealthPleasantnessDictionary.score == body.pleasantness_score)
            .first()
        )
        if not pl:
            raise HTTPException(status_code=400, detail="Invalid pleasantness_score")

        # Validate entry type code exists
        et = (
            db.query(MentalHealthEntryTypeDictionary)
            .filter(MentalHealthEntryTypeDictionary.code == body.entry_type)
            .first()
        )
        if not et:
            raise HTTPException(status_code=400, detail="Invalid entry_type")

        # Force canonical label server-side
        body = body.model_copy(update={"pleasantness_label": pl.label})

        created = crud_mh.mental_health_entry.create_with_user(db=db, obj_in=body, user_id=current_user.id)

        # Recompute daily aggregate for just this user and date
        try:
            recompute_daily_for_user(db, user_id=current_user.id, for_date=created.recorded_at.date())
        except Exception:
            # Non-fatal: log and continue (api still returns success)
            pass
        # Map back to schema (normalized entity doesn't store legacy fields)
        return MentalHealthEntryResponse(
            id=created.id,
            user_id=created.user_id,
            recorded_at=created.recorded_at,
            entry_type=body.entry_type,
            pleasantness_score=body.pleasantness_score,
            pleasantness_label=body.pleasantness_label,
            feelings=[],
            impacts=[],
            notes=created.notes,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create mental health entry: {e}")


@router.get("/rollup", response_model=MentalHealthRollupResponse)
def get_rollup(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    range: str = Query("W", pattern=r"^(W|M|6M|Y)$"),
):
    # Compose from daily aggregates for the user
    end_date = date.today()
    if range == "W":
        start_date = end_date - timedelta(days=7)
    elif range == "M":
        start_date = end_date - timedelta(days=30)
    elif range == "6M":
        start_date = end_date - timedelta(days=180)
    else:
        start_date = end_date - timedelta(days=365)

    # Build score->label map
    score_to_label = {row.score: row.label for row in db.query(MentalHealthPleasantnessDictionary).all()}

    # Fetch daily aggregates in range
    rows = (
        db.query(MentalHealthDailyAggregate)
        .filter(MentalHealthDailyAggregate.user_id == current_user.id)
        .filter(MentalHealthDailyAggregate.date >= start_date)
        .filter(MentalHealthDailyAggregate.date <= end_date)
        .order_by(MentalHealthDailyAggregate.date.asc())
        .all()
    )

    import json as _json

    points: List[MentalHealthDailyPoint] = []
    feelings_totals: dict[str, int] = {}
    impacts_totals: dict[str, int] = {}
    for r in rows:
        score = r.avg_score if r.avg_score is not None else r.last_score
        if score is None:
            continue
        try:
            parsed = _json.loads(r.feelings_counts_json or "[]")
            feelings_list = [item.get("name") for item in parsed if item.get("name")]
            for item in parsed:
                name = item.get("name"); count = int(item.get("count", 0))
                if name:
                    feelings_totals[name] = feelings_totals.get(name, 0) + count
        except Exception:
            feelings_list = []
        try:
            parsed = _json.loads(r.impacts_counts_json or "[]")
            impacts_list = [item.get("name") for item in parsed if item.get("name")]
            for item in parsed:
                name = item.get("name"); count = int(item.get("count", 0))
                if name:
                    impacts_totals[name] = impacts_totals.get(name, 0) + count
        except Exception:
            impacts_list = []
        label = score_to_label.get(int(score), "")
        points.append(MentalHealthDailyPoint(
            date=r.date,
            score=int(score),
            label=label,
            feelings=feelings_list,
            impacts=impacts_list,
        ))
    feelings_counts = [NameCount(name=k, count=v) for k, v in feelings_totals.items()]
    feelings_counts.sort(key=lambda x: x.count, reverse=True)
    impacts_counts = [NameCount(name=k, count=v) for k, v in impacts_totals.items()]
    impacts_counts.sort(key=lambda x: x.count, reverse=True)

    return MentalHealthRollupResponse(data_points=points, range=range, feelings_counts=feelings_counts, impacts_counts=impacts_counts)


@router.get("/dictionaries")
def get_dictionaries(db: Session = Depends(deps.get_db)):
    # DB dictionaries only (no hardcoded or env lists)
    feelings = [row.name for row in crud_mh.mental_health_feelings_dict.active(db)]
    impacts = [row.name for row in crud_mh.mental_health_impacts_dict.active(db)]
    pleasantness = [
        {"score": row.score, "label": row.label}
        for row in crud_mh.mental_health_pleasantness_dict.active(db)
    ]
    entry_types = [
        {"code": row.code, "label": row.label}
        for row in crud_mh.mental_health_entry_type_dict.active(db)
    ]
    return {
        "version": settings.MENTALHEALTH_DICT_VERSION,
        "mentalhealth_feelings": feelings,
        "mentalhealth_impact": impacts,
        "mentalhealth_pleasantness": pleasantness,
        "mentalhealth_entry_types": entry_types,
    }


