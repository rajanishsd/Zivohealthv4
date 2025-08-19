from typing import Optional
from datetime import datetime
from pydantic import BaseModel

# Shared properties
class AppointmentBase(BaseModel):
    title: str
    description: Optional[str] = None
    appointment_date: datetime
    duration_minutes: int = 30
    status: str = "scheduled"
    appointment_type: str = "consultation"
    patient_notes: Optional[str] = None
    doctor_notes: Optional[str] = None

# Properties to receive on appointment creation
class AppointmentCreate(AppointmentBase):
    doctor_id: int
    consultation_request_id: Optional[int] = None

# Properties to receive on appointment update
class AppointmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    appointment_date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    status: Optional[str] = None
    appointment_type: Optional[str] = None
    patient_notes: Optional[str] = None
    doctor_notes: Optional[str] = None

# Properties shared by models stored in DB
class AppointmentInDBBase(AppointmentBase):
    id: int
    patient_id: int
    doctor_id: int
    consultation_request_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Properties to return to client
class Appointment(AppointmentInDBBase):
    pass

# Properties stored in DB
class AppointmentInDB(AppointmentInDBBase):
    pass

# Appointment with user details
class AppointmentWithDetails(Appointment):
    patient_name: str
    patient_email: str
    doctor_name: str
    doctor_email: str 