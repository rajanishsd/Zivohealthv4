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
    FeedbackCreate, Feedback
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
                    submitter_name = doc.full_name or doc.email
            else:
                usr = db.query(models.User).filter(models.User.id == obj.user_id).first()
                if usr:
                    submitter_name = usr.full_name or usr.email
        except Exception:
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
                    submitter_name = doc.full_name or doc.email
            else:
                usr = db.query(models.User).filter(models.User.id == obj.user_id).first()
                if usr:
                    submitter_name = usr.full_name or usr.email
        except Exception:
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
                name = doc.full_name or doc.email or name
        elif it.user_id and role == "user":
            usr = db.query(models.User).filter(models.User.id == it.user_id).first()
            if usr:
                name = usr.full_name or usr.email or name

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
                name = doc.full_name or doc.email or name
        elif it.user_id and role == "user":
            usr = db.query(models.User).filter(models.User.id == it.user_id).first()
            if usr:
                name = usr.full_name or usr.email or name

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


