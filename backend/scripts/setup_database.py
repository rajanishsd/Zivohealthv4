#!/usr/bin/env python3
"""
ZivoHealth Database Setup Script
===============================

Simple script to set up database tables before starting the server.
Run this script before starting the FastAPI server.

Usage:
    python setup_database.py [--check-only]
"""

import sys
import logging
import argparse
from pathlib import Path
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

# Import app modules
from app.db.session import engine, SessionLocal
from app.db.base import Base
from app.core.security import get_password_hash

# Import all models to ensure they are registered with Base.metadata
# This import loads `app/models/__init__.py`, which imports all model modules
from app import models  # noqa: F401

# Import all models to ensure they're registered
from app.models.user import User
from app.models.doctor import Doctor, ConsultationRequest
from app.models.chat_session import ChatMessage, ChatSession

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_connection():
    """Test database connection"""
    logger.info("🔌 Testing database connection...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


def check_tables_exist():
    """Check if all required tables exist"""
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        required_tables = [table.name for table in Base.metadata.tables.values()]
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        logger.info(f"📋 Found {len(existing_tables)} existing tables")
        logger.info(f"📋 Required {len(required_tables)} tables")
        
        if missing_tables:
            logger.warning(f"⚠️ Missing tables: {missing_tables}")
            return False
        else:
            logger.info("✅ All required tables exist")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to check tables: {e}")
        return False


def create_tables():
    """Create all required tables"""
    try:
        logger.info("🏗️ Creating database tables...")
        Base.metadata.create_all(bind=engine)
        
        # Verify tables were created
        inspector = inspect(engine)
        created_tables = inspector.get_table_names()
        logger.info(f"✅ Successfully created {len(created_tables)} tables")
        
        if created_tables:
            logger.info(f"📋 Created tables: {', '.join(created_tables)}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create tables: {e}")
        return False


def create_demo_data():
    """Create basic demo data"""
    logger.info("👥 Creating demo users...")
    try:
        with SessionLocal() as db:
            # Check if demo users already exist
            existing_patient = db.query(User).filter(User.email == "patient@zivohealth.com").first()
            existing_doctor = db.query(User).filter(User.email == "doctor@zivohealth.com").first()
            
            if not existing_patient:
                patient = User(
                    email="patient@zivohealth.com",
                    hashed_password=get_password_hash("patient123"),
                    full_name="Demo Patient",
                    role="patient",
                    is_active=True
                )
                db.add(patient)
                logger.info("✅ Created demo patient: patient@zivohealth.com")
            else:
                logger.info("ℹ️ Demo patient already exists")
            
            if not existing_doctor:
                doctor_user = User(
                    email="doctor@zivohealth.com",
                    hashed_password=get_password_hash("doctor123"),
                    full_name="Dr. Demo Doctor",
                    role="doctor",
                    is_active=True
                )
                db.add(doctor_user)
                logger.info("✅ Created demo doctor: doctor@zivohealth.com")
            else:
                logger.info("ℹ️ Demo doctor already exists")
            
            db.commit()
            return True
            
    except Exception as e:
        logger.error(f"❌ Error creating demo data: {e}")
        return False


def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description='ZivoHealth Database Setup')
    parser.add_argument('--check-only', action='store_true', 
                       help='Only check if tables exist, do not create')
    
    args = parser.parse_args()
    
    logger.info("🚀 ZivoHealth Database Setup")
    logger.info("=" * 40)
    
    # Test database connection
    if not test_connection():
        logger.error("❌ Cannot proceed without database connection")
        sys.exit(1)
    
    # Check if tables exist
    tables_exist = check_tables_exist()
    
    if args.check_only:
        if tables_exist:
            logger.info("✅ Database check passed - all tables exist")
            sys.exit(0)
        else:
            logger.error("❌ Database check failed - missing tables")
            sys.exit(1)
    
    # Create tables if they don't exist
    if not tables_exist:
        if not create_tables():
            logger.error("❌ Failed to create tables")
            sys.exit(1)
    
    # Create demo data
    if not create_demo_data():
        logger.warning("⚠️ Failed to create demo data (tables created successfully)")
    
    # Final verification
    if check_tables_exist():
        logger.info("🎉 Database setup completed successfully!")
        logger.info("")
        logger.info("Demo Login Credentials:")
        logger.info("  Patient: patient@zivohealth.com / patient123")
        logger.info("  Doctor:  doctor@zivohealth.com / doctor123")
        logger.info("")
        logger.info("You can now start the server with:")
        logger.info("  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
    else:
        logger.error("❌ Setup verification failed")
        sys.exit(1)


if __name__ == "__main__":
    main() 