#!/usr/bin/env python3
"""
Script to verify AWS environment configuration and keys
Run this on the AWS instance to check configuration
"""

import os
import sys
import json
from datetime import datetime

def check_environment_variables():
    """Check if required environment variables are set"""
    print("🔍 Checking Environment Variables...")
    print("=" * 50)
    
    required_vars = [
        'APP_SECRET_KEY',
        'VALID_API_KEYS', 
        'DATABASE_URL',
        'ENVIRONMENT'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'SECRET' in var or 'KEY' in var or 'URL' in var:
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
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

def check_hmac_configuration():
    """Check HMAC configuration"""
    print("\n🔐 Checking HMAC Configuration...")
    print("=" * 50)
    
    secret_key = os.getenv('APP_SECRET_KEY')
    if secret_key:
        print(f"✅ APP_SECRET_KEY is set (length: {len(secret_key)})")
        
        # Test HMAC generation
        try:
            from app.utils.hmac import hmac_generator
            test_payload = "test"
            headers = hmac_generator.generateHeaders(test_payload)
            print(f"✅ HMAC generation working")
            print(f"   Test signature: {headers.get('X-Signature', 'N/A')[:16]}...")
        except Exception as e:
            print(f"❌ HMAC generation failed: {e}")
    else:
        print("❌ APP_SECRET_KEY not set")

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

def main():
    """Main verification function"""
    print("🚀 AWS Environment Verification")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    
    # Run all checks
    missing_vars = check_environment_variables()
    check_api_keys()
    check_database_connection()
    check_hmac_configuration()
    check_environment_config()
    
    # Summary
    print("\n📋 Summary")
    print("=" * 50)
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("💡 Set these variables in your AWS environment")
    else:
        print("✅ All required environment variables are set")
    
    print("\n🔧 Next Steps:")
    print("1. If any variables are missing, set them in your AWS environment")
    print("2. If database connection fails, check DATABASE_URL")
    print("3. If no admin users exist, create one using the admin creation script")
    print("4. Restart the application after fixing any issues")

if __name__ == "__main__":
    main()
