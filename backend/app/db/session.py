from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# PostgreSQL configuration with connection pooling
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_size=20,          # Increased from 10 to 20 for concurrent requests + aggregation
    max_overflow=30,       # Increased from 20 to 30 for higher burst capacity
    pool_recycle=300,      # Recycle connections every 5 minutes
    pool_pre_ping=True,    # Validate connections before use
    pool_timeout=45,       # Increased from 30 to 45 seconds timeout
    echo=False             # Set to True for SQL logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 