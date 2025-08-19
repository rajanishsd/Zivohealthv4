from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Float, Boolean, Date, ForeignKey, Index, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.db.base import Base

# Legacy VitalSign model - commented out as it's replaced by the new vitals system
# class VitalSign(Base):
#     """Store patient vital signs data"""
#     __tablename__ = "vital_signs"

#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
#     # Vital measurements
#     blood_pressure_systolic = Column(Integer)  # mmHg
#     blood_pressure_diastolic = Column(Integer)  # mmHg
#     heart_rate = Column(Integer)  # bpm
#     temperature = Column(Float)  # Celsius
#     weight = Column(Float)  # kg
#     height = Column(Float)  # cm
#     bmi = Column(Float)  # calculated
#     oxygen_saturation = Column(Float)  # SpO2 %
#     blood_sugar = Column(Float)  # mg/dL
    
#     # Metadata
#     measurement_date = Column(DateTime, nullable=False, default=datetime.utcnow)
#     device_used = Column(String(100))  # Blood pressure monitor, scale, etc.
#     notes = Column(Text)
#     source = Column(String(50), default="manual")  # manual, device, document
    
#     # Document processing
#     extracted_from_document_id = Column(Integer, ForeignKey("document_processing_logs.id"))
#     confidence_score = Column(Float)  # OCR/extraction confidence
    
#     created_at = Column(DateTime, default=datetime.utcnow)
#     updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

#     # Relationships
#     user = relationship("User")

class LabReport(Base):
    """Store lab test results"""
    __tablename__ = "lab_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Lab details
    test_name = Column(String(255), nullable=False)
    test_category = Column(String(100))  # Blood, Urine, Imaging, etc.
    test_value = Column(String(100))  # Can be numeric or text
    test_unit = Column(String(50))
    reference_range = Column(String(100))
    test_status = Column(String(20))  # Normal, High, Low, Critical
    
    # Lab information
    lab_name = Column(String(255))
    lab_address = Column(Text)
    ordering_physician = Column(String(255))
    test_date = Column(Date, nullable=False)
    report_date = Column(Date)
    
    # Additional data
    test_notes = Column(Text)
    test_methodology = Column(String(255))
    
    # Document processing
    extracted_from_document_id = Column(Integer, ForeignKey("document_processing_logs.id"))
    confidence_score = Column(Float)
    raw_text = Column(Text)  # Original extracted text
    
    # Status tracking
    categorization_status = Column(String(20), default='pending', nullable=False, index=True)  # pending, categorized, insufficient
    failure_reason = Column(String(255), nullable=True)  # Reason for insufficient data
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")

class LabReportCategorized(Base):
    """Store categorized lab test results"""
    __tablename__ = "lab_report_categorized"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    test_name = Column(String(255), nullable=False)
    test_value = Column(String(100), nullable=False)
    test_date = Column(Date, nullable=False)
    
    # Additional columns
    id = Column(Integer)
    test_code = Column(String(50), nullable=True, index=True)  # Standardized test code for aggregation
    loinc_code = Column(String(20), nullable=True, index=True)  # LOINC code for standardized lab test identification
    test_category = Column(String(100))
    test_unit = Column(String(50))
    reference_range = Column(String(100))
    test_status = Column(String(20))
    lab_name = Column(String(255), nullable=True)
    lab_address = Column(Text)
    ordering_physician = Column(String(255))
    report_date = Column(Date)
    test_notes = Column(Text)
    test_methodology = Column(String(255))
    extracted_from_document_id = Column(Integer)
    confidence_score = Column(Float)
    raw_text = Column(Text)
    inferred_test_category = Column(String(100))
    
    # Status tracking
    aggregation_status = Column(String(20), default='pending', nullable=False, index=True)  # pending, complete
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Primary key and table args
    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'loinc_code', 'test_value', 'test_date'),
        {'extend_existing': True}
    )

    # Relationships
    user = relationship("User")

