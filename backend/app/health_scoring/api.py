from datetime import date, datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import SessionLocal
from .services import HealthScoringService
from .schemas import SpecCreate
from .models import HealthScoreSpec


router = APIRouter(prefix="/internal/health-score", tags=["health-score-internal"])


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/recompute")
def recompute_daily(
    user_id: int = Query(..., ge=1),
    date_str: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
    _: Any = Depends(deps.get_current_active_admin),
):
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    svc = HealthScoringService(db)
    result = svc.compute_daily(user_id=user_id, day=d)
    return {
        "user_id": user_id,
        "date": date_str,
        "overall": result.overall_score,
        "chronic": result.chronic_score,
        "acute": result.acute_score,
        "confidence": result.confidence,
        "detail": result.detail,
        "spec_version": result.spec_version,
    }


@router.get("/daily")
def get_daily_scores(
    user_id: int = Query(..., ge=1),
    start: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$"),
    end: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
    _: Any = Depends(deps.get_current_active_admin),
):
    from .models import HealthScoreResultDaily
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    rows = (
        db.query(HealthScoreResultDaily)
        .filter(HealthScoreResultDaily.user_id == user_id)
        .filter(HealthScoreResultDaily.date >= s)
        .filter(HealthScoreResultDaily.date <= e)
        .order_by(HealthScoreResultDaily.date)
        .all()
    )
    return [
        {
            "date": r.date.isoformat(),
            "overall": r.overall_score,
            "chronic": r.chronic_score,
            "acute": r.acute_score,
            "confidence": r.confidence,
            "detail": r.detail,
            "spec_version": r.spec_version,
        }
        for r in rows
    ]


@router.post("/spec")
def upsert_spec(
    payload: SpecCreate,
    db: Session = Depends(get_db),
    _: Any = Depends(deps.get_current_active_admin),
):
    spec = (
        db.query(HealthScoreSpec)
        .filter(HealthScoreSpec.version == payload.version)
        .first()
    )
    if spec:
        spec.name = payload.name
        spec.spec_json = payload.spec_json
        spec.is_default = payload.is_default
    else:
        spec = HealthScoreSpec(
            version=payload.version,
            name=payload.name,
            spec_json=payload.spec_json,
            is_default=payload.is_default,
        )
        db.add(spec)
    if payload.is_default:
        # Unset other defaults
        db.query(HealthScoreSpec).filter(HealthScoreSpec.id != spec.id).update({HealthScoreSpec.is_default: False})
    db.commit()
    db.refresh(spec)
    return {"id": spec.id, "version": spec.version, "is_default": spec.is_default}


@router.get("/spec/current")
def get_current_spec(
    db: Session = Depends(get_db),
    _: Any = Depends(deps.get_current_active_admin),
):
    spec = (
        db.query(HealthScoreSpec)
        .filter(HealthScoreSpec.is_default == True)
        .order_by(HealthScoreSpec.updated_at.desc())
        .first()
    )
    if not spec:
        return {"message": "No default spec"}
    return {"version": spec.version, "name": spec.name, "spec": spec.spec_json}


@router.post("/sync-anchors-from-loinc")
def sync_anchors_from_loinc(
    db: Session = Depends(get_db),
    _: Any = Depends(deps.get_current_active_admin),
):
    svc = HealthScoringService(db)
    count = svc.sync_metric_anchors_from_lab_mapping()
    return {"upserts": count}


