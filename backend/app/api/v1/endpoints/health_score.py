from datetime import datetime, date
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.models import User
from app.db.session import SessionLocal
from app.health_scoring.services import HealthScoringService
from app.health_scoring.models import HealthScoreResultDaily


router = APIRouter()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/health-score/today")
def get_today_health_score(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    today = datetime.now().date()
    svc = HealthScoringService(db)
    result = svc.compute_daily(user_id=current_user.id, day=today)
    return {
        "date": today.isoformat(),
        "overall": result.overall_score,
        "chronic": result.chronic_score,
        "acute": result.acute_score,
        "confidence": result.confidence,
        "detail": result.detail,
        "spec_version": result.spec_version,
    }


@router.get("/health-score/range")
def get_health_score_range(
    start: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$"),
    end: str = Query(..., regex=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    try:
        s = datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.strptime(end, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format")
    rows = (
        db.query(HealthScoreResultDaily)
        .filter(HealthScoreResultDaily.user_id == current_user.id)
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


