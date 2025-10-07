from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.api import deps
from app.models.user import User
from app.models.doctor import Doctor
from app.schemas.doctor import (
    DoctorPublic,
    DoctorCreate,
    ConsultationRequestCreate,
    ConsultationRequestResponse,
    ConsultationRequestUpdate,
    ConsultationRequestWithDoctor,
    ConsultationRequestWithClinicalReport,
    ClinicalReportResponse,
    SummaryRequest
)
from app.schemas.chat_session import PrescriptionCreate
from app.doctoragentsv2.doctor_agent import generate_consultation_summary
import uuid

router = APIRouter()

@router.post("/register", response_model=DoctorPublic)
def register_doctor(
    *,
    db: Session = Depends(deps.get_db),
    doctor_in: DoctorCreate,
):
    existing = crud.doctor.get_by_email(db, email=doctor_in.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    doctor = crud.doctor.create(db, obj_in=doctor_in)
    return doctor

@router.get("/available", response_model=List[DoctorPublic])
def get_available_doctors(
    db: Session = Depends(deps.get_db)
):
    """Get all available doctors."""
    doctors = crud.doctor.get_available_doctors(db)
    return doctors

@router.post("/find-by-context", response_model=List[DoctorPublic])
def find_doctors_by_context(
    context: dict,
    db: Session = Depends(deps.get_db)
):
    """
    Find doctors based on chat context.
    Expected payload: {"context": "chat conversation text"}
    """
    chat_context = context.get("context", "")
    if not chat_context:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Context is required"
        )
    
    doctors = crud.doctor.get_doctors_by_context(db, chat_context)
    return doctors

