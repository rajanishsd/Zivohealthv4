from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware 
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import logging
import sys
import os
import warnings

# Suppress pkg_resources deprecation warning from guardrails package
warnings.filterwarnings(
    "ignore", 
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
    module="guardrails.hub.install"
)

# Import core modules (but not API routes yet)
from app.core.config import settings
from app.db.session import engine
from app.core.database_utils import get_db_session
from app.db.base import Base
from app.core.redis import get_redis
from app.core.system_metrics import system_metrics
from app.core.database_metrics import db_monitor
from app.middleware.performance import PerformanceMiddleware
from app.middleware.api_auth import APIKeyMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("server.log")
    ]
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting up ZivoHealth Backend...")
    
    # Check database tables
    try:
        from sqlalchemy import inspect
        from app.db.session import SessionLocal
        
        with get_db_session() as db:
            inspector = inspect(db.bind)
            existing_tables = inspector.get_table_names()
            required_tables = [table.name for table in Base.metadata.tables.values()]
            missing_tables = [table for table in required_tables if table not in existing_tables]
            
            if missing_tables:
                logger.warning(f"Missing database tables: {missing_tables}")
                logger.warning("Please run the database setup script before starting the server:")
                logger.warning("cd deployment && python database_setup.py")
            else:
                logger.info("All required database tables exist")
    except Exception as e:
        logger.warning(f"Could not check database tables: {e}")
    
    # Initialize Redis connection
    try:
        redis_gen = get_redis()
        redis_client = next(redis_gen)
        redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
    
    # Start performance monitoring
    try:
        # Setup database monitoring
        db_monitor.setup_sqlalchemy_monitoring(engine)
        logger.info("Database performance monitoring configured")
        
        # Start system metrics collection
        await system_metrics.start_collection()
        logger.info("System metrics collection started")
    except Exception as e:
        logger.error(f"Failed to start performance monitoring: {e}")
    
    # Verify S3 configuration and access
    try:
        from app.services.s3_service import verify_s3_configuration
        require_write = os.getenv("REQUIRE_S3_WRITE_CHECK", "false").lower() == "true"
        ok, msg = verify_s3_configuration(require_write=require_write)
        if ok:
            logger.info(f"✅ [Startup] S3 check: {msg}")
        else:
            logger.warning(f"⚠️ [Startup] S3 check failed: {msg}. Uploads will use local storage if enabled.")
    except Exception as e:
        logger.error(f"❌ [Startup] S3 verification error: {e}")

    # Event-driven aggregation setup
    try:
        from app.core.background_worker import EventDrivenVitalsAggregationWorker
        
        # Check if there's any pending data and trigger separate worker process
        if os.getenv("PROCESS_PENDING_ON_STARTUP", "true").lower() == "true":
            logger.info("🚀 [Startup] Checking for pending aggregation data...")
            
            # Check if there's pending work without processing it in-process
            from app.db.session import SessionLocal
            from app.crud.vitals import VitalsCRUD
            
            with get_db_session() as db:
                pending_count = len(VitalsCRUD.get_pending_aggregation_entries(db, limit=1))
                if pending_count > 0:
                    logger.info(f"📊 [Startup] Found pending data - triggering separate worker process")
                    
                    # Trigger separate worker process for startup processing
                    import subprocess
                    
                    try:
                        worker_script = os.path.join(os.path.dirname(__file__), "..", "aggregation", "worker_process.py")
                        subprocess.Popen(
                            ["python", worker_script],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=os.path.dirname(worker_script)
                        )
                        logger.info("✅ [Startup] Separate worker process triggered for pending data")
                    except Exception as e:
                        logger.error(f"❌ [Startup] Failed to trigger worker process: {e}")
                else:
                    logger.info("ℹ️ [Startup] No pending aggregation data found")
        else:
            logger.info("⏸️ [Startup] Pending data processing disabled by environment variable")
            
        logger.info("🎯 [Startup] Event-driven aggregation system ready - will trigger on data submission")
        
    except Exception as e:
        logger.error(f"Failed to setup event-driven aggregation: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ZivoHealth Backend...")
    
    # Stop performance monitoring
    try:
        await system_metrics.stop_collection()
        logger.info("System metrics collection stopped")
    except Exception as e:
        logger.error(f"Error stopping performance monitoring: {e}")
    
    logger.info("✅ ZivoHealth Backend shutdown complete")

