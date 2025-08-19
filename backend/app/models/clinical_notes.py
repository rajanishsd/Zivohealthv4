from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class ClinicalNotes(Base):
    __tablename__ = "clinical_notes"

    id = Column(String(36), primary_key=True)  # UUID compatibility
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Core clinical information
    diagnosis = Column(Text, nullable=True)  # Primary diagnosis/condition
    symptoms_presented = Column(Text, nullable=True)  # Patient symptoms
    doctor_observations = Column(Text, nullable=True)  # Doctor's clinical observations
    clinical_findings = Column(Text, nullable=True)  # Physical exam findings, test results mentioned
    
    # Treatment and care information
    treatment_plan = Column(Text, nullable=True)  # Prescribed treatment plan
    follow_up_recommendations = Column(Text, nullable=True)  # Follow-up care instructions
    vital_signs_mentioned = Column(Text, nullable=True)  # Any vital signs noted in the document
    medical_history_noted = Column(Text, nullable=True)  # Patient medical history mentioned
    
    # Additional clinical context
    visit_date = Column(DateTime(timezone=True), nullable=True)  # Date of the clinical visit
    clinic_or_hospital = Column(String(255), nullable=True)  # Healthcare facility
    attending_physician = Column(String(255), nullable=True)  # Doctor who saw the patient
    specialty = Column(String(100), nullable=True)  # Medical specialty (e.g., Cardiology, Internal Medicine)
    
    # Document metadata
    document_type = Column(String(100), nullable=True)  # e.g., "discharge_summary", "consultation_note", "progress_note"
    document_image_link = Column(String(500), nullable=True)  # Link to source document
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    session = relationship("ChatSession")
    user = relationship("User") 