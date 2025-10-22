from fastapi import APIRouter, Depends, HTTPException
from typing import Any
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session

from app import models
from app.api import deps
from app.core.config import settings
from app.schemas.feedback import (
    FeedbackUploadURLRequest, FeedbackUploadURLResponse,
    FeedbackCreate, Feedback, FeedbackUpdate
)
from app.crud.feedback import feedback as feedback_crud

router = APIRouter()


@router.post("/screenshot/upload-url", response_model=FeedbackUploadURLResponse)
def get_screenshot_upload_url(
    payload: FeedbackUploadURLRequest,
    current_user_or_doctor: models.User | models.Doctor = Depends(deps.get_current_user_or_doctor)
) -> Any:
    if not settings.USE_S3_UPLOADS:
        raise HTTPException(status_code=400, detail="S3 uploads are disabled")

    # Build key: feedback/{user_or_anon}/YYYY/MM/DD/{uuid}.jpg
    today = datetime.utcnow()
    date_prefix = today.strftime("%Y/%m/%d")
    user_prefix = (
        str(getattr(current_user_or_doctor, "id", "anon"))
        if current_user_or_doctor and getattr(current_user_or_doctor, "id", None)
        else "anon"
    )
    ext = "jpg" if payload.contentType == "image/jpeg" else "png"
    file_id = uuid4().hex
    s3_key = f"feedback/{user_prefix}/{date_prefix}/{file_id}.{ext}"

    # Generate presigned PUT URL
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
        client_kwargs = {}
        if getattr(settings, "AWS_DEFAULT_REGION", None):
            client_kwargs["region_name"] = settings.AWS_DEFAULT_REGION
        s3 = boto3.client("s3", **client_kwargs)
        url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": settings.AWS_S3_BUCKET,
                "Key": s3_key,
                "ContentType": payload.contentType,
            },
            ExpiresIn=900,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {e}")

    return FeedbackUploadURLResponse(uploadUrl=url, s3Key=s3_key)