@router.post("/consultation-requests", response_model=ConsultationRequestResponse)
def create_consultation_request(
    request_data: ConsultationRequestCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Create a new consultation request."""
    # Verify doctor exists and is available
    doctor = crud.doctor.get(db, request_data.doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    if not doctor.is_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor is not currently available"
        )
    
    consultation_request = crud.consultation_request.create(
        db, request_data, current_user.id
    )
    return consultation_request

@router.get("/consultation-requests", response_model=List[ConsultationRequestWithDoctor])
def get_user_consultation_requests(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Get all consultation requests for the current user."""
    requests = crud.consultation_request.get_user_requests(db, current_user.id)
    
    # Add doctor information to each request
    result = []
    for req in requests:
        doctor = crud.doctor.get(db, req.doctor_id)
        req_dict = req.__dict__.copy()
        req_dict["doctor"] = doctor
        result.append(req_dict)
    
    return result

@router.get("/consultation-requests/{request_id}", response_model=ConsultationRequestResponse)
def get_consultation_request(
    request_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """Get a specific consultation request."""
    consultation_request = crud.consultation_request.get(db, request_id)
    if not consultation_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation request not found"
        )
    
    # Verify user owns this request
    if consultation_request.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return consultation_request

@router.get("/consultation-requests/{request_id}/status", response_model=ConsultationRequestResponse)
def get_consultation_request_status(
    request_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    """
    Get consultation request status. 
    Accessible by both the requesting patient and assigned doctor.
    """
    consultation_request = crud.consultation_request.get(db, request_id)
    if not consultation_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation request not found"
        )
    
    # Allow access if user is either the requester or assigned doctor
    # For demo purposes, allow any authenticated user to check status
    # In production, you would verify: 
    # consultation_request.user_id == current_user.id OR consultation_request.doctor_id == current_user.doctor_id
    
    print(f"📊 [Doctor API] Checking status for consultation request {request_id}: {consultation_request.status}")
    return consultation_request

# Doctor-specific endpoints (for doctor app/dashboard)
@router.get("/my-consultation-requests", response_model=List[ConsultationRequestResponse])
def get_doctor_consultation_requests(
    status_filter: str = None,
    db: Session = Depends(deps.get_db),
    current_doctor: Doctor = Depends(deps.get_current_active_doctor)
):
    """
    Get consultation requests for the authenticated doctor.
    
    Optional query parameters:
    - status_filter: Filter by request status (pending, accepted, rejected, etc.)
    """
    
    name_parts = [p for p in [getattr(current_doctor, 'first_name', None), getattr(current_doctor, 'middle_name', None), getattr(current_doctor, 'last_name', None)] if p]
    composed_name = " ".join(name_parts) if name_parts else None
    print(f"🏥 [Doctor Dashboard] Fetching requests for doctor: {composed_name or ''} (ID: {current_doctor.id})")
    requests = crud.consultation_request.get_doctor_requests(
        db, current_doctor.id, status_filter
    )
    print(f"📋 [Doctor Dashboard] Found {len(requests)} requests for {composed_name or ''}")
    
    return requests

@router.patch("/consultation-requests/{request_id}/status", response_model=ConsultationRequestResponse)
async def update_consultation_request_status(
    request_id: int,
    update_data: ConsultationRequestUpdate,
    db: Session = Depends(deps.get_db),
    current_doctor: Doctor = Depends(deps.get_current_active_doctor)
):
    """
    Update consultation request status (accept/reject/complete).
    
    For demo purposes, any authenticated user can update any consultation request.
    In production, this would be restricted to the assigned doctor only.
    """
    consultation_request = crud.consultation_request.get(db, request_id)
    if not consultation_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation request not found"
        )
    
    # Only the assigned doctor can update the consultation status
    if consultation_request.doctor_id != current_doctor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Not assigned to this consultation"
        )
    
    print(f"🔄 [Doctor Dashboard] Updating consultation request {request_id} status to {update_data.status}")
    
    updated_request = crud.consultation_request.update_status(
        db, request_id, update_data
    )
    
    # Broadcast consultation status update to patient's app via WebSocket
    if consultation_request.chat_session_id:
        try:
            session_id = int(consultation_request.chat_session_id)
            
            # Import the WebSocket manager (use global instance)
            from app.websocket import manager as websocket_manager
            
            # Prepare broadcast message with consultation status update
            broadcast_message = {
                "type": "consultation_status_update",
                "consultation_id": request_id,
                "status": update_data.status,
                "session_id": session_id,
                "timestamp": updated_request.completed_at.isoformat() if updated_request.completed_at else None,
                "message": f"Consultation status updated to: {update_data.status}"
            }
            
            # Broadcast to patient's session
            await websocket_manager.broadcast(broadcast_message, session_id)
            
            print(f"📡 [Doctor Dashboard] Broadcasted status '{update_data.status}' to session {session_id}")
            
            # If consultation is completed, also update chat session verification status
            if update_data.status == "completed":
                chat_session = crud.chat_session.get(db, session_id)
                if chat_session:
                    chat_session.has_verification = True
                    db.commit()
                    
                    # Broadcast verification status update
                    verification_message = {
                        "type": "verification_status_update",
                        "session_id": session_id,
                        "has_verification": True,
                        "timestamp": updated_request.completed_at.isoformat()
                    }
                    await websocket_manager.broadcast(verification_message, session_id)
                    
                    print(f"✅ [Doctor Dashboard] Broadcasted verification status to session {session_id}")
            
        except (ValueError, Exception) as e:
            print(f"⚠️ [Doctor Dashboard] Could not broadcast to session: {e}")
    
    return updated_request

