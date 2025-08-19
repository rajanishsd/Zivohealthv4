from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.doctor import Doctor, ConsultationRequest
from app.schemas.doctor import DoctorCreate, DoctorUpdate, ConsultationRequestCreate, ConsultationRequestUpdate
from app.core.security import get_password_hash, verify_password
import re

class CRUDDoctor:
    def get(self, db: Session, doctor_id: int) -> Optional[Doctor]:
        return db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def get_by_email(self, db: Session, email: str) -> Optional[Doctor]:
        return db.query(Doctor).filter(Doctor.email == email).first()

    def authenticate(self, db: Session, email: str, password: str) -> Optional[Doctor]:
        doctor = self.get_by_email(db, email=email)
        if not doctor:
            return None
        if not verify_password(password, doctor.hashed_password):
            return None
        return doctor

    def get_available_doctors(self, db: Session) -> List[Doctor]:
        return db.query(Doctor).filter(
            and_(Doctor.is_available == True, Doctor.is_active == True)
        ).all()

    def get_doctors_by_specialization(self, db: Session, specialization: str) -> List[Doctor]:
        return db.query(Doctor).filter(
            and_(
                Doctor.specialization.ilike(f"%{specialization}%"),
                Doctor.is_available == True,
                Doctor.is_active == True
            )
        ).all()

    def get_doctors_by_context(self, db: Session, context: str) -> List[Doctor]:
        """
        Analyze chat context and return relevant doctors.
        This is a simplified version - in production you'd use ML/NLP.
        """
        context_lower = context.lower()
        
        # Define keyword mappings to specializations
        specialization_keywords = {
            "cardiology": ["heart", "blood pressure", "chest pain", "cardio", "cardiac"],
            "dermatology": ["skin", "rash", "acne", "eczema", "dermatitis"],
            "endocrinology": ["diabetes", "thyroid", "hormone", "insulin", "sugar"],
            "gastroenterology": ["stomach", "digestion", "nausea", "gastro", "intestinal"],
            "neurology": ["headache", "migraine", "brain", "neurological", "seizure"],
            "orthopedics": ["bone", "joint", "fracture", "arthritis", "muscle"],
            "pediatrics": ["child", "baby", "infant", "pediatric", "kids"],
            "psychiatry": ["depression", "anxiety", "mental", "stress", "psychiatric"],
            "general medicine": ["general", "fever", "cold", "flu", "wellness"]
        }
        
        matched_specializations = []
        for specialization, keywords in specialization_keywords.items():
            if any(keyword in context_lower for keyword in keywords):
                matched_specializations.append(specialization)
        
        if not matched_specializations:
            matched_specializations = ["general medicine"]
        
        # Get doctors for matched specializations
        doctors = []
        for spec in matched_specializations:
            docs = self.get_doctors_by_specialization(db, spec)
            doctors.extend(docs)
        
        # Remove duplicates and sort by rating
        unique_doctors = list({doc.id: doc for doc in doctors}.values())
        return sorted(unique_doctors, key=lambda x: x.rating, reverse=True)

    def create(self, db: Session, obj_in: DoctorCreate) -> Doctor:
        hashed_password = get_password_hash(obj_in.password)
        db_obj = Doctor(
            email=obj_in.email,
            hashed_password=hashed_password,
            full_name=obj_in.full_name,
            date_of_birth=obj_in.date_of_birth,
            contact_number=obj_in.contact_number,
            license_number=obj_in.license_number,
            specialization=obj_in.specialization,
            years_experience=obj_in.years_experience,
            bio=obj_in.bio,
            is_available=obj_in.is_available
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, doctor_id: int, obj_in: DoctorUpdate) -> Optional[Doctor]:
        db_obj = self.get(db, doctor_id)
        if db_obj:
            for field, value in obj_in.dict(exclude_unset=True).items():
                setattr(db_obj, field, value)
            db.commit()
            db.refresh(db_obj)
        return db_obj

class CRUDConsultationRequest:
    def get(self, db: Session, request_id: int) -> Optional[ConsultationRequest]:
        return db.query(ConsultationRequest).filter(ConsultationRequest.id == request_id).first()

    def get_user_requests(self, db: Session, user_id: int) -> List[ConsultationRequest]:
        return db.query(ConsultationRequest).filter(ConsultationRequest.user_id == user_id).all()

    def get_doctor_requests(self, db: Session, doctor_id: int, status: Optional[str] = None) -> List[ConsultationRequest]:
        query = db.query(ConsultationRequest).filter(ConsultationRequest.doctor_id == doctor_id)
        if status:
            query = query.filter(ConsultationRequest.status == status)
        return query.all()

    def find_latest_clinical_report_for_session(self, db: Session, chat_session_id: int, user_id: int) -> Optional[int]:
        """Find the most recent clinical report for a chat session and user"""
        from app.models.doctor import ClinicalReport
        
        clinical_report = db.query(ClinicalReport).filter(
            and_(
                ClinicalReport.chat_session_id == chat_session_id,
                ClinicalReport.user_id == user_id
            )
        ).order_by(ClinicalReport.created_at.desc()).first()
        
        return clinical_report.id if clinical_report else None

    def create(self, db: Session, obj_in: ConsultationRequestCreate, user_id: int) -> ConsultationRequest:
        # Automatically link to latest clinical report if chat session is provided
        clinical_report_id = obj_in.clinical_report_id
        if not clinical_report_id and obj_in.chat_session_id:
            clinical_report_id = self.find_latest_clinical_report_for_session(
                db, obj_in.chat_session_id, user_id
            )
            if clinical_report_id:
                print(f"📋 [CRUD] Linking consultation request to clinical report {clinical_report_id}")
        
        db_obj = ConsultationRequest(
            user_id=user_id,
            doctor_id=obj_in.doctor_id,
            chat_session_id=obj_in.chat_session_id,
            clinical_report_id=clinical_report_id,
            context=obj_in.context,
            user_question=obj_in.user_question,
            urgency_level=obj_in.urgency_level
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_status(self, db: Session, request_id: int, obj_in: ConsultationRequestUpdate) -> Optional[ConsultationRequest]:
        db_obj = self.get(db, request_id)
        if db_obj:
            for field, value in obj_in.dict(exclude_unset=True).items():
                setattr(db_obj, field, value)
            
            # Set timestamps based on status
            if obj_in.status == "accepted" and not db_obj.accepted_at:
                from datetime import datetime
                db_obj.accepted_at = datetime.utcnow()
            elif obj_in.status == "completed" and not db_obj.completed_at:
                from datetime import datetime
                db_obj.completed_at = datetime.utcnow()
            
            db.commit()
            db.refresh(db_obj)
        return db_obj

doctor = CRUDDoctor()
consultation_request = CRUDConsultationRequest() 