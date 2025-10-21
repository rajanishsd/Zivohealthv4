from __future__ import annotations

import json
from datetime import datetime, date, timedelta
from typing import Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.mental_health import (
    MentalHealthEntry,
    MentalHealthPleasantnessDictionary,
    MentalHealthEntryFeeling,
    MentalHealthFeelingDictionary,
    MentalHealthEntryImpact,
    MentalHealthImpactDictionary,
    MentalHealthDailyAggregate,
)


def _day_bounds(d: date) -> Tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day)
    end = start + timedelta(days=1)
    return start, end


def recompute_daily_for_user(db: Session, *, user_id: int, for_date: date) -> None:
    """Compute and upsert the daily aggregate for a given user and date.

    Writes into MentalHealthDailyAggregate (avg_score, last_score, last_entry_at, top3 feelings/impacts).
    Safe to call after each entry write.
    """
    start_dt, end_dt = _day_bounds(for_date)

    # Entries with scores for the day
    rows = (
        db.query(MentalHealthEntry.recorded_at, MentalHealthPleasantnessDictionary.score)
        .join(
            MentalHealthPleasantnessDictionary,
            MentalHealthEntry.pleasantness_id == MentalHealthPleasantnessDictionary.id,
        )
        .filter(
            MentalHealthEntry.user_id == user_id,
            MentalHealthEntry.recorded_at >= start_dt,
            MentalHealthEntry.recorded_at < end_dt,
        )
        .order_by(MentalHealthEntry.recorded_at.asc())
        .all()
    )

    if not rows:
        # If no entries, upsert a zeroed aggregate (optional: delete existing)
        agg = (
            db.query(MentalHealthDailyAggregate)
            .filter(
                MentalHealthDailyAggregate.user_id == user_id,
                MentalHealthDailyAggregate.date == for_date,
            )
            .first()
        )
        if agg:
            agg.avg_score = None
            agg.last_score = None
            agg.last_entry_at = None
            agg.feelings_top3_json = json.dumps([])
            agg.impacts_top3_json = json.dumps([])
            db.add(agg)
            db.commit()
        else:
            agg = MentalHealthDailyAggregate(
                user_id=user_id,
                date=for_date,
                avg_score=None,
                last_score=None,
                last_entry_at=None,
                feelings_top3_json=json.dumps([]),
                impacts_top3_json=json.dumps([]),
            )
            db.add(agg)
            db.commit()
        return

    scores = [r[1] for r in rows]
    avg_score = sum(scores) / float(len(scores)) if scores else None
    last_score = scores[-1] if scores else None
    last_entry_at = rows[-1][0] if rows else None

    # Feelings counts for the day
    feelings_counts = (
        db.query(MentalHealthFeelingDictionary.name, func.count(MentalHealthFeelingDictionary.id))
        .join(MentalHealthEntryFeeling, MentalHealthEntryFeeling.feeling_id == MentalHealthFeelingDictionary.id)
        .join(MentalHealthEntry, MentalHealthEntry.id == MentalHealthEntryFeeling.entry_id)
        .filter(
            MentalHealthEntry.user_id == user_id,
            MentalHealthEntry.recorded_at >= start_dt,
            MentalHealthEntry.recorded_at < end_dt,
        )
        .group_by(MentalHealthFeelingDictionary.name)
        .order_by(func.count(MentalHealthFeelingDictionary.id).desc(), MentalHealthFeelingDictionary.name.asc())
        .all()
    )
    feelings_top3 = [{"name": n, "count": int(c)} for n, c in feelings_counts]

    # Impacts counts for the day
    impacts_counts = (
        db.query(MentalHealthImpactDictionary.name, func.count(MentalHealthImpactDictionary.id))
        .join(MentalHealthEntryImpact, MentalHealthEntryImpact.impact_id == MentalHealthImpactDictionary.id)
        .join(MentalHealthEntry, MentalHealthEntry.id == MentalHealthEntryImpact.entry_id)
        .filter(
            MentalHealthEntry.user_id == user_id,
            MentalHealthEntry.recorded_at >= start_dt,
            MentalHealthEntry.recorded_at < end_dt,
        )
        .group_by(MentalHealthImpactDictionary.name)
        .order_by(func.count(MentalHealthImpactDictionary.id).desc(), MentalHealthImpactDictionary.name.asc())
        .all()
    )
    impacts_top3 = [{"name": n, "count": int(c)} for n, c in impacts_counts]

    # Upsert into daily aggregate
    agg = (
        db.query(MentalHealthDailyAggregate)
        .filter(
            MentalHealthDailyAggregate.user_id == user_id,
            MentalHealthDailyAggregate.date == for_date,
        )
        .first()
    )
    if agg:
        agg.avg_score = avg_score
        agg.last_score = last_score
        agg.last_entry_at = last_entry_at
        agg.feelings_counts_json = json.dumps(feelings_top3)
        agg.impacts_counts_json = json.dumps(impacts_top3)
        db.add(agg)
    else:
        agg = MentalHealthDailyAggregate(
            user_id=user_id,
            date=for_date,
            avg_score=avg_score,
            last_score=last_score,
            last_entry_at=last_entry_at,
            feelings_counts_json=json.dumps(feelings_top3),
            impacts_counts_json=json.dumps(impacts_top3),
        )
        db.add(agg)

    db.commit()

    # Mark entries for the day as aggregated
    db.query(MentalHealthEntry).filter(
        MentalHealthEntry.user_id == user_id,
        MentalHealthEntry.recorded_at >= start_dt,
        MentalHealthEntry.recorded_at < end_dt,
    ).update(
        {
            MentalHealthEntry.aggregation_status: "completed",
            MentalHealthEntry.aggregated_at: datetime.utcnow(),
        },
        synchronize_session=False,
    )
    db.commit()