class PharmacyBill(Base):
    """Store pharmacy bills and medication purchases"""
    __tablename__ = "pharmacy_bills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Pharmacy details
    pharmacy_name = Column(String(255), nullable=False)
    pharmacy_address = Column(Text)
    pharmacy_phone = Column(String(20))
    pharmacy_gstin = Column(String(20))
    pharmacy_fssai_license = Column(String(20))
    pharmacy_dl_numbers = Column(JSON)  # Array of DL numbers
    pharmacy_registration_address = Column(Text)
    pharmacy_premise_address = Column(Text)
    pos_location = Column(String(100))
    pharmacist_name = Column(String(255))
    pharmacist_registration_number = Column(String(50))
    
    # Bill information
    bill_type = Column(String(50))  # Tax Invoice, Cash Memo, Bill of Supply, etc.
    bill_number = Column(String(100))
    invoice_number = Column(String(100))  # Separate from bill_number
    order_id = Column(String(100))
    bill_date = Column(Date, nullable=False)
    order_date = Column(Date)
    invoice_date = Column(Date)
    
    # Financial breakdown
    total_amount = Column(Float, nullable=False)
    gross_amount = Column(Float)
    taxable_amount = Column(Float)
    tax_amount = Column(Float)
    cgst_rate = Column(Float)
    cgst_amount = Column(Float)
    sgst_rate = Column(Float)
    sgst_amount = Column(Float)
    igst_rate = Column(Float)
    igst_amount = Column(Float)
    total_gst_amount = Column(Float)
    discount_amount = Column(Float)
    shipping_charges = Column(Float)
    vas_charges = Column(Float)  # Value Added Services charges
    credits_applied = Column(Float)  # Pharmeasy credits, etc.
    payable_amount = Column(Float)
    amount_in_words = Column(Text)
    
    # Customer information
    patient_name = Column(String(255))
    patient_address = Column(Text)
    patient_contact = Column(String(20))
    place_of_supply = Column(String(100))
    
    # Prescription details
    prescription_number = Column(String(100))
    prescribing_doctor = Column(String(255))
    doctor_address = Column(Text)
    
    # Transaction details
    transaction_id = Column(String(100))
    payment_method = Column(String(50))
    transaction_timestamp = Column(DateTime)
    transaction_amount = Column(Float)
    
    # Additional information
    support_contact = Column(String(100))
    compliance_codes = Column(JSON)  # QR codes, barcodes, etc.
    
    # Document processing
    pharmacybill_filepath = Column(String(500))  # Updated field name and type
    confidence_score = Column(Float)
    raw_text = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User")
    medications = relationship("PharmacyMedication", back_populates="bill")

class PharmacyMedication(Base):
    """Individual medications in a pharmacy bill"""
    __tablename__ = "pharmacy_medications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bill_id = Column(Integer, ForeignKey("pharmacy_bills.id"), nullable=False)
    
    # Medication details
    medication_name = Column(String(255), nullable=False)
    generic_name = Column(String(255))
    brand_name = Column(String(255))
    strength = Column(String(100))  # 500mg, 10ml, etc.
    quantity = Column(Integer)
    unit_of_measurement = Column(String(20))  # tablets, ml, gm, etc.
    
    # Manufacturer and regulatory information
    manufacturer_name = Column(String(255))
    hsn_code = Column(String(20))
    batch_number = Column(String(50))
    expiry_date = Column(Date)
    ndc_number = Column(String(20))
    
    # Pricing details
    unit_price = Column(Float)
    mrp = Column(Float)  # Maximum Retail Price
    total_price = Column(Float)
    discount_amount = Column(Float)
    taxable_amount = Column(Float)
    
    # Tax breakdown
    gst_rate = Column(Float)
    gst_amount = Column(Float)
    cgst_rate = Column(Float)
    cgst_amount = Column(Float)
    sgst_rate = Column(Float)
    sgst_amount = Column(Float)
    igst_rate = Column(Float)
    igst_amount = Column(Float)
    
    # Usage instructions
    dosage_instructions = Column(Text)
    frequency = Column(String(100))
    duration = Column(String(100))
    
    # Regulatory information
    prescription_validity_date = Column(Date)
    dispensing_dl_number = Column(String(50))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    bill = relationship("PharmacyBill", back_populates="medications")

