from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Index
from sqlalchemy.sql import func
from datetime import datetime
from app.db.base import Base
from app.utils.timezone import local_now_db_expr, local_now_db_func

class LabTestMapping(Base):
    """Mapping table for lab test names to categories"""
    __tablename__ = "lab_test_mappings"

    id = Column(Integer, primary_key=True, index=True)
    test_name = Column(String(255), nullable=False, unique=True, index=True)
    test_name_standardized = Column(String(255), nullable=True, index=True)  # Standardized version of test name
    test_code = Column(String(50), nullable=True, index=True)  # Standardized test code for aggregation
    test_category = Column(String(100), nullable=False, index=True)
    gpt_suggested_category = Column(String(100))  # GPT's original categorization suggestion
    
    # Additional metadata
    description = Column(Text)  # Description of what the test measures
    common_units = Column(String(100))  # Common units for this test
    normal_range_info = Column(Text)  # General normal range information
    loinc_code = Column(String(20), nullable=True, index=True)  # LOINC code for standardized lab test identification
    loinc_source = Column(String(20), nullable=True)  # Source of LOINC code (LOINC or CHATGPT)
    
    # Status and management
    is_active = Column(Boolean, default=True, nullable=False)
    is_standardized = Column(Boolean, default=True, nullable=False)  # Whether this is a standardized test name
    
    # Audit fields
    created_at = Column(DateTime, server_default=local_now_db_expr(), nullable=False)
    updated_at = Column(DateTime, server_default=local_now_db_expr(), onupdate=local_now_db_func(), nullable=False)
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_test_category_active', 'test_category', 'is_active'),
        Index('idx_test_name_category', 'test_name', 'test_category'),
        Index('idx_test_code', 'test_code'),
        Index('idx_test_name_standardized', 'test_name_standardized'),
    )

    def __repr__(self):
        return f"<LabTestMapping(test_name='{self.test_name}', standardized='{self.test_name_standardized}', test_code='{self.test_code}', category='{self.test_category}')>" 