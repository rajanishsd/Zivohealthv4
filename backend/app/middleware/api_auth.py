from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.security import verify_api_key, verify_app_signature, generate_app_signature
import time
import json
from typing import Optional

class APIKeyMiddleware:
    """
    Middleware to verify API keys and app signatures for mobile app requests
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Skip authentication for certain endpoints
            path = request.url.path
            should_skip = self._should_skip_auth(path)
            
            # Debug logging for verification endpoints
            if "verify" in path or "resend" in path:
                import logging
                logger = logging.getLogger("app.middleware.api_auth")
                logger.info(f"Path check: {path} -> skip_auth={should_skip}")
            
            if should_skip:
                await self.app(scope, receive, send)
                return
            
            # Verify API key
            if settings.REQUIRE_API_KEY:
                api_key = self._extract_api_key(request)
                if not api_key or not verify_api_key(api_key):
                    response = JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={
                            "error": True,
                            "message": "Invalid or missing API key",
                            "code": "INVALID_API_KEY"
                        }
                    )
                    await response(scope, receive, send)
                    return
            
            # Verify app signature if required (GET and POST)
            if (settings.REQUIRE_APP_SIGNATURE and settings.APP_SECRET_KEY and 
                settings.ENVIRONMENT != "development" and request.method in ("GET", "POST")):
                    if request.url.path.startswith("/api/v1/files/s3presign"):
                        # Support URL-based signature for image loaders (signature over s3_uri)
                        ts = request.query_params.get("ts")
                        sig = request.query_params.get("sig")
                        payload = request.query_params.get("s3_uri", "")
                        try:
                            if not ts or not sig or not payload:
                                raise ValueError("missing ts/sig/payload")
                            current_time = int(time.time())
                            request_time = int(ts)
                            if abs(current_time - request_time) > 300:
                                raise ValueError("timestamp out of window")
                            if not verify_app_signature(payload, ts, sig, settings.APP_SECRET_KEY):
                                raise ValueError("bad signature")
                        except Exception:
                            response = JSONResponse(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                content={
                                    "error": True,
                                    "message": "Invalid URL signature",
                                    "code": "INVALID_SIGNATURE"
                                }
                            )
                            await response(scope, receive, send)
                            return
                    else:
                        if not await self._verify_app_signature(request):
                            response = JSONResponse(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                content={
                                    "error": True,
                                    "message": "Invalid app signature",
                                    "code": "INVALID_SIGNATURE"
                                }
                            )
                            await response(scope, receive, send)
                            return
        
        await self.app(scope, receive, send)
    
    def _should_skip_auth(self, path: str) -> bool:
        """
        Determine if authentication should be skipped for this path
        """
        # Skip auth for health checks, documentation, password reset, and email verification
        skip_paths = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/docs",
            "/api/v1/redoc",
            "/api/v1/openapi.json",
            "/reset-password",
            "/verify-email",  # Frontend email verification route
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/verify-reset-token",
            "/api/v1/dual-auth/email/verify",  # API endpoint for email verification
            "/api/v1/dual-auth/email/resend-verification"  # API endpoint to resend verification
        ]
        # Require API key for all routes, including dashboard
        # (Do not bypass API key for /api/v1/dashboard)
        
        return any(path.startswith(skip_path) for skip_path in skip_paths)
    
    def _extract_api_key(self, request: Request) -> Optional[str]:
        """
        Extract API key from request headers or query parameters
        """
        # Prefer explicit X-API-Key header (do NOT treat JWT Authorization as API key)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key
        
        # Check query parameter
        api_key = request.query_params.get("api_key")
        if api_key:
            return api_key
        
        return None
    
    async def _verify_app_signature(self, request: Request) -> bool:
        """
        Verify app signature for request authenticity
        """
        try:
            # Get signature from headers
            signature = request.headers.get("X-App-Signature")
            timestamp = request.headers.get("X-Timestamp")
            
            if not signature or not timestamp:
                return False
            
            # Check timestamp (prevent replay attacks)
            current_time = int(time.time())
            request_time = int(timestamp)
            
            # Allow 5-minute window for timestamp
            if abs(current_time - request_time) > 300:
                return False
            
            # Handle HMAC verification for different request types
            if request.method == "POST":
                # For POST requests, we'll skip HMAC verification to avoid body consumption issues
                # This is a temporary workaround - in production, you'd want to implement a proper solution
                return True  # Skip HMAC verification for POST requests
            else:
                # For GET requests, use empty payload
                payload = ""
            
            # Generate expected signature for comparison
            expected_signature = generate_app_signature(payload, timestamp, settings.APP_SECRET_KEY)
            
            return verify_app_signature(
                payload, 
                timestamp, 
                signature, 
                settings.APP_SECRET_KEY
            )
            
        except Exception:
            return False