@router.post("/generate-summary", response_model=ConsultationRequestResponse)
async def generate_summary(
    summary_request: SummaryRequest,
    db: Session = Depends(deps.get_db),
    current_doctor: Doctor = Depends(deps.get_current_active_doctor)
):
    """
    Generate an AI summary of a consultation request for doctors.
    
    Creates a structured summary emphasizing:
    - Primary Patient Question (single, most recent)
    - Symptom Summary, Agent Responses to Symptoms, Conversation Q&A
    - Report-based addendum when applicable
    """
    consultation_request = crud.consultation_request.get(db, summary_request.request_id)
    if not consultation_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation request not found"
        )
    
    # Only the assigned doctor can generate the summary
    if consultation_request.doctor_id != current_doctor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Not assigned to this consultation"
        )
    
    try:
        # Generate AI summary using centralized doctor agent
        ai_summary = await generate_consultation_summary(
            patient_question=consultation_request.user_question or "",
            conversation_context=consultation_request.context or ""
        )
        print(f"📋 [Doctor API] Generated summary for consultation {summary_request.request_id}")
        
        # Update consultation request with the generated summary
        update_data = ConsultationRequestUpdate(
            doctor_notes=ai_summary
        )
        
        updated_request = crud.consultation_request.update_status(
            db, summary_request.request_id, update_data
        )
        
        print(f"✅ [Doctor API] Updated consultation {summary_request.request_id} with AI summary")
        return updated_request
        
    except Exception as e:
        print(f"❌ [Doctor API] Error generating summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate summary. Please try again."
        )

@router.post("/consultation-requests/{request_id}/prescriptions")
def save_prescriptions_for_consultation(
    request_id: int,
    prescriptions_data: dict,
    db: Session = Depends(deps.get_db),
    current_doctor: Doctor = Depends(deps.get_current_active_doctor)
):
    """
    Save prescriptions for a completed consultation request.
    
    Expected payload: {"prescriptions": [list of prescription objects]}
    """
    from app.schemas.chat_session import ChatSessionCreate
    from app import crud
    
    consultation_request = crud.consultation_request.get(db, request_id)
    if not consultation_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation request not found"
        )
    
    # Only assigned doctor can save prescriptions
    if consultation_request.doctor_id != current_doctor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Not assigned to this consultation"
        )
    
    prescriptions = prescriptions_data.get("prescriptions", [])
    if not prescriptions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No prescriptions provided"
        )
    
    print(f"💊 [Doctor API] Saving {len(prescriptions)} prescriptions for consultation {request_id}")
    
    # If the consultation has a chat session, save prescriptions to that session
    if consultation_request.chat_session_id:
        try:
            session_id = int(consultation_request.chat_session_id)
            for prescription_data in prescriptions:
                prescription_create = PrescriptionCreate(
                    medication_name=prescription_data.get("medication_name", ""),
                    dosage=prescription_data.get("dosage", ""),
                    frequency=prescription_data.get("frequency", ""),
                    instructions=prescription_data.get("instructions", ""),
                    duration=prescription_data.get("duration", ""),
                    prescribed_by=prescription_data.get("prescribed_by", (" ".join([p for p in [getattr(current_doctor, 'first_name', None), getattr(current_doctor, 'middle_name', None), getattr(current_doctor, 'last_name', None)] if p]) or "")),
                    consultation_request_id=request_id,
                    user_id=consultation_request.user_id
                )
                
                crud.prescription.create_with_session(
                    db=db, obj_in=prescription_create, session_id=session_id
                )
                
            print(f"✅ [Doctor API] Successfully saved prescriptions to session {session_id}")
            
        except ValueError as e:
            print(f"❌ [Doctor API] Invalid session ID format: {consultation_request.chat_session_id}")
            # Fall through to create without session
    
    # If no chat session exists, create a temporary one for the prescriptions
    if not consultation_request.chat_session_id:
        print(f"⚠️ [Doctor API] No chat session associated with consultation {request_id}, creating one...")
        
        # Create a chat session for this consultation
        session_data = ChatSessionCreate(
            title=f"Consultation #{request_id} - Prescriptions",
            has_prescriptions=True
        )
        
        # Create chat session associated with the user who made the consultation request
        chat_session = crud.chat_session.create_with_user(
            db=db, obj_in=session_data, user_id=consultation_request.user_id
        )
        
        print(f"✅ [Doctor API] Created chat session {chat_session.id} for consultation {request_id}")
        
        # Update consultation request with the new session ID
        consultation_request.chat_session_id = str(chat_session.id)
        db.commit()
        
        # Now save prescriptions to the new session
        for prescription_data in prescriptions:
            prescription_create = PrescriptionCreate(
                medication_name=prescription_data.get("medication_name", ""),
                dosage=prescription_data.get("dosage", ""),
                frequency=prescription_data.get("frequency", ""),
                instructions=prescription_data.get("instructions", ""),
                duration=prescription_data.get("duration", ""),
                prescribed_by=prescription_data.get("prescribed_by", (" ".join([p for p in [getattr(current_doctor, 'first_name', None), getattr(current_doctor, 'middle_name', None), getattr(current_doctor, 'last_name', None)] if p]) or "")),
                consultation_request_id=request_id,
                user_id=consultation_request.user_id
            )
            
            crud.prescription.create_with_session(
                db=db, obj_in=prescription_create, session_id=chat_session.id
            )
        
        print(f"✅ [Doctor API] Successfully saved {len(prescriptions)} prescriptions to new session {chat_session.id}")
    
    return {"message": f"Successfully saved {len(prescriptions)} prescriptions", "consultation_id": request_id}

