from typing import List, Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
import os
from urllib.parse import quote_plus
from pathlib import Path
from enum import Enum

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class Settings(BaseSettings):
    # Environment Configuration
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    
    # Project Information
    PROJECT_NAME: str
    VERSION: str  
    PROJECT_VERSION: str
    API_V1_STR: str
    
    # Server settings
    SERVER_HOST: str
    SERVER_PORT: int
    
    # Database - Local PostgreSQL within project directory
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    # JWT Settings
    ALGORITHM: str
    
    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    
    # AWS Configuration for Textract OCR
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: str
    AWS_REGION: str
    AWS_S3_BUCKET: str 
    
    # Timezone configuration (used for user-facing timestamps)
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"
    
    # File Uploads
    USE_S3_UPLOADS: bool = True  # Toggle: False for local dev, True for cloud/S3
    UPLOADS_S3_PREFIX: Optional[str] = "uploads"  # Optional S3 key prefix, e.g., "uploads"
    UPLOADS_TMP_DIR: Optional[str] = None  # Local temp directory for processing (derived if not set)
    UPLOADS_LOCAL_DIR: Optional[str] = None  # Local durable storage when S3 disabled (derived if not set)

    # --- Validators & Derived Settings ---
    @field_validator("AWS_S3_BUCKET", mode="before")
    @classmethod
    def default_bucket_when_blank(cls, v: Optional[str]) -> str:
        # Normalize blank/None to a sensible default so downstream code doesn't see empty string
        if v is None:
            return "zivohealth-data"
        if isinstance(v, str) and v.strip() == "":
            return ""
        return v

    @model_validator(mode="after")
    def _finalize_and_validate(self) -> "Settings":
        # Derive SQLALCHEMY_DATABASE_URI if not provided
        if not self.SQLALCHEMY_DATABASE_URI:
            user = getattr(self, "POSTGRES_USER", None)
            password = getattr(self, "POSTGRES_PASSWORD", None)
            server = getattr(self, "POSTGRES_SERVER", None)
            port = getattr(self, "POSTGRES_PORT", None)
            db = getattr(self, "POSTGRES_DB", None)
            if user and server and port and db:
                safe_user = quote_plus(user)
                if password:
                    safe_password = quote_plus(password)
                    self.SQLALCHEMY_DATABASE_URI = (
                        f"postgresql://{safe_user}:{safe_password}@{server}:{port}/{db}"
                    )
                else:
                    self.SQLALCHEMY_DATABASE_URI = (
                        f"postgresql://{safe_user}@{server}:{port}/{db}"
                    )

        # If S3 is enabled but bucket is missing/blank, auto-disable to avoid runtime 500s
        if self.USE_S3_UPLOADS and (self.AWS_S3_BUCKET is None or str(self.AWS_S3_BUCKET).strip() == ""):
            self.USE_S3_UPLOADS = False
            try:
                print("⚠️ [Config] USE_S3_UPLOADS is True but AWS_S3_BUCKET is blank. Disabling S3 uploads.")
            except Exception:
                pass

        # Parse API keys from environment variable if provided
        if not self.VALID_API_KEYS:
            import os
            api_keys_env = os.getenv("VALID_API_KEYS")
            if api_keys_env:
                try:
                    import json
                    self.VALID_API_KEYS = json.loads(api_keys_env)
                except (json.JSONDecodeError, TypeError):
                    # Fallback: treat as comma-separated string
                    self.VALID_API_KEYS = [key.strip() for key in api_keys_env.split(",") if key.strip()]

        # Derive upload directories if not explicitly provided
        try:
            project_root = Path(__file__).resolve().parents[3]
        except Exception:
            project_root = Path(os.getcwd())

        # UPLOADS_TMP_DIR: default based on environment mode
        if not getattr(self, "UPLOADS_TMP_DIR", None):
            if self.USE_S3_UPLOADS:
                self.UPLOADS_TMP_DIR = "/tmp/zivo"
            else:
                self.UPLOADS_TMP_DIR = str(project_root / "data" / "tmp")

        # UPLOADS_LOCAL_DIR: used when S3 is disabled
        if not getattr(self, "UPLOADS_LOCAL_DIR", None):
            self.UPLOADS_LOCAL_DIR = str(project_root / "data" / "uploads" / "chat")

        return self
    
    # OCR Configuration
    OCR_PROVIDER: str
    OCR_TIMEOUT: int
    OCR_MAX_FILE_SIZE: int
    
    # CORS
    CORS_ORIGINS: List[str]
    
    # API Security
    VALID_API_KEYS: List[str] = []
    APP_SECRET_KEY: Optional[str] = None
    REQUIRE_API_KEY: bool = True
    REQUIRE_APP_SIGNATURE: bool = True
    
    # WebSocket
    WS_MESSAGE_QUEUE: str
    
    # Event-Driven Vitals Aggregation Settings
    VITALS_BATCH_SIZE: int = 20000
    PROCESS_PENDING_ON_STARTUP: bool = True
    
    # Smart Delay Settings for Aggregation
    VITALS_AGGREGATION_DELAY_BULK: int = 60      # Delay for bulk loads (seconds)
    VITALS_AGGREGATION_DELAY_INCREMENTAL: int = 15  # Delay for incremental loads (seconds)
    
    # AI Model Configuration
    # All models default to the main model if not specified
    DEFAULT_AI_MODEL: Optional[str] = None  # Single fallback model
    NUTRITION_AGENT_MODEL: Optional[str] = None  # Nutrition agent model
    NUTRITION_AGENT_TEMPERATURE: float = 0.1  # Nutrition agent temperature
    BASE_AGENT_MODEL: Optional[str] = None
    BASE_AGENT_TEMPERATURE: Optional[float] = None
    CUSTOMER_AGENT_MODEL: Optional[str] = None
    CUSTOMER_AGENT_TEMPERATURE: Optional[float] = None
    MEDICAL_DOCTOR_MODEL: Optional[str] = None
    MEDICAL_DOCTOR_TEMPERATURE: Optional[float] = None
    DOCUMENT_WORKFLOW_MODEL: Optional[str] = None
    DOCUMENT_WORKFLOW_TEMPERATURE: Optional[float] = None
    OPENAI_CLIENT_MODEL: Optional[str] = None
    
    # Enhanced Chat Features Configuration
    ENHANCED_CHAT_MODE_DEFAULT: bool = True  # Default enhanced mode for new sessions
    ENHANCED_CHAT_MODE_OVERRIDE: Optional[bool] = None  # Override for all sessions (None = use per-session)
    USE_CUSTOMER_WORKFLOW: bool = True  # Toggle between enhanced_customer_agent (False) and customer_workflow (True)
    
    # LangSmith Configuration
    LAB_AGENT: Optional[str] = None  # or whatever default you want
    LAB_AGENT_TEMPERATURE: Optional[float] = None
    LAB_AGGREGATION_AGENT_MODEL: Optional[str] = None
    LAB_AGGREGATION_AGENT_TEMPERATURE: Optional[float] = None
    LANGCHAIN_TRACING_V2: Optional[str] = None
    LANGCHAIN_ENDPOINT: Optional[str] = None
    LANGCHAIN_PROJECT: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    
    # E2B Configuration for code execution
    E2B_API_KEY: Optional[str] = None
    SERPAPI_KEY: Optional[str] = None

    # Nutrition Vision Model (for image analysis)
    NUTRITION_VISION_MODEL: Optional[str] = None
    
    # Vitals Agent Models
    VITALS_AGENT_MODEL: Optional[str] = None  # Vitals agent model
    VITALS_VISION_MODEL: Optional[str] = None  # Vitals vision model (for image analysis)
    
    # Pharmacy Agent Models
    PHARMACY_AGENT_MODEL: Optional[str] = None  # Pharmacy agent model
    PHARMACY_VISION_MODEL: Optional[str] = None  # Pharmacy vision model (for image analysis)
    
    # Prescription Clinical Agent Models
    PRESCRIPTION_CLINICAL_AGENT_MODEL: Optional[str] = None  # Prescription clinical agent model
    PRESCRIPTION_CLINICAL_VISION_MODEL: Optional[str] = None  # Prescription clinical vision model (for image analysis)
    PRESCRIPTION_CLINICAL_VISION_MAX_TOKENS: Optional[int] = None  # Prescription clinical vision max tokens
    
    # LiveKit (Self-hosted or Cloud) - used for video consultations
    LIVEKIT_URL: Optional[str] = None  # e.g., wss://your-subdomain.livekit.cloud or ws://<host>:7880
    LIVEKIT_API_KEY: Optional[str] = None
    LIVEKIT_API_SECRET: Optional[str] = None

    # YouTube Configuration for user profile authentication
    YOUTUBE_USER_PROFILE_PATH: Optional[str] = None
    YOUTUBE_BROWSER_TYPE: str = "chrome"  # chrome or firefox
    
    # YouTube Rate Limiting Configuration
    YOUTUBE_REQUEST_DELAY: float = 2.0  # Minimum seconds between requests
    YOUTUBE_MAX_REQUESTS_PER_MINUTE: int = 10  # Maximum requests per minute
    YOUTUBE_BACKOFF_DELAY_MIN: float = 30.0  # Minimum backoff delay on rate limit
    YOUTUBE_BACKOFF_DELAY_MAX: float = 60.0  # Maximum backoff delay on rate limit

    # Email Configuration for Password Reset (Required)
    SMTP_SERVER: str  # SMTP server (e.g., smtp.zoho.in)
    SMTP_PORT: str  # SMTP port (e.g., 587)
    SMTP_USERNAME: str  # SMTP username
    SMTP_PASSWORD: str  # SMTP password
    FROM_EMAIL: str  # From email address
    FRONTEND_URL: str  # Frontend URL for reset links
    PASSWORD_RESET_BASE_URL: Optional[str] = None  # Base URL for password reset links (defaults to FRONTEND_URL)
    PASSWORD_RESET_TOKEN_EXPIRY_MINUTES: str = "30"  # Token expiry in minutes
    
    # Derived API URL for React app (automatically generated from FRONTEND_URL)
    @property
    def api_url_for_react_app(self) -> str:
        """Generate API URL for React app based on FRONTEND_URL"""
        return f"{self.FRONTEND_URL}/api/v1"
    
    # Password Reset App Configuration
    PASSWORD_RESET_APP_DIR: str  # Directory for password reset app
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID: Optional[str] = None  # iOS client ID (no secret needed for mobile apps)
    GOOGLE_WEB_CLIENT_ID: Optional[str] = None  # Web client ID for server-side verification
    GOOGLE_WEB_CLIENT_SECRET: Optional[str] = None  # Web client secret for server-side verification
    
    # OTP Configuration
    OTP_LENGTH: int = 6
    OTP_EXPIRY_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RATE_LIMIT_PER_EMAIL: int = 5  # Max OTP requests per email per day

    # Environment-specific properties
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == Environment.DEVELOPMENT
    
    @property
    def is_staging(self) -> bool:
        return self.ENVIRONMENT == Environment.STAGING
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == Environment.PRODUCTION
    
    @property
    def debug_mode(self) -> bool:
        return self.is_development
    
    @property
    def require_https(self) -> bool:
        return self.is_production
    
    @property
    def cors_origins_development(self) -> List[str]:
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://192.168.0.106:3000",
            "http://192.168.0.106:8000"
        ]
    
    @property
    def cors_origins_production(self) -> List[str]:
        return [
            "https://zivohealth.ai",
            "https://www.zivohealth.ai",
            "https://app.zivohealth.ai"
        ]
    
    @property
    def allowed_cors_origins(self) -> List[str]:
        if self.is_development:
            return self.cors_origins_development
        elif self.is_staging:
            return self.cors_origins_development + self.cors_origins_production
        else:  # production
            return self.cors_origins_production

    @model_validator(mode='after')
    def validate_environment_config(self):
        """Validate environment-specific configuration requirements"""
        if self.is_production:
            # Production-specific validations
            if not self.FRONTEND_URL.startswith('https://'):
                raise ValueError("FRONTEND_URL must use HTTPS in production")
            
            if self.SMTP_SERVER in ['smtp.gmail.com', 'localhost']:
                raise ValueError("Production should not use development SMTP servers")
        
        elif self.is_development:
            # Development-specific validations
            if self.FRONTEND_URL.startswith('https://') and 'localhost' not in self.FRONTEND_URL:
                raise ValueError("Development should use HTTP and localhost for FRONTEND_URL")
        
        return self

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra='ignore')

settings = Settings() 