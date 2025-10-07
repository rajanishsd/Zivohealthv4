from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # Made nullable for Google-only users
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_tobe_deleted = Column(Boolean, default=False)
    delete_date = Column(DateTime, nullable=True)
    email_verified_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notifications_enabled = Column(Boolean, nullable=False, default=True)

    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user")
    patient_appointments = relationship("Appointment", foreign_keys="Appointment.patient_id", back_populates="patient")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user")
    identities = relationship("UserIdentity", back_populates="user")
    login_events = relationship("LoginEvent", back_populates="user")
    # Removed timezone relationship; timezone is managed via UserProfile