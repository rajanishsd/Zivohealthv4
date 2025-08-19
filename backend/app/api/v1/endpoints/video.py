from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.api import deps
from sqlalchemy.orm import Session
from app import models
from app.core.config import settings

import base64
import hashlib
import hmac
import json
import time

router = APIRouter()


class VideoTokenRequest(BaseModel):
    room: str
    identity: str
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    ttl_seconds: int = 3600


class VideoTokenResponse(BaseModel):
    token: str


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _sign_jwt(header: dict, payload: dict, secret: str) -> str:
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signing_input = f"{_b64url(header_bytes)}.{_b64url(payload_bytes)}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{signing_input.decode('utf-8')}.{_b64url(signature)}"


@router.post("/token", response_model=VideoTokenResponse)
def create_video_token(
    req: VideoTokenRequest,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    if not settings.LIVEKIT_URL or not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise HTTPException(status_code=503, detail="LiveKit configuration missing on server")

    now = int(time.time())
    exp = now + max(60, min(req.ttl_seconds, 3600 * 6))  # clamp TTL to [60, 6h]

    header = {
        "alg": "HS256",
        "typ": "JWT",
        "kid": settings.LIVEKIT_API_KEY,
    }

    # LiveKit access token payload per LK spec
    payload = {
        "iss": settings.LIVEKIT_API_KEY,
        "sub": req.identity,
        "nbf": now,
        "iat": now,
        "exp": exp,
        "name": req.name or current_user.full_name if hasattr(current_user, "full_name") else req.identity,
        "video": {
            "room": req.room,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
        },
        "metadata": req.metadata or {},
    }

    token = _sign_jwt(header, payload, settings.LIVEKIT_API_SECRET)
    return VideoTokenResponse(token=token)


class VideoConfigResponse(BaseModel):
    url: str


@router.get("/config", response_model=VideoConfigResponse)
def get_video_config(
    current_user: models.User = Depends(deps.get_current_active_user),
):
    if not settings.LIVEKIT_URL:
        raise HTTPException(status_code=503, detail="LiveKit configuration missing on server")
    return VideoConfigResponse(url=settings.LIVEKIT_URL)


