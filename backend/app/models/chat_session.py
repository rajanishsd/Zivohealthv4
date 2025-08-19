from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_message_at = Column(DateTime(timezone=True), server_default=func.now())
    message_count = Column(Integer, default=0)
    has_verification = Column(Boolean, default=False)
    has_prescriptions = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    enhanced_mode_enabled = Column(Boolean, default=True)  # Backend control for enhanced features

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # File upload support
    file_path = Column(String(500), nullable=True)  # Path to uploaded file
    file_type = Column(String(10), nullable=True)   # File extension (jpg, png, pdf)
    
    # Optional metadata
    tokens_used = Column(Integer)
    response_time_ms = Column(Integer)
    
    # Visualization support
    visualizations = Column(JSON, nullable=True)  # Store visualization metadata as JSON

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    user = relationship("User")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(String(36), primary_key=True)  # Keep as string for UUID compatibility
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    consultation_request_id = Column(Integer, ForeignKey("consultation_requests.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Direct user reference
    
    medication_name = Column(String(255), nullable=False)
    dosage = Column(String(100))
    frequency = Column(String(100))
    instructions = Column(Text)
    duration = Column(String(100))  # New field for prescription duration
    prescribed_by = Column(String(255), nullable=False)
    prescribed_at = Column(DateTime(timezone=True), server_default=func.now())
    prescription_image_link = Column(String(500))  # New field for prescription image URL/path
    
    # Timestamp fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    session = relationship("ChatSession", back_populates="prescriptions")
    consultation_request = relationship("ConsultationRequest")
    user = relationship("User")  # Direct relationship to user 