@router.post("/", response_model=Feedback)
def create_feedback(
    *,
    db: Session = Depends(deps.get_db),
    feedback_in: FeedbackCreate,
    current_user_or_doctor: models.User | models.Doctor = Depends(deps.get_current_user_or_doctor)
) -> Any:
    # Persist a record; id is set as UUID string
    try:
        # Ensure id is set (SQLAlchemy Base doesn't auto UUID here)
        from app.models.feedback import FeedbackScreenshot
        if not getattr(FeedbackScreenshot, 'id', None):
            pass
        # Determine submitter type strictly from JWT context
        is_doctor = isinstance(current_user_or_doctor, models.Doctor)
        submitter_type = "doctor" if is_doctor else "user"
        
        obj = feedback_crud.create_with_user(
            db=db,
            obj_in=feedback_in,
            user_id=getattr(current_user_or_doctor, "id", None),
        )
        
        # Normalize app identifier based on role (bundle id mapping as requested)
        # doctor -> com.zivodoc.app, user -> com.zivohealth.app
        obj.app_identifier = "com.zivodoc.app" if submitter_type == "doctor" else "com.zivohealth.app"
        # Set the submitter_type directly on the object
        obj.submitter_type = submitter_type
        db.commit()
        db.refresh(obj)
        # Ensure it has an id if DB doesn't auto-generate
        if not obj.id:
            obj.id = uuid4().hex
            db.add(obj)
            db.commit()
            db.refresh(obj)
        # Enrich with submitter details for dashboard clients
        submitter_role = submitter_type
        # If doctor, always fetch from doctors table using id; else from users
        submitter_name = None
        try:
            if submitter_role == "doctor":
                doc = db.query(models.Doctor).filter(models.Doctor.id == obj.user_id).first()
                if doc:
                    parts = [p for p in [getattr(doc, 'first_name', None), getattr(doc, 'middle_name', None), getattr(doc, 'last_name', None)] if p]
                    composed = " ".join(parts) if parts else None
                    submitter_name = composed or doc.email
            else:
                usr = db.query(models.User).filter(models.User.id == obj.user_id).first()
                if usr:
                    parts = [p for p in [getattr(usr, 'first_name', None), getattr(usr, 'middle_name', None), getattr(usr, 'last_name', None)] if p]
                    composed = " ".join(parts) if parts else None
                    submitter_name = composed or usr.email
        except Exception:
            if hasattr(current_user_or_doctor, 'first_name') or hasattr(current_user_or_doctor, 'last_name'):
                parts = [p for p in [getattr(current_user_or_doctor, 'first_name', None), getattr(current_user_or_doctor, 'middle_name', None), getattr(current_user_or_doctor, 'last_name', None)] if p]
                submitter_name = (" ".join(parts) if parts else None) or getattr(current_user_or_doctor, "email", None)
            else:
                submitter_name = getattr(current_user_or_doctor, "full_name", None) or getattr(current_user_or_doctor, "email", None)
        resp = obj.__dict__.copy()
        resp["submitter_role"] = submitter_role
        resp["submitter_name"] = submitter_name
        return Feedback(**resp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create feedback: {e}")


# Support no-trailing-slash POST as well to avoid 307 redirects from clients
@router.post("", response_model=Feedback, include_in_schema=False)
def create_feedback_no_slash(
    *,
    db: Session = Depends(deps.get_db),
    feedback_in: FeedbackCreate,
    current_user_or_doctor: models.User | models.Doctor = Depends(deps.get_current_user_or_doctor)
) -> Any:
    try:
        from app.models.feedback import FeedbackScreenshot
        is_doctor = isinstance(current_user_or_doctor, models.Doctor)
        submitter_type = "doctor" if is_doctor else "user"
        obj = feedback_crud.create_with_user(
            db=db, obj_in=feedback_in, user_id=getattr(current_user_or_doctor, "id", None)
        )
        # Normalize bundle id per role
        obj.app_identifier = "com.zivodoc.app" if submitter_type == "doctor" else "com.zivohealth.app"
        obj.submitter_type = submitter_type
        if not obj.id:
            from uuid import uuid4 as _uuid4
            obj.id = _uuid4().hex
            db.add(obj)
        db.commit()
        db.refresh(obj)

        submitter_role = submitter_type
        submitter_name = None
        try:
            if submitter_role == "doctor":
                doc = db.query(models.Doctor).filter(models.Doctor.id == obj.user_id).first()
                if doc:
                    parts = [p for p in [getattr(doc, 'first_name', None), getattr(doc, 'middle_name', None), getattr(doc, 'last_name', None)] if p]
                    composed = " ".join(parts) if parts else None
                    submitter_name = composed or doc.email
            else:
                usr = db.query(models.User).filter(models.User.id == obj.user_id).first()
                if usr:
                    parts = [p for p in [getattr(usr, 'first_name', None), getattr(usr, 'middle_name', None), getattr(usr, 'last_name', None)] if p]
                    composed = " ".join(parts) if parts else None
                    submitter_name = composed or usr.email
        except Exception:
            if hasattr(current_user_or_doctor, 'first_name') or hasattr(current_user_or_doctor, 'last_name'):
                parts = [p for p in [getattr(current_user_or_doctor, 'first_name', None), getattr(current_user_or_doctor, 'middle_name', None), getattr(current_user_or_doctor, 'last_name', None)] if p]
                submitter_name = (" ".join(parts) if parts else None) or getattr(current_user_or_doctor, "email", None)
            else:
                submitter_name = getattr(current_user_or_doctor, "full_name", None) or getattr(current_user_or_doctor, "email", None)
        resp = obj.__dict__.copy()
        resp["submitter_role"] = submitter_role
        resp["submitter_name"] = submitter_name
        return Feedback(**resp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create feedback: {e}")


@router.get("/", response_model=list[Feedback])
def list_feedback(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user_or_doctor: models.User | models.Doctor = Depends(deps.get_current_user_or_doctor)
) -> Any:
    # List feedback; submitter_role mirrors submitter_type when available
    items = feedback_crud.list(db=db, skip=skip, limit=limit)
    result: list[Feedback] = []
    for it in items:
        # submitter_role is exactly submitter_type; do not derive
        role = getattr(it, 'submitter_type', None)
        if role not in ("doctor", "user"):
            role = "unknown"

        # Resolve submitter name strictly from the corresponding table
        name = "Anonymous"
        if it.user_id and role == "doctor":
            doc = db.query(models.Doctor).filter(models.Doctor.id == it.user_id).first()
            if doc:
                parts = [p for p in [getattr(doc, 'first_name', None), getattr(doc, 'middle_name', None), getattr(doc, 'last_name', None)] if p]
                composed = " ".join(parts) if parts else None
                name = composed or doc.email or name
        elif it.user_id and role == "user":
            usr = db.query(models.User).filter(models.User.id == it.user_id).first()
            if usr:
                parts = [p for p in [getattr(usr, 'first_name', None), getattr(usr, 'middle_name', None), getattr(usr, 'last_name', None)] if p]
                composed = " ".join(parts) if parts else None
                name = composed or usr.email or name

        payload = it.__dict__.copy()
        payload["submitter_role"] = role
        payload["submitter_name"] = name
        result.append(Feedback(**payload))
    return result


# Support no-trailing-slash GET list
@router.get("", response_model=list[Feedback], include_in_schema=False)
def list_feedback_no_slash(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user_or_doctor: models.User | models.Doctor = Depends(deps.get_current_user_or_doctor)
) -> Any:
    items = feedback_crud.list(db=db, skip=skip, limit=limit)
    result: list[Feedback] = []
    for it in items:
        # submitter_role is exactly submitter_type; do not derive
        role = getattr(it, 'submitter_type', None)
        if role not in ("doctor", "user"):
            role = "unknown"

        # Resolve submitter name strictly from the corresponding table
        name = "Anonymous"
        if it.user_id and role == "doctor":
            doc = db.query(models.Doctor).filter(models.Doctor.id == it.user_id).first()
            if doc:
                parts = [p for p in [getattr(doc, 'first_name', None), getattr(doc, 'middle_name', None), getattr(doc, 'last_name', None)] if p]
                composed = " ".join(parts) if parts else None
                name = composed or doc.email or name
        elif it.user_id and role == "user":
            usr = db.query(models.User).filter(models.User.id == it.user_id).first()
            if usr:
                parts = [p for p in [getattr(usr, 'first_name', None), getattr(usr, 'middle_name', None), getattr(usr, 'last_name', None)] if p]
                composed = " ".join(parts) if parts else None
                name = composed or usr.email or name

        payload = it.__dict__.copy()
        payload["submitter_role"] = role
        payload["submitter_name"] = name
        result.append(Feedback(**payload))
    return result


@router.get("/{feedback_id}/view-url")
def get_view_url(
    feedback_id: str,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user)
) -> Any:
    from app.services.s3_service import generate_presigned_get_url
    obj = feedback_crud.get(db=db, id=feedback_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Feedback not found")
    s3_uri = f"s3://{settings.AWS_S3_BUCKET}/{obj.s3_key}"
    try:
        url = generate_presigned_get_url(s3_uri, expires_in=900)
        return {"viewUrl": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate view URL: {e}")


@router.patch("/{feedback_id}", response_model=Feedback)
def update_feedback(
    feedback_id: str,
    feedback_update: FeedbackUpdate,
    db: Session = Depends(deps.get_db),
    current_admin: models.Admin = Depends(deps.get_current_active_admin)
) -> Any:
    """Update feedback status and closed date"""
    print(f"🔧 [Feedback Update] Received PATCH request for feedback_id: {feedback_id}")
    print(f"🔧 [Feedback Update] Update data: {feedback_update}")
    print(f"🔧 [Feedback Update] Admin user: {current_admin.email if current_admin else 'None'}")
    
    obj = feedback_crud.get(db=db, id=feedback_id)
    if not obj:
        print(f"❌ [Feedback Update] Feedback not found: {feedback_id}")
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    print(f"✅ [Feedback Update] Found feedback: {obj.id}, current status: {obj.status}")
    print(f"🔧 [Feedback Update] Update data received: status={feedback_update.status}, closed_date={feedback_update.closed_date}")
    print(f"🔧 [Feedback Update] closed_date type: {type(feedback_update.closed_date)}")
    if feedback_update.closed_date:
        print(f"🔧 [Feedback Update] closed_date ISO: {feedback_update.closed_date.isoformat()}")
    
    # Update the feedback
    updated_obj = feedback_crud.update(db=db, db_obj=obj, obj_in=feedback_update)
    print(f"🔧 [Feedback Update] After update - status: {updated_obj.status}, closed_date: {updated_obj.closed_date}")
    
    # Enrich with submitter details for dashboard clients
    role = getattr(updated_obj, 'submitter_type', None)
    if role not in ("doctor", "user"):
        role = "unknown"

    # Resolve submitter name strictly from the corresponding table
    name = "Anonymous"
    if updated_obj.user_id and role == "doctor":
        doc = db.query(models.Doctor).filter(models.Doctor.id == updated_obj.user_id).first()
        if doc:
            parts = [p for p in [getattr(doc, 'first_name', None), getattr(doc, 'middle_name', None), getattr(doc, 'last_name', None)] if p]
            composed = " ".join(parts) if parts else None
            name = composed or doc.email or name
    elif updated_obj.user_id and role == "user":
        usr = db.query(models.User).filter(models.User.id == updated_obj.user_id).first()
        if usr:
            parts = [p for p in [getattr(usr, 'first_name', None), getattr(usr, 'middle_name', None), getattr(usr, 'last_name', None)] if p]
            composed = " ".join(parts) if parts else None
            name = composed or usr.email or name

    payload = updated_obj.__dict__.copy()
    payload["submitter_role"] = role
    payload["submitter_name"] = name
    result = Feedback(**payload)
    print(f"✅ [Feedback Update] Successfully updated feedback {feedback_id} to status: {result.status}, closed_date: {result.closed_date}")
    print(f"🔧 [Feedback Update] Final response payload: {payload}")
    return result


@router.delete("/{feedback_id}")
def delete_feedback(
    feedback_id: str,
    db: Session = Depends(deps.get_db),
    current_admin: models.Admin = Depends(deps.get_current_active_admin)
) -> Any:
    """Delete feedback entry and associated screenshot from S3"""
    print(f"🗑️ [Feedback Delete] Received DELETE request for feedback_id: {feedback_id}")
    print(f"🗑️ [Feedback Delete] Admin user: {current_admin.email if current_admin else 'None'}")
    
    # Get the feedback object
    obj = feedback_crud.get(db=db, id=feedback_id)
    if not obj:
        print(f"❌ [Feedback Delete] Feedback not found: {feedback_id}")
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    print(f"✅ [Feedback Delete] Found feedback: {obj.id}, s3_key: {obj.s3_key}")
    
    # Delete from S3 first (before deleting from DB in case of errors)
    s3_deleted = False
    if obj.s3_key:
        try:
            from app.services.s3_service import delete_file_from_s3
            s3_uri = f"s3://{settings.AWS_S3_BUCKET}/{obj.s3_key}"
            print(f"🗑️ [Feedback Delete] Deleting from S3: {s3_uri}")
            delete_file_from_s3(s3_uri)
            s3_deleted = True
            print(f"✅ [Feedback Delete] Successfully deleted from S3")
        except Exception as e:
            print(f"⚠️ [Feedback Delete] Failed to delete from S3: {e}")
            # Continue with DB deletion even if S3 deletion fails
    
    # Delete from database
    try:
        db.delete(obj)
        db.commit()
        print(f"✅ [Feedback Delete] Successfully deleted feedback from database")
    except Exception as e:
        db.rollback()
        print(f"❌ [Feedback Delete] Failed to delete from database: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete feedback: {e}")
    
    return {
        "message": f"Feedback {feedback_id} deleted successfully",
        "s3_deleted": s3_deleted
    }


