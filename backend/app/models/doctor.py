from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Float, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    middle_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    contact_number = Column(String, nullable=True)
    license_number = Column(String, unique=True, nullable=False)
    specialization = Column(String, nullable=False)  # e.g., "Cardiology", "General Medicine", etc.
    years_experience = Column(Integer, nullable=False)
    rating = Column(Float, default=0.0)
    total_consultations = Column(Integer, default=0)
    bio = Column(Text)
    is_available = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    timezone_id = Column(Integer, ForeignKey("timezone_dictionary.id"), nullable=True)

    # Relationships
    password_reset_tokens = relationship("PasswordResetToken", back_populates="doctor")
    timezone = relationship("TimezoneDictionary", back_populates="doctors")

    # Derived field for API schemas expecting full_name
    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join([p for p in parts if p and p.strip()]).strip()

class ConsultationRequest(Base):
    __tablename__ = "consultation_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # Foreign key to User
    doctor_id = Column(Integer, nullable=False)  # Foreign key to Doctor
    chat_session_id = Column(Integer, nullable=True)  # Optional: link to chat session
    clinical_report_id = Column(Integer, ForeignKey("clinical_reports.id"), nullable=True)  # Link to clinical report
    context = Column(Text, nullable=False)  # The chat context/summary
    user_question = Column(Text, nullable=False)  # Main health question
    status = Column(String, default="pending")  # pending, accepted, rejected, completed
    urgency_level = Column(String, default="normal")  # low, normal, high, urgent
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    doctor_notes = Column(Text, nullable=True)
    
    # Relationships
    appointments = relationship("Appointment", back_populates="consultation_request")
    clinical_report = relationship("ClinicalReport", back_populates="consultation_requests")

class ClinicalReport(Base):
    __tablename__ = "clinical_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # Foreign key to User
    chat_session_id = Column(Integer, nullable=False)  # Link to chat session
    message_id = Column(Integer, nullable=True)  # Specific message that triggered the report
    user_question = Column(Text, nullable=False)  # The patient's question
    ai_response = Column(Text, nullable=False)  # The AI's response
    
    # Comprehensive health data used for the AI response
    comprehensive_context = Column(Text, nullable=False)  # Full formatted medical context
    
    # Summary of data sources used
    data_sources_summary = Column(Text, nullable=True)  # JSON string of data sources and counts
    
    # Individual data sections (for structured access)
    vitals_data = Column(Text, nullable=True)  # Vitals measurements context
    nutrition_data = Column(Text, nullable=True)  # Nutrition intake context  
    prescription_data = Column(Text, nullable=True)  # Medication context
    lab_data = Column(Text, nullable=True)  # Lab results context
    pharmacy_data = Column(Text, nullable=True)  # Pharmacy data context
    
    # Agent requirements and priorities
    agent_requirements = Column(Text, nullable=True)  # JSON string of what data was requested
    
    # Report metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    consultation_requests = relationship("ConsultationRequest", back_populates="clinical_report") 