from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from datetime import datetime

from app.crud.base import CRUDBase
from app.models.appointment import Appointment
from app.models.user import User
from app.models.doctor import Doctor
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate

class CRUDAppointment(CRUDBase[Appointment, AppointmentCreate, AppointmentUpdate]):
    def create_with_patient(
        self, db: Session, *, obj_in: AppointmentCreate, patient_id: int
    ) -> Appointment:
        obj_in_data = obj_in.dict()
        obj_in_data["patient_id"] = patient_id
        obj_in_data["updated_at"] = datetime.utcnow()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_patient_appointments(
        self, db: Session, *, patient_id: int, skip: int = 0, limit: int = 100
    ) -> List[Appointment]:
        return (
            db.query(self.model)
            .options(joinedload(Appointment.doctor), joinedload(Appointment.patient))
            .filter(Appointment.patient_id == patient_id)
            .order_by(Appointment.appointment_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_doctor_appointments(
        self, db: Session, *, doctor_id: int, skip: int = 0, limit: int = 100
    ) -> List[Appointment]:
        return (
            db.query(self.model)
            .options(joinedload(Appointment.doctor), joinedload(Appointment.patient))
            .filter(Appointment.doctor_id == doctor_id)
            .order_by(Appointment.appointment_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_appointment_with_details(
        self, db: Session, *, appointment_id: int, user_id: int, is_doctor: bool = False
    ) -> Optional[Appointment]:
        query = (
            db.query(self.model)
            .options(joinedload(Appointment.doctor), joinedload(Appointment.patient))
            .filter(Appointment.id == appointment_id)
        )
        
        if is_doctor:
            # Doctor can see appointments where they are the doctor
            query = query.filter(Appointment.doctor_id == user_id)
        else:
            # Patient can see appointments where they are the patient
            query = query.filter(Appointment.patient_id == user_id)
        
        return query.first()

    def update_appointment(
        self, db: Session, *, db_obj: Appointment, obj_in: AppointmentUpdate, user_id: int, is_doctor: bool = False
    ) -> Optional[Appointment]:
        # Verify user has permission to update
        if is_doctor:
            if db_obj.doctor_id != user_id:
                return None
        else:
            if db_obj.patient_id != user_id:
                return None
        
        obj_data = obj_in.dict(exclude_unset=True)
        obj_data["updated_at"] = datetime.utcnow()
        
        for field in obj_data:
            setattr(db_obj, field, obj_data[field])
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete_appointment(
        self, db: Session, *, appointment_id: int, user_id: int, is_doctor: bool = False
    ) -> Optional[Appointment]:
        query = db.query(self.model).filter(Appointment.id == appointment_id)
        
        if is_doctor:
            query = query.filter(Appointment.doctor_id == user_id)
        else:
            query = query.filter(Appointment.patient_id == user_id)
            
        obj = query.first()
        if obj:
            db.delete(obj)
            db.commit()
        return obj

appointment = CRUDAppointment(Appointment) 