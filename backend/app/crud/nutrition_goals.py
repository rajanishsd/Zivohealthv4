from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, asc

from app.models.nutrition_goals import (
    NutritionObjective,
    NutritionNutrientCatalog,
    NutritionGoal,
    NutritionGoalTarget,
    UserNutrientFocus,
)


class CRUDNutritionObjectives:
    @staticmethod
    def list(db: Session) -> List[NutritionObjective]:
        return db.query(NutritionObjective).order_by(asc(NutritionObjective.display_name)).all()


class CRUDNutrientCatalog:
    @staticmethod
    def list(db: Session, *, enabled_only: bool = True) -> List[NutritionNutrientCatalog]:
        q = db.query(NutritionNutrientCatalog)
        if enabled_only:
            q = q.filter(NutritionNutrientCatalog.is_enabled == True)
        return q.order_by(asc(NutritionNutrientCatalog.display_name)).all()

    @staticmethod
    def by_ids(db: Session, ids: List[int]) -> List[NutritionNutrientCatalog]:
        return db.query(NutritionNutrientCatalog).filter(NutritionNutrientCatalog.id.in_(ids)).all()


class CRUDNutritionGoals:
    @staticmethod
    def get_active_for_user(db: Session, user_id: int) -> Optional[NutritionGoal]:
        return db.query(NutritionGoal).options(joinedload(NutritionGoal.targets).joinedload(NutritionGoalTarget.nutrient)).filter(
            and_(NutritionGoal.user_id == user_id, NutritionGoal.status == "active")
        ).order_by(NutritionGoal.effective_at.desc()).first()

    @staticmethod
    def list_for_user(db: Session, user_id: int, status: Optional[str] = None) -> List[NutritionGoal]:
        q = db.query(NutritionGoal).filter(NutritionGoal.user_id == user_id)
        if status:
            q = q.filter(NutritionGoal.status == status)
        return q.order_by(NutritionGoal.effective_at.desc()).all()

    @staticmethod
    def get_with_targets(db: Session, goal_id: int, user_id: int) -> Optional[NutritionGoal]:
        return db.query(NutritionGoal).options(joinedload(NutritionGoal.targets).joinedload(NutritionGoalTarget.nutrient)).filter(
            and_(NutritionGoal.id == goal_id, NutritionGoal.user_id == user_id)
        ).first()


# Removed: CRUDObjectiveDefaults (table doesn't exist, not used by frontend)


class CRUDUserNutrientFocus:
    @staticmethod
    def list_for_user(db: Session, user_id: int) -> List[UserNutrientFocus]:
        return db.query(UserNutrientFocus).options(joinedload(UserNutrientFocus.nutrient)).filter(
            and_(UserNutrientFocus.user_id == user_id, UserNutrientFocus.is_active == True)
        ).all()


nutrition_objectives = CRUDNutritionObjectives()
nutrient_catalog = CRUDNutrientCatalog()
nutrition_goals = CRUDNutritionGoals()
# Removed: objective_defaults = CRUDObjectiveDefaults()
user_nutrient_focus = CRUDUserNutrientFocus()
