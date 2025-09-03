import os
import uuid
from typing import Dict, Optional

from app.core.config import settings


def _ensure_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass


def _detect_ext(original_filename: Optional[str]) -> str:
    if not original_filename:
        return "bin"
    _, ext = os.path.splitext(original_filename)
    return ext.lstrip(".").lower() or "bin"


def _content_type_for_ext(ext: str) -> str:
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "pdf": "application/pdf",
    }.get(ext.lower(), "application/octet-stream")


def store_file(content_bytes: bytes, original_filename: str, user_id: int, session_id: int) -> Dict[str, str]:
    """
    Store an uploaded file using a common temp folder for processing and a durable storage location.

    Behavior:
    - Always write a temp copy under data/tmp for processing (caller should delete when done)
    - If settings.USE_S3_UPLOADS is True: upload to S3 and return s3:// URL as stored_url
    - Else: write to local persistent folder under data/uploads/chat and return local path as stored_url

    Returns dict with keys: original_name, file_type, temp_path, stored_url, stored_is_s3 ("true"/"false")
    """
    ext = _detect_ext(original_filename)

    # 1) Write temp copy for processing
    is_s3 = bool(getattr(settings, "USE_S3_UPLOADS", False))
    # Use configured temp directory (derived in settings)
    temp_root = os.path.abspath(getattr(settings, "UPLOADS_TMP_DIR"))
    _ensure_dir(temp_root)
    temp_name = f"tmp_{uuid.uuid4().hex}_{user_id}_{session_id}.{ext}"
    temp_path = os.path.abspath(os.path.join(temp_root, temp_name))
    with open(temp_path, "wb") as f_out:
        f_out.write(content_bytes)

    # 2) Durable storage target
    if is_s3:
        # Upload to S3
        from app.services.s3_service import upload_bytes_and_get_uri
        s3_prefix = "uploads/chat"
        if not s3_prefix or str(s3_prefix).strip() == "":
            raise RuntimeError("UPLOADS_S3_PREFIX must be set when USE_S3_UPLOADS is true")
        filename = f"{uuid.uuid4().hex}_{user_id}_{session_id}.{ext}"
        s3_key = f"{s3_prefix.rstrip('/')}/{filename}"
        s3_uri = upload_bytes_and_get_uri(
            bucket=settings.AWS_S3_BUCKET,
            key=s3_key,
            data=content_bytes,
            content_type=_content_type_for_ext(ext),
        )
        stored_url = s3_uri
        stored_is_s3 = "true"
    else:
        # Local persistent path
        local_root = os.path.abspath(getattr(settings, "UPLOADS_LOCAL_DIR"))
        _ensure_dir(local_root)
        filename = f"{uuid.uuid4().hex}_{user_id}_{session_id}.{ext}"
        stored_path = os.path.abspath(os.path.join(local_root, filename))
        with open(stored_path, "wb") as f_out:
            f_out.write(content_bytes)
        stored_url = stored_path
        stored_is_s3 = "false"

    return {
        "original_name": original_filename or "uploaded_file",
        "file_type": ext,
        "temp_path": temp_path,
        "stored_url": stored_url,
        "stored_is_s3": stored_is_s3,
    }


def ensure_local_processing_path(file_path: str) -> str:
    """
    Given a stored URL which may be s3:// or local path, return a local path suitable for
    processing. For S3 URIs, downloads to a temp file and returns the temp path.
    For local paths, returns the original path.
    """
    try:
        from app.services.s3_service import is_s3_uri, download_to_temp
        if is_s3_uri(file_path):
            return download_to_temp(file_path)
        return file_path
    except Exception:
        return file_path


def cleanup_temp_file(path: Optional[str]) -> None:
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


