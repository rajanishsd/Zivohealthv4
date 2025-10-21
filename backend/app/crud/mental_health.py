import json
from datetime import date, datetime
from typing import List, Optional
from sqlalchemy.orm import Session
import sqlalchemy as sa

from .base import CRUDBase
from app.models.mental_health import (
    MentalHealthEntry,
    MentalHealthDailyAggregate,
    MentalHealthFeelingDictionary,
    MentalHealthImpactDictionary,
    MentalHealthPleasantnessDictionary,
    MentalHealthEntryTypeDictionary,
)
from app.schemas.mental_health import MentalHealthEntryCreate


class CRUDMentalHealthEntry(CRUDBase[MentalHealthEntry, MentalHealthEntryCreate, MentalHealthEntryCreate]):
    def create_with_user(self, db: Session, *, obj_in: MentalHealthEntryCreate, user_id: int) -> MentalHealthEntry:
        # Resolve pleasantness and entry type ids
        pleasantness = (
            db.query(MentalHealthPleasantnessDictionary)
            .filter(MentalHealthPleasantnessDictionary.score == obj_in.pleasantness_score)
            .first()
        )
        entry_type = (
            db.query(MentalHealthEntryTypeDictionary)
            .filter(MentalHealthEntryTypeDictionary.code == obj_in.entry_type)
            .first()
        )

        db_obj = MentalHealthEntry(
            user_id=user_id,
            recorded_at=obj_in.recorded_at,
            notes=obj_in.notes,
            source="app",
            pleasantness_id=pleasantness.id if pleasantness else None,
            entry_type_id=entry_type.id if entry_type else None,
            aggregation_status="pending",
        )
        db.add(db_obj)
        db.flush()  # get db_obj.id without committing yet

        # Insert feelings associations
        if obj_in.feelings:
            names = [name.strip() for name in obj_in.feelings if name.strip()]
            if names:
                id_map = {
                    r.name: r.id for r in (
                        db.query(MentalHealthFeelingDictionary)
                        .filter(MentalHealthFeelingDictionary.name.in_(names))
                        .all()
                    )
                }
                for name in names:
                    fid = id_map.get(name)
                    if fid:
                        db.execute(
                            sa.text(
                                "INSERT INTO mental_health_entry_feelings (entry_id, feeling_id) VALUES (:e, :f)"
                            ),
                            {"e": db_obj.id, "f": fid},
                        )

        # Insert impacts associations
        if obj_in.impacts:
            names = [name.strip() for name in obj_in.impacts if name.strip()]
            if names:
                id_map = {
                    r.name: r.id for r in (
                        db.query(MentalHealthImpactDictionary)
                        .filter(MentalHealthImpactDictionary.name.in_(names))
                        .all()
                    )
                }
                for name in names:
                    iid = id_map.get(name)
                    if iid:
                        db.execute(
                            sa.text(
                                "INSERT INTO mental_health_entry_impacts (entry_id, impact_id) VALUES (:e, :i)"
                            ),
                            {"e": db_obj.id, "i": iid},
                        )

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_user_range(self, db: Session, *, user_id: int, start: datetime, end: datetime) -> List[MentalHealthEntry]:
        return (
            db.query(MentalHealthEntry)
            .filter(MentalHealthEntry.user_id == user_id)
            .filter(MentalHealthEntry.recorded_at >= start)
            .filter(MentalHealthEntry.recorded_at <= end)
            .order_by(MentalHealthEntry.recorded_at.asc())
            .all()
        )


class CRUDMentalHealthDaily(CRUDBase[MentalHealthDailyAggregate, MentalHealthDailyAggregate, MentalHealthDailyAggregate]):
    def get_by_user_date_range(self, db: Session, *, user_id: int, start_date: date, end_date: date) -> List[MentalHealthDailyAggregate]:
        return (
            db.query(MentalHealthDailyAggregate)
            .filter(MentalHealthDailyAggregate.user_id == user_id)
            .filter(MentalHealthDailyAggregate.date >= start_date)
            .filter(MentalHealthDailyAggregate.date <= end_date)
            .order_by(MentalHealthDailyAggregate.date.asc())
            .all()
        )


mental_health_entry = CRUDMentalHealthEntry(MentalHealthEntry)
mental_health_daily = CRUDMentalHealthDaily(MentalHealthDailyAggregate)


class CRUDMentalHealthFeelingDict(CRUDBase[MentalHealthFeelingDictionary, MentalHealthFeelingDictionary, MentalHealthFeelingDictionary]):
    def active(self, db: Session):
        return (
            db.query(MentalHealthFeelingDictionary)
            .filter(MentalHealthFeelingDictionary.is_active == "true")
            .order_by(MentalHealthFeelingDictionary.sort_order.asc().nulls_last(), MentalHealthFeelingDictionary.name.asc())
            .all()
        )


class CRUDMentalHealthImpactDict(CRUDBase[MentalHealthImpactDictionary, MentalHealthImpactDictionary, MentalHealthImpactDictionary]):
    def active(self, db: Session):
        return (
            db.query(MentalHealthImpactDictionary)
            .filter(MentalHealthImpactDictionary.is_active == "true")
            .order_by(MentalHealthImpactDictionary.sort_order.asc().nulls_last(), MentalHealthImpactDictionary.name.asc())
            .all()
        )


mental_health_feelings_dict = CRUDMentalHealthFeelingDict(MentalHealthFeelingDictionary)
mental_health_impacts_dict = CRUDMentalHealthImpactDict(MentalHealthImpactDictionary)

class CRUDMentalHealthPleasantnessDict(CRUDBase[MentalHealthPleasantnessDictionary, MentalHealthPleasantnessDictionary, MentalHealthPleasantnessDictionary]):
    def active(self, db: Session):
        return (
            db.query(MentalHealthPleasantnessDictionary)
            .filter(MentalHealthPleasantnessDictionary.is_active == "true")
            .order_by(MentalHealthPleasantnessDictionary.sort_order.asc().nulls_last(), MentalHealthPleasantnessDictionary.score.asc())
            .all()
        )

mental_health_pleasantness_dict = CRUDMentalHealthPleasantnessDict(MentalHealthPleasantnessDictionary)

class CRUDMentalHealthEntryTypeDict(CRUDBase[MentalHealthEntryTypeDictionary, MentalHealthEntryTypeDictionary, MentalHealthEntryTypeDictionary]):
    def active(self, db: Session):
        return (
            db.query(MentalHealthEntryTypeDictionary)
            .filter(MentalHealthEntryTypeDictionary.is_active == "true")
            .order_by(MentalHealthEntryTypeDictionary.sort_order.asc().nulls_last(), MentalHealthEntryTypeDictionary.code.asc())
            .all()
        )

mental_health_entry_type_dict = CRUDMentalHealthEntryTypeDict(MentalHealthEntryTypeDictionary)


