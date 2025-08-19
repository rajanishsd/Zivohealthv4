from typing import Optional
from pydantic import BaseModel, EmailStr, validator, Field
from datetime import datetime, date

# Doctor Schemas
class DoctorBase(BaseModel):
    email: EmailStr
    full_name: str
    date_of_birth: date | None = None
    contact_number: str | None = None
    license_number: str
    specialization: str
    years_experience: int
    bio: Optional[str] = None
    is_available: bool = True

class Doctor(DoctorBase):
    id: int
    rating: float
    total_consultations: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class DoctorCreate(DoctorBase):
    password: str

class DoctorUpdate(BaseModel):
    full_name: Optional[str] = None
    specialization: Optional[str] = None
    bio: Optional[str] = None
    is_available: Optional[bool] = None

class DoctorResponse(DoctorBase):
    id: int
    rating: float
    total_consultations: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class DoctorPublic(BaseModel):
    id: int
    full_name: str
    specialization: str
    years_experience: int
    rating: float
    total_consultations: int = Field(default=0, ge=0)
    bio: Optional[str] = None
    is_available: bool

    @validator('total_consultations', pre=True, always=True)
    def validate_total_consultations(cls, v):
        if v is None:
            return 0
        return v

    @validator('rating', pre=True, always=True)
    def validate_rating(cls, v):
        if v is None:
            return 0.0
        return v

    class Config:
        from_attributes = True

# Clinical Report Schemas
class ClinicalReportBase(BaseModel):
    user_question: str
    ai_response: str
    comprehensive_context: str
    data_sources_summary: Optional[str] = None
    vitals_data: Optional[str] = None
    nutrition_data: Optional[str] = None
    prescription_data: Optional[str] = None
    lab_data: Optional[str] = None
    pharmacy_data: Optional[str] = None
    agent_requirements: Optional[str] = None

class ClinicalReportCreate(ClinicalReportBase):
    user_id: int
    chat_session_id: int
    message_id: Optional[int] = None

class ClinicalReportResponse(ClinicalReportBase):
    id: int
    user_id: int
    chat_session_id: int
    message_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Consultation Request Schemas
class ConsultationRequestBase(BaseModel):
    context: str
    user_question: str
    urgency_level: str = "normal"

class ConsultationRequestCreate(ConsultationRequestBase):
    doctor_id: int
    chat_session_id: Optional[int] = None
    clinical_report_id: Optional[int] = None

class ConsultationRequestUpdate(BaseModel):
    status: Optional[str] = None
    doctor_notes: Optional[str] = None

class SummaryRequest(BaseModel):
    request_id: int

class ConsultationRequestResponse(ConsultationRequestBase):
    id: int
    user_id: int
    doctor_id: int
    chat_session_id: Optional[int] = None
    clinical_report_id: Optional[int] = None
    status: str
    created_at: datetime
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    doctor_notes: Optional[str] = None

    class Config:
        from_attributes = True

class ConsultationRequestWithDoctor(ConsultationRequestResponse):
    doctor: DoctorPublic

    class Config:
        from_attributes = True

class ConsultationRequestWithClinicalReport(ConsultationRequestResponse):
    doctor: DoctorPublic
    clinical_report: Optional[ClinicalReportResponse] = None

    class Config:
        from_attributes = True 