class DocumentProcessingLog(Base):
    """Comprehensive logging for document processing workflows"""
    __tablename__ = "document_processing_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Request tracking
    request_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    
    # File details
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255))
    file_size = Column(Integer)
    file_type = Column(String(20))  # pdf, jpg, png
    mime_type = Column(String(100))
    
    # Processing workflow
    document_type = Column(String(50))  # vital_reading, lab_report, prescription, pharmacy_bill
    classification_confidence = Column(Float)
    processing_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    
    # OCR results
    ocr_text = Column(Text)
    ocr_confidence = Column(Float)
    ocr_engine = Column(String(50))
    
    # Extraction results
    extracted_data = Column(JSON)
    structured_data = Column(JSON)
    validation_errors = Column(JSON)
    
    # Database operations
    records_created = Column(JSON)  # What records were created
    records_updated = Column(JSON)  # What records were updated
    
    # Timing and performance
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    processing_duration_ms = Column(Integer)
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Agent workflow tracking
    workflow_steps = Column(JSON)  # LangGraph execution steps
    agent_interactions = Column(JSON)  # Inter-agent communications
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")

class OpenTelemetryTrace(Base):
    """Store OpenTelemetry traces for comprehensive logging"""
    __tablename__ = "opentelemetry_traces"

    id = Column(Integer, primary_key=True, index=True)
    
    # OpenTelemetry identifiers
    trace_id = Column(String(32), nullable=False, index=True)  # 128-bit hex
    span_id = Column(String(16), nullable=False, index=True)   # 64-bit hex
    parent_span_id = Column(String(16))
    
    # Span details
    span_name = Column(String(255), nullable=False)
    span_kind = Column(String(20))  # INTERNAL, CLIENT, SERVER, PRODUCER, CONSUMER
    status_code = Column(String(20))  # OK, ERROR, UNSET
    status_message = Column(Text)
    
    # Timing
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    duration_ms = Column(Float)
    
    # Context and attributes
    service_name = Column(String(100), default="zivohealth-agents")
    operation_name = Column(String(100))
    resource_attributes = Column(JSON)
    span_attributes = Column(JSON)
    span_events = Column(JSON)
    
    # Business context
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    request_id = Column(String(100), index=True)
    document_id = Column(Integer, ForeignKey("document_processing_logs.id"))
    
    # Agent-specific
    agent_name = Column(String(100))
    agent_type = Column(String(50))
    workflow_step = Column(String(100))
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")

class AgentMemory(Base):
    """Store agent memory and context for conversations"""
    __tablename__ = "agent_memory"

    id = Column(Integer, primary_key=True, index=True)
    
    # Context identification
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    agent_name = Column(String(100), nullable=False)
    
    # Memory content
    memory_type = Column(String(50))  # context, preference, history, analysis
    memory_key = Column(String(255))
    memory_value = Column(JSON)
    
    # Metadata
    relevance_score = Column(Float, default=1.0)
    expiry_date = Column(DateTime)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    access_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    session = relationship("ChatSession") 

class MedicalImage(Base):
    """Medical images like X-rays, MRIs, CT scans, ultrasounds"""
    __tablename__ = "medical_images"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Image classification
    image_type = Column(String, nullable=False)  # x-ray, mri, ct-scan, ultrasound, etc.
    body_part = Column(String)  # chest, abdomen, head, knee, etc.
    
    # File information
    image_path = Column(String, nullable=False)  # Path to stored image file
    original_filename = Column(String)
    file_size = Column(Integer)  # File size in bytes
    image_format = Column(String)  # jpg, png, dicom, etc.
    
    # AI Analysis
    ai_summary = Column(Text)  # AI-generated summary of the image
    ai_findings = Column(Text)  # Specific findings identified by AI
    confidence_score = Column(Float)  # AI confidence (0.0-1.0)
    
    # Medical context
    exam_date = Column(Date)  # Date when image was taken
    ordering_physician = Column(String)  # Doctor who ordered the exam
    facility_name = Column(String)  # Where the image was taken
    exam_reason = Column(Text)  # Reason for the examination
    
    # Processing status
    processing_status = Column(String(20), nullable=False, default='pending')  # pending, processed, failed
    processed_at = Column(DateTime)
    
    # Metadata
    notes = Column(Text)  # Additional notes or observations
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_medical_images_user_date', 'user_id', 'exam_date'),
        Index('idx_medical_images_type', 'image_type', 'exam_date'),
        Index('idx_medical_images_body_part', 'body_part', 'exam_date'),
        Index('idx_medical_images_status', 'processing_status', 'user_id'),
    ) 