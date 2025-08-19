from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator
import os

class Settings(BaseSettings):
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

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: dict) -> str:
        if v:
            return v
        user = values.get("POSTGRES_USER")
        server = values.get("POSTGRES_SERVER")
        port = values.get("POSTGRES_PORT")
        db = values.get("POSTGRES_DB")
        return f"postgresql://{user}@{server}:{port}/{db}"

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
    
    # OCR Configuration
    OCR_PROVIDER: str
    OCR_TIMEOUT: int
    OCR_MAX_FILE_SIZE: int
    
    # CORS
    CORS_ORIGINS: List[str]
    
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

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings() 