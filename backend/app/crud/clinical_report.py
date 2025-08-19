from typing import Optional, List
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.doctor import ClinicalReport
from app.schemas.doctor import ClinicalReportCreate, ClinicalReportResponse

class CRUDClinicalReport(CRUDBase[ClinicalReport, ClinicalReportCreate, ClinicalReportResponse]):
    def create_clinical_report(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        chat_session_id: int, 
        user_question: str, 
        ai_response: str, 
        comprehensive_context: str,
        message_id: Optional[int] = None,
        data_sources_summary: Optional[str] = None,
        vitals_data: Optional[str] = None,
        nutrition_data: Optional[str] = None,
        prescription_data: Optional[str] = None,
        lab_data: Optional[str] = None,
        pharmacy_data: Optional[str] = None,
        agent_requirements: Optional[str] = None
    ) -> ClinicalReport:
        """Create a new clinical report."""
        db_obj = ClinicalReport(
            user_id=user_id,
            chat_session_id=chat_session_id,
            message_id=message_id,
            user_question=user_question,
            ai_response=ai_response,
            comprehensive_context=comprehensive_context,
            data_sources_summary=data_sources_summary,
            vitals_data=vitals_data,
            nutrition_data=nutrition_data,
            prescription_data=prescription_data,
            lab_data=lab_data,
            pharmacy_data=pharmacy_data,
            agent_requirements=agent_requirements
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_id(self, db: Session, *, report_id: int) -> Optional[ClinicalReport]:
        """Get clinical report by ID."""
        return db.query(ClinicalReport).filter(ClinicalReport.id == report_id).first()

    def get_by_chat_session(self, db: Session, *, chat_session_id: int) -> List[ClinicalReport]:
        """Get all clinical reports for a chat session."""
        return db.query(ClinicalReport).filter(
            ClinicalReport.chat_session_id == chat_session_id
        ).order_by(ClinicalReport.created_at.desc()).all()

    def get_by_user(self, db: Session, *, user_id: int, limit: int = 50) -> List[ClinicalReport]:
        """Get clinical reports for a user."""
        return db.query(ClinicalReport).filter(
            ClinicalReport.user_id == user_id
        ).order_by(ClinicalReport.created_at.desc()).limit(limit).all()

    def get_latest_by_user(self, db: Session, *, user_id: int) -> Optional[ClinicalReport]:
        """Get the most recent clinical report for a user."""
        return db.query(ClinicalReport).filter(
            ClinicalReport.user_id == user_id
        ).order_by(ClinicalReport.created_at.desc()).first()

clinical_report = CRUDClinicalReport(ClinicalReport) 