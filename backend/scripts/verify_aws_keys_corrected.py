#!/usr/bin/env python3
"""
Corrected script to verify AWS environment configuration and keys
This checks the actual environment variables used by the application
"""

import os
import sys
import json
from datetime import datetime

def check_environment_variables():
    """Check if required environment variables are set"""
    print("🔍 Checking Environment Variables...")
    print("=" * 50)
    
    # These are the actual environment variables used by the app
    required_vars = [
        'SECRET_KEY',  # Not APP_SECRET_KEY
        'VALID_API_KEYS', 
        'POSTGRES_SERVER',
        'POSTGRES_USER', 
        'POSTGRES_PASSWORD',
        'POSTGRES_DB',
        'POSTGRES_PORT',
        'ENVIRONMENT'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'SECRET' in var or 'KEY' in var or 'PASSWORD' in var:
                masked_value = value[:8] + '...' + value[-4:] if len(value) > 12 else '***'
                print(f"✅ {var}: {masked_value}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: NOT SET")
            missing_vars.append(var)
    
    return missing_vars

def check_api_keys():
    """Check API keys configuration"""
    print("\n🔑 Checking API Keys Configuration...")
    print("=" * 50)
    
    api_keys = os.getenv('VALID_API_KEYS')
    if api_keys:
        try:
            # Try to parse as JSON array
            keys_list = json.loads(api_keys)
            print(f"✅ Found {len(keys_list)} API keys configured")
            for i, key in enumerate(keys_list):
                masked_key = key[:8] + '...' + key[-4:] if len(key) > 12 else '***'
                print(f"   Key {i+1}: {masked_key}")
        except json.JSONDecodeError:
            # Try to parse as comma-separated string
            keys_list = [k.strip() for k in api_keys.split(',')]
            print(f"✅ Found {len(keys_list)} API keys configured")
            for i, key in enumerate(keys_list):
                masked_key = key[:8] + '...' + key[-4:] if len(key) > 12 else '***'
                print(f"   Key {i+1}: {masked_key}")
    else:
        print("❌ VALID_API_KEYS not set")

def check_database_connection():
    """Check database connection"""
    print("\n🗄️ Checking Database Connection...")
    print("=" * 50)
    
    try:
        # Add the current directory to Python path
        sys.path.insert(0, os.getcwd())
        
        from app.db.session import SessionLocal
        from app.models.admin import Admin
        
        db = SessionLocal()
        try:
            # Test database connection
            admin_count = db.query(Admin).count()
            print(f"✅ Database connection successful")
            print(f"✅ Found {admin_count} admin users in database")
            
            # List admin users (masked)
            admins = db.query(Admin).all()
            for admin in admins:
                masked_email = admin.email[:3] + '***' + admin.email[-10:] if len(admin.email) > 13 else '***'
                print(f"   Admin: {masked_email} (Active: {admin.is_active})")
                
        except Exception as e:
            print(f"❌ Database query failed: {e}")
        finally:
            db.close()
            
    except ImportError as e:
        print(f"❌ Cannot import database modules: {e}")
        print("💡 Make sure you're running from the backend directory")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

def check_hmac_configuration():
    """Check HMAC configuration"""
    print("\n🔐 Checking HMAC Configuration...")
    print("=" * 50)
    
    secret_key = os.getenv('SECRET_KEY')  # Note: SECRET_KEY, not APP_SECRET_KEY
    if secret_key:
        print(f"✅ SECRET_KEY is set (length: {len(secret_key)})")
        
        # Test HMAC generation
    try:
        sys.path.insert(0, os.getcwd())
        from app.core.security import generate_app_signature
        import time
        
        test_payload = "test"
        timestamp = str(int(time.time()))
        signature = generate_app_signature(test_payload, timestamp, secret_key)
        print(f"✅ HMAC generation working")
        print(f"   Test signature: {signature[:16]}...")
    except Exception as e:
        print(f"❌ HMAC generation failed: {e}")
    else:
        print("❌ SECRET_KEY not set")

def check_environment_config():
    """Check environment-specific configuration"""
    print("\n🌍 Checking Environment Configuration...")
    print("=" * 50)
    
    environment = os.getenv('ENVIRONMENT', 'development')
    print(f"Environment: {environment}")
    
    # Check if we're in production/staging
    if environment in ['production', 'staging']:
        print("⚠️  Running in production/staging environment")
        
        # Check for production-specific settings
        debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
        print(f"Debug mode: {debug_mode}")
        
        # Check HTTPS requirements
        require_https = os.getenv('REQUIRE_HTTPS', 'False').lower() == 'true'
        print(f"HTTPS required: {require_https}")

def check_database_url():
    """Check if DATABASE_URL is set (alternative to individual POSTGRES_* vars)"""
    print("\n🔗 Checking Database URL...")
    print("=" * 50)
    
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # Mask the password in the URL
        if '://' in database_url and '@' in database_url:
            parts = database_url.split('://')
            if len(parts) == 2:
                protocol = parts[0]
                rest = parts[1]
                if '@' in rest:
                    user_pass, host_db = rest.split('@', 1)
                    if ':' in user_pass:
                        user, _ = user_pass.split(':', 1)
                        masked_url = f"{protocol}://{user}:***@{host_db}"
                    else:
                        masked_url = f"{protocol}://{user_pass}@{host_db}"
                else:
                    masked_url = database_url
            else:
                masked_url = "***"
        else:
            masked_url = "***"
        print(f"✅ DATABASE_URL: {masked_url}")
    else:
        print("❌ DATABASE_URL not set (using individual POSTGRES_* variables)")

def main():
    """Main verification function"""
    print("🚀 AWS Environment Verification (Corrected)")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    
    # Run all checks
    missing_vars = check_environment_variables()
    check_api_keys()
    check_database_url()
    check_database_connection()
    check_hmac_configuration()
    check_environment_config()
    
    # Summary
    print("\n📋 Summary")
    print("=" * 50)
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("💡 Set these variables in your AWS environment")
        print("\n🔧 Required Environment Variables for AWS:")
        print("   SECRET_KEY=your-secret-key")
        print("   VALID_API_KEYS=[\"key1\",\"key2\"] or key1,key2")
        print("   POSTGRES_SERVER=your-db-host")
        print("   POSTGRES_USER=your-db-user")
        print("   POSTGRES_PASSWORD=your-db-password")
        print("   POSTGRES_DB=your-db-name")
        print("   POSTGRES_PORT=5432")
        print("   ENVIRONMENT=production")
    else:
        print("✅ All required environment variables are set")
    
    print("\n🔧 Next Steps:")
    print("1. If any variables are missing, set them in your AWS environment")
    print("2. If database connection fails, check POSTGRES_* variables or DATABASE_URL")
    print("3. If no admin users exist, create one using the admin creation script")
    print("4. Restart the application after fixing any issues")
    print("5. Check application logs for detailed error messages")

if __name__ == "__main__":
    main()
