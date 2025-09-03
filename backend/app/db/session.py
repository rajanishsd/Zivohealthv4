from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Configure database engine with proper connection pooling
if settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
    engine = create_engine(
        settings.SQLALCHEMY_DATABASE_URI,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        echo=False
    )
else:
    # PostgreSQL configuration with connection pooling
    engine = create_engine(
        settings.SQLALCHEMY_DATABASE_URI,
        pool_size=10,          # Increased base pool for concurrent requests
        max_overflow=20,       # Allow more bursts under load
        pool_recycle=300,      # Recycle connections every 5 minutes
        pool_pre_ping=True,    # Validate connections before use
        pool_timeout=30,       # Timeout for getting connection from pool
        echo=False             # Set to True for SQL logging
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 