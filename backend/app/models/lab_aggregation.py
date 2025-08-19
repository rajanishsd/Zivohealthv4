from sqlalchemy import Column, Integer, String, DateTime, Float, Date, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.db.base import Base

class LabReportDaily(Base):
    """Daily aggregation of lab reports"""
    __tablename__ = "lab_reports_daily"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    test_name = Column(String(255), nullable=False)
    test_code = Column(String(50), nullable=True, index=True)  # Standardized test code for aggregation
    loinc_code = Column(String(20), nullable=True, index=True)  # LOINC code for standardized lab test identification
    test_category = Column(String(100), nullable=False, index=True)
    
    # Aggregated values - changed to String to support mixed numeric/non-numeric values
    avg_value = Column(String(100), nullable=True)
    min_value = Column(String(100), nullable=True)
    max_value = Column(String(100), nullable=True)
    count = Column(Integer, default=1, nullable=False)
    
    # Unit and reference info
    unit = Column(String(50), nullable=True)
    normal_range_min = Column(Float, nullable=True)
    normal_range_max = Column(Float, nullable=True)
    
    # Status based on normal range
    status = Column(String(20), nullable=True)  # 'green', 'amber', 'red'
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_daily_user_date', 'user_id', 'date'),
        Index('idx_daily_category_date', 'test_category', 'date'),
        Index('idx_daily_user_category_date', 'user_id', 'test_category', 'date'),
        Index('idx_daily_test_code', 'test_code'),
        Index('idx_daily_loinc_code', 'loinc_code'),
        Index('idx_daily_user_test_code_date', 'user_id', 'test_code', 'date'),
        Index('idx_daily_user_loinc_code_date', 'user_id', 'loinc_code', 'date'),
        UniqueConstraint('user_id', 'date', 'test_category', 'loinc_code', name='lab_reports_daily_loinc_code_unique'),
    )

class LabReportMonthly(Base):
    """Monthly aggregation of lab reports"""
    __tablename__ = "lab_reports_monthly"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    test_name = Column(String(255), nullable=False)
    test_code = Column(String(50), nullable=True, index=True)  # Standardized test code for aggregation
    loinc_code = Column(String(20), nullable=True, index=True)  # LOINC code for standardized lab test identification
    test_category = Column(String(100), nullable=False, index=True)
    
    # Aggregated values - changed to String to support mixed numeric/non-numeric values
    avg_value = Column(String(100), nullable=True)
    min_value = Column(String(100), nullable=True)
    max_value = Column(String(100), nullable=True)
    count = Column(Integer, default=1, nullable=False)
    
    # Unit and reference info
    unit = Column(String(50), nullable=True)
    normal_range_min = Column(Float, nullable=True)
    normal_range_max = Column(Float, nullable=True)
    
    # Status based on normal range
    status = Column(String(20), nullable=True)  # 'green', 'amber', 'red'
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_monthly_user_year_month', 'user_id', 'year', 'month'),
        Index('idx_monthly_category_year_month', 'test_category', 'year', 'month'),
        Index('idx_monthly_user_category_year_month', 'user_id', 'test_category', 'year', 'month'),
        Index('idx_monthly_test_code', 'test_code'),
        Index('idx_monthly_loinc_code', 'loinc_code'),
        Index('idx_monthly_user_test_code_year_month', 'user_id', 'test_code', 'year', 'month'),
        Index('idx_monthly_user_loinc_code_year_month', 'user_id', 'loinc_code', 'year', 'month'),
        UniqueConstraint('user_id', 'year', 'month', 'test_category', 'loinc_code', name='lab_reports_monthly_loinc_code_unique'),
    )

class LabReportQuarterly(Base):
    """Quarterly aggregation of lab reports"""
    __tablename__ = "lab_reports_quarterly"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)  # 1, 2, 3, 4
    test_name = Column(String(255), nullable=False)
    test_code = Column(String(50), nullable=True, index=True)  # Standardized test code for aggregation
    loinc_code = Column(String(20), nullable=True, index=True)  # LOINC code for standardized lab test identification
    test_category = Column(String(100), nullable=False, index=True)
    
    # Aggregated values - changed to String to support mixed numeric/non-numeric values
    avg_value = Column(String(100), nullable=True)
    min_value = Column(String(100), nullable=True)
    max_value = Column(String(100), nullable=True)
    count = Column(Integer, default=1, nullable=False)
    
    # Unit and reference info
    unit = Column(String(50), nullable=True)
    normal_range_min = Column(Float, nullable=True)
    normal_range_max = Column(Float, nullable=True)
    
    # Status based on normal range
    status = Column(String(20), nullable=True)  # 'green', 'amber', 'red'
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_quarterly_user_year_quarter', 'user_id', 'year', 'quarter'),
        Index('idx_quarterly_category_year_quarter', 'test_category', 'year', 'quarter'),
        Index('idx_quarterly_user_category_year_quarter', 'user_id', 'test_category', 'year', 'quarter'),
        Index('idx_quarterly_test_code', 'test_code'),
        Index('idx_quarterly_loinc_code', 'loinc_code'),
        Index('idx_quarterly_user_test_code_year_quarter', 'user_id', 'test_code', 'year', 'quarter'),
        Index('idx_quarterly_user_loinc_code_year_quarter', 'user_id', 'loinc_code', 'year', 'quarter'),
        UniqueConstraint('user_id', 'year', 'quarter', 'test_category', 'loinc_code', name='lab_reports_quarterly_loinc_code_unique'),
    )

class LabReportYearly(Base):
    """Yearly aggregation of lab reports"""
    __tablename__ = "lab_reports_yearly"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    year = Column(Integer, nullable=False)
    test_name = Column(String(255), nullable=False)
    test_code = Column(String(50), nullable=True, index=True)  # Standardized test code for aggregation
    loinc_code = Column(String(20), nullable=True, index=True)  # LOINC code for standardized lab test identification
    test_category = Column(String(100), nullable=False, index=True)
    
    # Aggregated values - changed to String to support mixed numeric/non-numeric values
    avg_value = Column(String(100), nullable=True)
    min_value = Column(String(100), nullable=True)
    max_value = Column(String(100), nullable=True)
    count = Column(Integer, default=1, nullable=False)
    
    # Unit and reference info
    unit = Column(String(50), nullable=True)
    normal_range_min = Column(Float, nullable=True)
    normal_range_max = Column(Float, nullable=True)
    
    # Status based on normal range
    status = Column(String(20), nullable=True)  # 'green', 'amber', 'red'
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_yearly_user_year', 'user_id', 'year'),
        Index('idx_yearly_category_year', 'test_category', 'year'),
        Index('idx_yearly_user_category_year', 'user_id', 'test_category', 'year'),
        Index('idx_yearly_test_code', 'test_code'),
        Index('idx_yearly_loinc_code', 'loinc_code'),
        Index('idx_yearly_user_test_code_year', 'user_id', 'test_code', 'year'),
        Index('idx_yearly_user_loinc_code_year', 'user_id', 'loinc_code', 'year'),
        UniqueConstraint('user_id', 'year', 'test_category', 'loinc_code', name='lab_reports_yearly_loinc_code_unique'),
    )
