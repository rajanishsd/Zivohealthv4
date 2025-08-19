from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum

from app.db.base import Base

class PharmacyDataSource(str, Enum):
    """Source of pharmacy data"""
    PHOTO_ANALYSIS = "photo_analysis"
    MANUAL_ENTRY = "manual_entry"
    BARCODE_SCAN = "barcode_scan"
    PRESCRIPTION_IMPORT = "prescription_import"
    API_IMPORT = "api_import"

class MedicationType(str, Enum):
    """Type of medication"""
    PRESCRIPTION = "prescription"
    OTC = "otc"  # Over-the-counter
    SUPPLEMENT = "supplement"
    MEDICAL_DEVICE = "medical_device"
    OTHER = "other"

class PharmacyType(str, Enum):
    """Type of pharmacy"""
    CHAIN_PHARMACY = "chain_pharmacy"
    INDEPENDENT_PHARMACY = "independent_pharmacy"
    HOSPITAL_PHARMACY = "hospital_pharmacy"
    ONLINE_PHARMACY = "online_pharmacy"
    OTHER = "other"

class TimeGranularity(str, Enum):
    """Time granularity for data aggregation"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class PharmacyRawData(Base):
    """Raw pharmacy data from all sources"""
    __tablename__ = "pharmacy_raw_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Medication identification
    medication_name = Column(String, nullable=False)
    brand_name = Column(String, nullable=True)  # Brand name if different from generic
    generic_name = Column(String, nullable=True)  # Generic name
    medication_type = Column(String, nullable=False)  # prescription, otc, supplement, etc.
    dosage_form = Column(String, nullable=True)  # tablet, capsule, liquid, etc.
    strength = Column(String, nullable=True)  # e.g., "500mg", "10ml"
    
    # Prescription details
    quantity = Column(Float, nullable=False)  # Number of units (pills, bottles, etc.)
    quantity_unit = Column(String, nullable=False)  # tablets, capsules, bottles, etc.
    days_supply = Column(Integer, nullable=True)  # Number of days the medication should last
    refills_remaining = Column(Integer, nullable=True)
    
    # Pharmacy information
    pharmacy_name = Column(String, nullable=True)
    pharmacy_type = Column(String, nullable=True)
    pharmacy_address = Column(String, nullable=True)
    pharmacy_phone = Column(String, nullable=True)
    pharmacist_name = Column(String, nullable=True)
    
    # Prescriber information
    prescriber_name = Column(String, nullable=True)
    prescriber_npi = Column(String, nullable=True)
    prescriber_dea = Column(String, nullable=True)
    
    # Financial information
    total_cost = Column(Float, default=0.0)
    insurance_coverage = Column(Float, default=0.0)
    copay_amount = Column(Float, default=0.0)
    deductible_amount = Column(Float, default=0.0)
    
    # Timing
    purchase_date = Column(Date, nullable=False)
    purchase_time = Column(DateTime, nullable=False)
    prescription_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    
    # Source tracking
    data_source = Column(String, nullable=False)  # Store as string to match enum values
    confidence_score = Column(Float)  # AI analysis confidence (0.0-1.0)
    image_url = Column(String)  # Reference to uploaded photo
    
    # Metadata
    notes = Column(Text)  # Additional notes, special instructions, etc.
    prescription_number = Column(String, nullable=True)
    ndc_number = Column(String, nullable=True)  # National Drug Code
    lot_number = Column(String, nullable=True)
    manufacturer = Column(String, nullable=True)
    
    # Aggregation tracking
    aggregation_status = Column(String(20), nullable=False, default='pending')  # pending, processing, completed, failed
    aggregated_at = Column(DateTime, nullable=True)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_pharmacy_user_purchase_date', 'user_id', 'purchase_date'),
        Index('idx_pharmacy_purchase_date_range', 'purchase_date', 'purchase_time'),
        Index('idx_pharmacy_user_source_date', 'user_id', 'data_source', 'purchase_date'),
        Index('idx_pharmacy_aggregation_status', 'aggregation_status', 'user_id', 'purchase_date'),
        Index('idx_pharmacy_medication_type_date', 'medication_type', 'purchase_date'),
        Index('idx_pharmacy_prescription_number', 'prescription_number'),
        Index('idx_pharmacy_ndc_number', 'ndc_number'),
    )


class PharmacyDailyAggregate(Base):
    """Daily aggregated pharmacy data"""
    __tablename__ = "pharmacy_daily_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    
    # Aggregated financial values
    total_spent = Column(Float, default=0.0)
    total_insurance_coverage = Column(Float, default=0.0)
    total_copay = Column(Float, default=0.0)
    total_deductible = Column(Float, default=0.0)
    
    # Medication counts
    total_medications = Column(Integer, default=0)
    prescription_count = Column(Integer, default=0)
    otc_count = Column(Integer, default=0)
    supplement_count = Column(Integer, default=0)
    
    # Pharmacy visits
    unique_pharmacies = Column(Integer, default=0)
    total_visits = Column(Integer, default=0)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Unique constraint on user and date
    __table_args__ = (
        Index('idx_pharmacy_daily_user_date', 'user_id', 'date'),
    )


class PharmacyWeeklyAggregate(Base):
    """Weekly aggregated pharmacy data"""
    __tablename__ = "pharmacy_weekly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    
    # Aggregated financial values
    total_spent = Column(Float, default=0.0)
    total_insurance_coverage = Column(Float, default=0.0)
    total_copay = Column(Float, default=0.0)
    total_deductible = Column(Float, default=0.0)
    average_daily_spent = Column(Float, default=0.0)
    
    # Medication counts
    total_medications = Column(Integer, default=0)
    prescription_count = Column(Integer, default=0)
    otc_count = Column(Integer, default=0)
    supplement_count = Column(Integer, default=0)
    average_daily_medications = Column(Float, default=0.0)
    
    # Pharmacy patterns
    unique_pharmacies = Column(Integer, default=0)
    total_visits = Column(Integer, default=0)
    average_daily_visits = Column(Float, default=0.0)
    most_visited_pharmacy = Column(String, nullable=True)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_pharmacy_weekly_user_date', 'user_id', 'week_start_date'),
    )


class PharmacyMonthlyAggregate(Base):
    """Monthly aggregated pharmacy data"""
    __tablename__ = "pharmacy_monthly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    year = Column(Integer, nullable=False)
    
    # Aggregated financial values
    total_spent = Column(Float, default=0.0)
    total_insurance_coverage = Column(Float, default=0.0)
    total_copay = Column(Float, default=0.0)
    total_deductible = Column(Float, default=0.0)
    average_daily_spent = Column(Float, default=0.0)
    
    # Medication trends
    total_medications = Column(Integer, default=0)
    prescription_count = Column(Integer, default=0)
    otc_count = Column(Integer, default=0)
    supplement_count = Column(Integer, default=0)
    average_daily_medications = Column(Float, default=0.0)
    
    # Pharmacy patterns
    unique_pharmacies = Column(Integer, default=0)
    total_visits = Column(Integer, default=0)
    average_daily_visits = Column(Float, default=0.0)
    most_visited_pharmacy = Column(String, nullable=True)
    
    # Top medications
    most_frequent_medication = Column(String, nullable=True)
    most_expensive_medication = Column(String, nullable=True)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes
    __table_args__ = (
        Index('idx_pharmacy_monthly_user_date', 'user_id', 'year', 'month'),
    )