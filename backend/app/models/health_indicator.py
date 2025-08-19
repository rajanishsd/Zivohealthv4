from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Float, Date
from sqlalchemy.orm import relationship
from app.db.base import Base

class HealthIndicatorCategory(Base):
    """Categories of health indicators (body systems)"""
    __tablename__ = "health_indicator_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # e.g., "Pancreas & Endocrine System"
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    indicators = relationship("HealthIndicator", back_populates="category")

class HealthIndicator(Base):
    """Individual health metrics/indicators"""
    __tablename__ = "health_indicators"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("health_indicator_categories.id"), nullable=False)
    name = Column(String, nullable=False)  # e.g., "Blood Glucose (Fasting)"
    unit = Column(String)  # e.g., "mg/dL", "mmHg", "bpm"
    normal_range_min = Column(Float)
    normal_range_max = Column(Float)
    data_type = Column(String, default="numeric")  # numeric, text, boolean, file
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category = relationship("HealthIndicatorCategory", back_populates="indicators")
    patient_records = relationship("PatientHealthRecord", back_populates="indicator")

class PatientHealthRecord(Base):
    """Current/latest health data for each patient-indicator combination"""
    __tablename__ = "patient_health_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    indicator_id = Column(Integer, ForeignKey("health_indicators.id"), nullable=False)
    
    # Data fields
    numeric_value = Column(Float)
    text_value = Column(Text)
    boolean_value = Column(Boolean)
    file_path = Column(String)  # For storing file paths of reports/images
    
    # Metadata
    recorded_date = Column(Date, nullable=False)
    recorded_by = Column(Integer, ForeignKey("users.id"))  # Doctor/user who recorded
    notes = Column(Text)
    is_abnormal = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("User", foreign_keys=[patient_id])
    indicator = relationship("HealthIndicator", back_populates="patient_records")
    recorded_by_user = relationship("User", foreign_keys=[recorded_by])
    
    # History relationship
    history_records = relationship("HealthDataHistory", back_populates="current_record")

class HealthDataHistory(Base):
    """Historical health data for tracking changes over time"""
    __tablename__ = "health_data_history"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    indicator_id = Column(Integer, ForeignKey("health_indicators.id"), nullable=False)
    current_record_id = Column(Integer, ForeignKey("patient_health_records.id"), nullable=False)
    
    # Data fields (same as PatientHealthRecord)
    numeric_value = Column(Float)
    text_value = Column(Text)
    boolean_value = Column(Boolean)
    file_path = Column(String)
    
    # Metadata
    recorded_date = Column(Date, nullable=False)
    recorded_by = Column(Integer, ForeignKey("users.id"))
    notes = Column(Text)
    is_abnormal = Column(Boolean, default=False)
    
    # Tracking fields
    change_type = Column(String)  # 'insert', 'update', 'delete'
    previous_value = Column(Text)  # JSON representation of previous values
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship("User", foreign_keys=[patient_id])
    indicator = relationship("HealthIndicator")
    current_record = relationship("PatientHealthRecord", back_populates="history_records")
    recorded_by_user = relationship("User", foreign_keys=[recorded_by])

class PatientHealthSummary(Base):
    """Summary statistics and insights for each patient"""
    __tablename__ = "patient_health_summaries"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Summary data
    total_indicators_tracked = Column(Integer, default=0)
    abnormal_indicators_count = Column(Integer, default=0)
    last_updated = Column(DateTime)
    health_score = Column(Float)  # Overall health score (0-100)
    
    # Risk factors
    high_risk_indicators = Column(Text)  # JSON array of indicator IDs
    medium_risk_indicators = Column(Text)  # JSON array of indicator IDs
    
    # Trends
    improving_trends = Column(Text)  # JSON array of indicator IDs
    declining_trends = Column(Text)  # JSON array of indicator IDs
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("User", foreign_keys=[patient_id]) 