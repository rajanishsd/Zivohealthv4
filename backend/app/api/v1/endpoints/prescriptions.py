from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app import crud, models
from app.api import deps
from app.models.chat_session import Prescription, ChatSession as ChatSessionModel
from app.models.doctor import ConsultationRequest, Doctor
from app.schemas.chat_session import (
    Prescription as PrescriptionSchema,
    PrescriptionCreate,
    PrescriptionWithSession,
)

router = APIRouter()


@router.post("/session/{session_id}", response_model=PrescriptionSchema)
def add_prescription_to_session(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    prescription_in: PrescriptionCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Add a prescription to a chat session.
    """
    session = crud.chat_session.get_session_with_messages(
        db=db, session_id=session_id, user_id=current_user.id
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    prescription = crud.prescription.create_with_session(
        db=db, obj_in=prescription_in, session_id=session_id
    )
    return prescription


@router.get("/session/{session_id}", response_model=List[PrescriptionSchema])
def get_session_prescriptions(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get prescriptions for a chat session.
    """
    session = crud.chat_session.get_session_with_messages(
        db=db, session_id=session_id, user_id=current_user.id
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    prescriptions = crud.prescription.get_session_prescriptions(
        db=db, session_id=session_id
    )
    return prescriptions


@router.get("", response_model=List[PrescriptionWithSession])
def get_all_user_prescriptions(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get all prescriptions for the current user across all sessions.
    """
    prescriptions = crud.prescription.get_user_prescriptions(
        db=db, user_id=current_user.id, skip=skip, limit=limit
    )
    return prescriptions


@router.get("/grouped", response_model=List[dict])
def get_grouped_prescriptions(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get grouped prescriptions for the current user with enhanced data.
    
    Groups prescriptions by prescription_group_id and includes:
    - Doctor information and consultation details
    - S3 presigned URLs for prescription documents (PDFs/images)
    - All medications within each prescription group
    """
    # If grouping is desired, return grouped prescriptions (one per document/upload)
    try:
        grouped = crud.prescription.get_grouped_by_group_id(
            db=db, user_id=current_user.id, skip=skip, limit=limit
        )
        if grouped:
            result = []
            for group in grouped:
                medications = group.get("medications", [])
                first = medications[0] if medications else None
                doctor_name = "Unknown Doctor"
                consultation_id = None
                if first:
                    # Try to get doctor from consultation request first
                    consultation_request = db.query(ConsultationRequest).filter(
                        ConsultationRequest.chat_session_id == first.session_id
                    ).first()
                    if consultation_request:
                        consultation_id = consultation_request.id
                        doctor = db.query(Doctor).filter(Doctor.id == consultation_request.doctor_id).first()
                        if doctor:
                            doctor_name = doctor.full_name
                    
                    # Fallback: use prescribed_by from the prescription itself
                    if doctor_name == "Unknown Doctor" and first.prescribed_by:
                        doctor_name = first.prescribed_by
                
                # Convert S3 URI to presigned URL if applicable
                prescription_image_link = group.get("prescription_image_link")
                if prescription_image_link:
                    try:
                        from app.services.s3_service import is_s3_uri, generate_presigned_get_url
                        if is_s3_uri(prescription_image_link):
                            prescription_image_link = generate_presigned_get_url(prescription_image_link, expires_in=3600)
                    except Exception as e:
                        print(f"⚠️  Failed to generate presigned URL for prescription image: {e}")
                        # Keep the original link if presigning fails
                        pass
                
                result.append({
                    "prescription_group_id": group.get("prescription_group_id"),
                    "chat_session_id": group.get("session_id"),
                    "consultation_id": consultation_id,
                    "doctor_name": doctor_name,
                    "prescribed_at": group.get("prescribed_at"),
                    "prescription_image_link": prescription_image_link,
                    "medications": [
                        {
                            "id": m.id,
                            "medication_name": m.medication_name,
                            "dosage": m.dosage or "",
                            "frequency": m.frequency or "",
                            "instructions": m.instructions or "",
                            "prescribed_by": m.prescribed_by,
                            "prescribed_at": m.prescribed_at,
                        } for m in medications
                    ]
                })
            return result
    except Exception:
        # Fallback to legacy flat list below if grouping fails for any reason
        pass

    # Legacy flat-mode: Get prescriptions with session data
    prescriptions = db.query(Prescription).join(ChatSessionModel).filter(
        ChatSessionModel.user_id == current_user.id
    ).options(joinedload(Prescription.session)).order_by(
        Prescription.prescribed_at.desc()
    ).offset(skip).limit(limit).all()
    
    result = []
    for prescription in prescriptions:
        # Try to find associated consultation request and doctor
        consultation_request = db.query(ConsultationRequest).filter(
            ConsultationRequest.chat_session_id == prescription.session_id
        ).first()
        
        doctor_name = "Unknown Doctor"
        consultation_id = None
        
        if consultation_request:
            consultation_id = consultation_request.id
            doctor = db.query(Doctor).filter(Doctor.id == consultation_request.doctor_id).first()
            if doctor:
                doctor_name = doctor.full_name
        
        # If no consultation found, use prescribed_by from prescription
        if doctor_name == "Unknown Doctor":
            doctor_name = prescription.prescribed_by or "Unknown Doctor"
        
        prescription_data = {
            "id": str(prescription.id),
            "medication_name": prescription.medication_name,
            "dosage": prescription.dosage or "",
            "frequency": prescription.frequency or "",
            "instructions": prescription.instructions or "",
            "prescribed_by": prescription.prescribed_by,
            "prescribed_at": prescription.prescribed_at.isoformat(),
            "consultation_id": consultation_id or 0,
            "chat_session_id": None if not consultation_request else consultation_request.chat_session_id,
            "doctor_name": doctor_name,
            "session_title": prescription.session.title if prescription.session else "Chat Session"
        }
        result.append(prescription_data)
    
    print(f"📊 [Prescriptions API] Returning {len(result)} grouped prescriptions")
    return result