@router.get("/consultation-requests/{request_id}/clinical-report", response_model=ClinicalReportResponse)
def get_consultation_clinical_report(
    request_id: int,
    db: Session = Depends(deps.get_db),
    current_doctor: Doctor = Depends(deps.get_current_active_doctor)
):
    """
    Get the clinical report associated with a consultation request.
    Only accessible by the assigned doctor.
    """
    consultation_request = crud.consultation_request.get(db, request_id)
    if not consultation_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation request not found"
        )
    
    # Verify doctor is assigned to this consultation
    if consultation_request.doctor_id != current_doctor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Not assigned to this consultation"
        )
    
    # Get the clinical report
    if not consultation_request.clinical_report_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No clinical report found for this consultation"
        )
    
    clinical_report = crud.clinical_report.get_by_id(db, report_id=consultation_request.clinical_report_id)
    if not clinical_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinical report not found"
        )
    
    name_parts = [p for p in [getattr(current_doctor, 'first_name', None), getattr(current_doctor, 'middle_name', None), getattr(current_doctor, 'last_name', None)] if p]
    composed_name = " ".join(name_parts) if name_parts else None
    print(f"📋 [Doctor Dashboard] Doctor {composed_name or ''} viewing clinical report {clinical_report.id}")
    return clinical_report

@router.get("/consultation-requests/{request_id}/with-clinical-report", response_model=ConsultationRequestWithClinicalReport)
def get_consultation_with_clinical_report(
    request_id: int,
    db: Session = Depends(deps.get_db),
    current_doctor: Doctor = Depends(deps.get_current_active_doctor)
):
    """
    Get consultation request with associated clinical report.
    Only accessible by the assigned doctor.
    """
    consultation_request = crud.consultation_request.get(db, request_id)
    if not consultation_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation request not found"
        )
    
    # Verify doctor is assigned to this consultation
    if consultation_request.doctor_id != current_doctor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Not assigned to this consultation"
        )
    
    # Get doctor information
    doctor = crud.doctor.get(db, consultation_request.doctor_id)
    
    # Get clinical report if available
    clinical_report = None
    if consultation_request.clinical_report_id:
        clinical_report = crud.clinical_report.get_by_id(db, report_id=consultation_request.clinical_report_id)
    
    # Build response with relationships
    response_data = consultation_request.__dict__.copy()
    response_data["doctor"] = doctor
    response_data["clinical_report"] = clinical_report
    
    name_parts = [p for p in [getattr(current_doctor, 'first_name', None), getattr(current_doctor, 'middle_name', None), getattr(current_doctor, 'last_name', None)] if p]
    composed_name = " ".join(name_parts) if name_parts else None
    print(f"📋 [Doctor Dashboard] Doctor {composed_name or ''} viewing consultation {request_id} with clinical report")
    return response_data 