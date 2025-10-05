from typing import Optional, Any
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.feedback import FeedbackScreenshot
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate


class CRUDFeedback(CRUDBase[FeedbackScreenshot, FeedbackCreate, FeedbackUpdate]):
    def create_with_user(self, db: Session, *, obj_in: FeedbackCreate, user_id: Optional[int]) -> FeedbackScreenshot:
        data = obj_in.model_dump()
        data["user_id"] = user_id
        db_obj = FeedbackScreenshot(**data)  # type: ignore
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def list(self, db: Session, *, skip: int = 0, limit: int = 100) -> list[FeedbackScreenshot]:
        return db.query(FeedbackScreenshot).order_by(FeedbackScreenshot.created_at.desc()).offset(skip).limit(limit).all()


feedback = CRUDFeedback(FeedbackScreenshot)


