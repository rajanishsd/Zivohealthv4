from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import jwt
from app import crud, models, schemas
from app.api import deps
from app.core.config import settings
from app.core import security
from app.schemas.appointment import AppointmentWithDetails

router = APIRouter()

@router.post("/", response_model=schemas.Appointment)
def create_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_in: schemas.AppointmentCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create new appointment.
    """
    appointment = crud.appointment.create_with_patient(
        db=db, obj_in=appointment_in, patient_id=current_user.id
    )
    return appointment

def get_current_user_info(token: str = Depends(deps.reusable_oauth2)):
    """Extract user info and role from token"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        user_id = int(payload.get("sub"))
        is_doctor = payload.get("is_doctor", False)
        return {"user_id": user_id, "is_doctor": is_doctor}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

@router.get("/", response_model=List[AppointmentWithDetails])
def read_appointments(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    user_info: dict = Depends(get_current_user_info),
) -> Any:
    """
    Retrieve appointments for current user (patient or doctor).
    """
    user_id = user_info["user_id"]
    is_doctor = user_info["is_doctor"]
    
    if is_doctor:
        # User is a doctor - get appointments where they are the doctor
        appointments = crud.appointment.get_doctor_appointments(
            db, doctor_id=user_id, skip=skip, limit=limit
        )
    else:
        # User is a patient - get appointments where they are the patient
        appointments = crud.appointment.get_patient_appointments(
            db, patient_id=user_id, skip=skip, limit=limit
        )
    
    # Convert to AppointmentWithDetails
    appointments_with_details = []
    for appointment in appointments:
        appointment_dict = {
            **appointment.__dict__,
            "patient_name": appointment.patient.full_name,
            "patient_email": appointment.patient.email,
            "doctor_name": appointment.doctor.full_name,
            "doctor_email": appointment.doctor.email,
        }
        appointments_with_details.append(AppointmentWithDetails(**appointment_dict))
    
    return appointments_with_details

@router.get("/{appointment_id}", response_model=AppointmentWithDetails)
def read_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    user_info: dict = Depends(get_current_user_info),
) -> Any:
    """
    Get appointment by ID.
    """
    user_id = user_info["user_id"]
    is_doctor = user_info["is_doctor"]
    
    appointment = crud.appointment.get_appointment_with_details(
        db=db, appointment_id=appointment_id, user_id=user_id, is_doctor=is_doctor
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    appointment_dict = {
        **appointment.__dict__,
        "patient_name": appointment.patient.full_name,
        "patient_email": appointment.patient.email,
        "doctor_name": appointment.doctor.full_name,
        "doctor_email": appointment.doctor.email,
    }
    return AppointmentWithDetails(**appointment_dict)

@router.put("/{appointment_id}", response_model=schemas.Appointment)
def update_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    appointment_in: schemas.AppointmentUpdate,
    user_info: dict = Depends(get_current_user_info),
) -> Any:
    """
    Update an appointment.
    """
    user_id = user_info["user_id"]
    is_doctor = user_info["is_doctor"]
    
    appointment = crud.appointment.get(db=db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    appointment = crud.appointment.update_appointment(
        db=db, db_obj=appointment, obj_in=appointment_in, user_id=user_id, is_doctor=is_doctor
    )
    if not appointment:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    return appointment

@router.delete("/{appointment_id}", response_model=schemas.Appointment)
def delete_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    user_info: dict = Depends(get_current_user_info),
) -> Any:
    """
    Delete an appointment.
    """
    user_id = user_info["user_id"]
    is_doctor = user_info["is_doctor"]
    
    appointment = crud.appointment.delete_appointment(
        db=db, appointment_id=appointment_id, user_id=user_id, is_doctor=is_doctor
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return appointment 