"""
File serving endpoints for chat system.
Handles serving plot images and other static files.
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends, Header
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from typing import Optional
from app.core.security import verify_api_key
import os

router = APIRouter()


async def verify_authentication(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    api_key: Optional[str] = Query(None),
    x_app_signature: Optional[str] = Header(None, alias="X-App-Signature"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
    ts: Optional[str] = Query(None),
    sig: Optional[str] = Query(None),
    s3_uri: Optional[str] = Query(None)
) -> str:
    """Verify authentication via API key or HMAC signature"""
    from app.core.config import settings
    from app.core.security import verify_app_signature
    
    # Try API key authentication first
    key = x_api_key or api_key
    if key and verify_api_key(key):
        return key
    
    # Try HMAC signature authentication (header-based)
    if x_app_signature and x_timestamp and settings.APP_SECRET_KEY:
        try:
            # For file access, use empty payload since it's a GET request
            payload = ""
            if verify_app_signature(payload, x_timestamp, x_app_signature, settings.APP_SECRET_KEY):
                return "hmac_authenticated"
        except Exception:
            pass
    
    # Try HMAC signature authentication (query-based for s3presign)
    if ts and sig and s3_uri and settings.APP_SECRET_KEY:
        try:
            if verify_app_signature(s3_uri, ts, sig, settings.APP_SECRET_KEY):
                return "hmac_authenticated"
        except Exception:
            pass
    
    raise HTTPException(status_code=401, detail="Valid API key or HMAC signature required")

@router.get("/plots/{filename}")
async def get_plot_file(filename: str, auth: str = Depends(verify_authentication)):
    """
    Serve plot files from the data/plots directory.
    
    Args:
        filename: Name of the plot file to serve
        
    Returns:
        FileResponse with the plot image
        
    Raises:
        HTTPException: If file not found or invalid filename
    """
    # Security: Only allow certain file extensions
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.svg'}
    file_path = Path(filename)
    
    if file_path.suffix.lower() not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # Security: Prevent directory traversal attacks
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Construct full path
    plots_dir = Path("data/plots")
    full_path = plots_dir / filename
    
    # Check if file exists
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Plot file not found")
    
    # Return file response with appropriate media type
    media_type = "image/png"
    if filename.lower().endswith(('.jpg', '.jpeg')):
        media_type = "image/jpeg"
    elif filename.lower().endswith('.svg'):
        media_type = "image/svg+xml"
    
    return FileResponse(
        path=str(full_path),
        media_type=media_type,
        filename=filename
    )


@router.get("/s3presign")
async def get_s3_presigned_url(
    s3_uri: str = Query(..., description="s3://bucket/key URI"),
    expires_in: int = 900,
    format: str | None = Query(None, description="Optional: 'url' to return signed URL JSON instead of redirect"),
    auth: str = Depends(verify_authentication)
):
    """
    Generate a presigned GET URL for the provided s3:// URI and redirect to it.
    Defaults to 15 minutes expiry.
    """
    try:
        from app.services.s3_service import generate_presigned_get_url, is_s3_uri
        # Normalize common legacy path 'uploads/chat/plots' -> 'uploads/plots'
        if "/uploads/chat/plots/" in s3_uri:
            s3_uri = s3_uri.replace("/uploads/chat/plots/", "/uploads/plots/")
        if not is_s3_uri(s3_uri):
            raise HTTPException(status_code=400, detail="Invalid S3 URI; must start with s3://")
        if expires_in <= 0 or expires_in > 86400:
            raise HTTPException(status_code=400, detail="expires_in must be between 1 and 86400 seconds")
        url = generate_presigned_get_url(s3_uri, expires_in=expires_in)
        if format == "url":
            return JSONResponse(content={"url": url})
        return RedirectResponse(url=url, status_code=307)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {e}")