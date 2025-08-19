from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    consultation_request_id = Column(Integer, ForeignKey("consultation_requests.id"), nullable=True)
    
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    appointment_date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30)
    
    status = Column(String, default="scheduled")  # scheduled, confirmed, cancelled, completed
    appointment_type = Column(String, default="consultation")  # consultation, follow_up, emergency
    
    patient_notes = Column(Text, nullable=True)
    doctor_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = relationship("User", foreign_keys=[patient_id], back_populates="patient_appointments")
    doctor = relationship("Doctor", foreign_keys=[doctor_id])
    consultation_request = relationship("ConsultationRequest", back_populates="appointments") 