def validate_configuration():
    """
    Validate that all required configuration is present before starting the application.
    """
    logger.info(f"Validating application configuration for {settings.ENVIRONMENT} environment...")
    
    # Validate email configuration
    required_email_settings = [
        "SMTP_SERVER", "SMTP_PORT", "SMTP_USERNAME", 
        "SMTP_PASSWORD", "FROM_EMAIL", "FRONTEND_URL"
    ]
    
    missing_settings = []
    for setting in required_email_settings:
        if not getattr(settings, setting, None):
            missing_settings.append(setting)
    
    if missing_settings:
        error_msg = f"Missing required email configuration: {', '.join(missing_settings)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate password reset app directory
    if not os.path.exists(settings.PASSWORD_RESET_APP_DIR):
        error_msg = f"Password reset app directory not found: {settings.PASSWORD_RESET_APP_DIR}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # Environment-specific validations
    if settings.is_production:
        logger.info("🔒 Production environment detected - applying strict validations")
        if not settings.FRONTEND_URL.startswith('https://'):
            raise ValueError("Production requires HTTPS for FRONTEND_URL")
        if settings.SMTP_SERVER in ['smtp.gmail.com', 'localhost']:
            raise ValueError("Production should not use development SMTP servers")
    elif settings.is_development:
        logger.info("🛠️ Development environment detected - applying development validations")
        if settings.FRONTEND_URL.startswith('https://') and 'localhost' not in settings.FRONTEND_URL:
            logger.warning("Development environment should typically use HTTP and localhost")
    elif settings.is_staging:
        logger.info("🧪 Staging environment detected")
    
    logger.info(f"✅ Configuration validation passed for {settings.ENVIRONMENT} environment")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application"""
    
    logger.info("Starting create_application()")
    
    # Validate configuration before proceeding
    validate_configuration()
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="ZivoHealth - Healthcare Management and AI-Powered Consultation Platform",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan
    )
    
    logger.info("FastAPI instance created successfully")
    
    # API Key Authentication Middleware (add first to catch all requests)
    if settings.REQUIRE_API_KEY:
        app.add_middleware(APIKeyMiddleware)
    
    # CORS Middleware - Environment-specific origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.info(f"CORS configured for {settings.ENVIRONMENT} environment with origins: {settings.allowed_cors_origins}")
    
    # GZip Middleware for response compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Performance monitoring middleware
    app.add_middleware(PerformanceMiddleware)
    
    # Import and include API routes AFTER middleware setup
    # This delays agent loading until after the app is configured
    try:
        from app.api.v1.api import api_router
        logger.info("API router imported successfully")
    except Exception as e:
        logger.error(f"Failed to import API router: {e}")
        raise
    
    try:
        from app.routes.performance import router as performance_router
        logger.info("Performance router imported successfully")
    except Exception as e:
        logger.error(f"Failed to import performance router: {e}")
        raise
    
    try:
        from app.routes.dashboard import router as dashboard_router
        logger.info("Dashboard router imported successfully")
    except Exception as e:
        logger.error(f"Failed to import dashboard router: {e}")
        raise
    
    app.include_router(api_router, prefix=settings.API_V1_STR)
    app.include_router(performance_router, prefix="/performance")
    app.include_router(dashboard_router, prefix="/dashboard")
    
    # Mount static files for serving uploaded images and documents
    uploads_dir = "data/uploads"
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir, exist_ok=True)
        logger.info(f"Created uploads directory: {uploads_dir}")
    
    app.mount("/data", StaticFiles(directory="data"), name="data")
    logger.info("Static files mounted at /data for serving uploads")
    
    # Mount password reset app (directory already validated in validate_configuration)
    reset_password_dir = settings.PASSWORD_RESET_APP_DIR
    app.mount("/reset-password", StaticFiles(directory=reset_password_dir, html=True), name="reset-password")
    logger.info(f"Password reset app mounted at /reset-password from {reset_password_dir}")
    
    logger.info("create_application() completed successfully")
    
    return app

# Create the FastAPI app instance
app = create_application()

@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint that redirects to API documentation"""
    return RedirectResponse(url=f"{settings.API_V1_STR}/docs")

@app.get("/health", tags=["Health Check"])
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        from app.core.database_utils import get_db_session
        with get_db_session() as db:
            db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    try:
        # Test Redis connection
        redis_gen = get_redis()
        redis_client = next(redis_gen)
        redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_status = "unhealthy"
    
    try:
        # Test S3 status (without write)
        from app.services.s3_service import verify_s3_configuration
        ok, msg = verify_s3_configuration(require_write=False)
        s3_status = "healthy" if ok else "degraded"
        s3_message = msg
    except Exception as e:
        logger.error(f"S3 health check failed: {e}")
        s3_status = "unhealthy"
        s3_message = str(e)
    
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "project": settings.PROJECT_NAME,
        "database": db_status,
        "redis": redis_status,
        "s3": {"status": s3_status, "message": s3_message}
    }

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Global HTTP exception handler"""
    logger.error(f"HTTP {exc.status_code}: {exc.detail} - {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc} - {request.url}")
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error",
            "status_code": 500
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=True,
        log_level="info"
    )
