"""
Performance Monitoring Middleware

FastAPI middleware to automatically capture HTTP request metrics
including response times, status codes, and request/response sizes.
"""

import time
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
import logging
from ..core.system_metrics import system_metrics

logger = logging.getLogger(__name__)


class PerformanceMiddleware:
    """Middleware to track HTTP request performance metrics"""
    
    def __init__(self, app):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
            
        # Create request object
        request = Request(scope, receive)
        
        # Skip monitoring for certain paths
        if self._should_skip_monitoring(request.url.path):
            await self.app(scope, receive, send)
            return
            
        # Start timing
        start_time = time.time()
        
        # Track request size
        request_size = 0
        if "content-length" in request.headers:
            try:
                request_size = int(request.headers["content-length"])
            except ValueError:
                pass
                
        # Variables to capture response data
        response_size = 0
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal response_size, status_code
            
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Get response size from headers if available
                headers = dict(message.get("headers", []))
                content_length = headers.get(b"content-length")
                if content_length:
                    try:
                        response_size = int(content_length.decode())
                    except (ValueError, UnicodeDecodeError):
                        pass
                        
            elif message["type"] == "http.response.body":
                # Track body size for responses without content-length
                if "body" in message and response_size == 0:
                    response_size += len(message["body"])
                    
            await send(message)
            
        try:
            # Process request
            await self.app(scope, receive, send_wrapper)
            
        except Exception as e:
            # Track errors
            status_code = 500
            logger.error(f"Request processing error: {e}")
            raise
            
        finally:
            # Calculate response time
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            # Record metrics
            self._record_request_metrics(
                request=request,
                status_code=status_code,
                response_time_ms=response_time_ms,
                request_size=request_size,
                response_size=response_size
            )
            
    def _should_skip_monitoring(self, path: str) -> bool:
        """Determine if we should skip monitoring for this path"""
        skip_paths = [
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/favicon.ico",
            "/static/",
            "/health",
            "/metrics"  # Avoid recursion on metrics endpoints
        ]
        
        return any(path.startswith(skip_path) for skip_path in skip_paths)
        
    def _record_request_metrics(self, request: Request, status_code: int,
                              response_time_ms: float, request_size: int,
                              response_size: int):
        """Record HTTP request metrics"""
        try:
            # Extract client information
            client_ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            # Clean endpoint path (remove query params and path params)
            endpoint = self._clean_endpoint_path(request.url.path)
            
            # Record the metric
            system_metrics.record_http_request(
                method=request.method,
                endpoint=endpoint,
                status_code=status_code,
                response_time_ms=response_time_ms,
                request_size=request_size if request_size > 0 else None,
                response_size=response_size if response_size > 0 else None,
                user_agent=user_agent,
                ip_address=client_ip
            )
            
            # Log slow requests
            if response_time_ms > 2000:
                logger.warning(
                    f"Slow request: {request.method} {endpoint} "
                    f"took {response_time_ms:.0f}ms (status: {status_code})"
                )
                
            # Log errors
            if status_code >= 400:
                logger.warning(
                    f"Request error: {request.method} {endpoint} "
                    f"returned {status_code} in {response_time_ms:.0f}ms"
                )
                
        except Exception as e:
            logger.error(f"Error recording request metrics: {e}")
            
    def _clean_endpoint_path(self, path: str) -> str:
        """Clean endpoint path for consistent grouping"""
        # Remove query parameters
        if "?" in path:
            path = path.split("?")[0]
            
        # Replace path parameters with placeholders
        # This is a simple approach - for more sophisticated path param detection,
        # you might want to integrate with FastAPI's routing system
        path_parts = path.split("/")
        cleaned_parts = []
        
        for part in path_parts:
            if part:
                # Replace UUIDs and numeric IDs with placeholders
                if self._looks_like_uuid(part):
                    cleaned_parts.append("{uuid}")
                elif self._looks_like_id(part):
                    cleaned_parts.append("{id}")
                else:
                    cleaned_parts.append(part)
            else:
                cleaned_parts.append("")
                
        return "/".join(cleaned_parts)
        
    def _looks_like_uuid(self, value: str) -> bool:
        """Check if a string looks like a UUID"""
        if len(value) == 36 and value.count("-") == 4:
            try:
                # Try to parse as UUID
                import uuid
                uuid.UUID(value)
                return True
            except ValueError:
                pass
        return False
        
    def _looks_like_id(self, value: str) -> bool:
        """Check if a string looks like a numeric ID"""
        return value.isdigit() and len(value) <= 20


async def add_performance_middleware(app):
    """Add performance monitoring middleware to FastAPI app"""
    app.add_middleware(PerformanceMiddleware)
    logger.info("Performance monitoring middleware added") 