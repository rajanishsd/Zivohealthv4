#!/usr/bin/env python3
"""
Comprehensive AWS Diagnostic Script
Run this on your AWS instance to diagnose authentication issues
"""

import os
import sys
import json
import subprocess
from datetime import datetime

def print_section(title):
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print(f"{'='*60}")

def check_system_info():
    """Check basic system information"""
    print_section("System Information")
    print(f"Hostname: {os.uname().nodename}")
    print(f"User: {os.getenv('USER', 'unknown')}")
    print(f"Working Directory: {os.getcwd()}")
    print(f"Python Version: {sys.version}")
    print(f"Timestamp: {datetime.now().isoformat()}")

def check_environment_variables():
    """Check all environment variables"""
    print_section("Environment Variables")
    
    critical_vars = [
        'SECRET_KEY',
        'VALID_API_KEYS', 
        'POSTGRES_SERVER',
        'POSTGRES_USER',
        'POSTGRES_PASSWORD',
        'POSTGRES_DB',
        'POSTGRES_PORT',
        'DATABASE_URL',
        'ENVIRONMENT',
        'DEBUG',
        'REDIS_HOST',
        'REDIS_PORT'
    ]
    
    missing_vars = []
    for var in critical_vars:
        value = os.getenv(var)
        if value:
            if any(sensitive in var.upper() for sensitive in ['SECRET', 'KEY', 'PASSWORD', 'URL']):
                masked = value[:8] + '...' + value[-4:] if len(value) > 12 else '***'
                print(f"✅ {var}: {masked}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: NOT SET")
            missing_vars.append(var)
    
    return missing_vars

def check_api_keys_detailed():
    """Detailed API keys check"""
    print_section("API Keys Configuration")
    
    api_keys = os.getenv('VALID_API_KEYS')
    if not api_keys:
        print("❌ VALID_API_KEYS not set")
        return
    
    try:
        # Try JSON parsing
        keys_list = json.loads(api_keys)
        print(f"✅ Found {len(keys_list)} API keys (JSON format)")
        for i, key in enumerate(keys_list):
            masked = key[:8] + '...' + key[-4:] if len(key) > 12 else '***'
            print(f"   Key {i+1}: {masked}")
    except json.JSONDecodeError:
        try:
            # Try comma-separated
            keys_list = [k.strip() for k in api_keys.split(',')]
            print(f"✅ Found {len(keys_list)} API keys (comma-separated)")
            for i, key in enumerate(keys_list):
                masked = key[:8] + '...' + key[-4:] if len(key) > 12 else '***'
                print(f"   Key {i+1}: {masked}")
        except Exception as e:
            print(f"❌ Error parsing API keys: {e}")

def check_database_connection():
    """Test database connection"""
    print_section("Database Connection Test")
    
    try:
        # Add current directory to path
        sys.path.insert(0, os.getcwd())
        
        from app.db.session import SessionLocal
        from app.models.admin import Admin
        
        print("✅ Successfully imported database modules")
        
        db = SessionLocal()
        try:
            # Test basic connection
            result = db.execute("SELECT 1").fetchone()
            print("✅ Database connection successful")
            
            # Check admin users
            admin_count = db.query(Admin).count()
            print(f"✅ Found {admin_count} admin users")
            
            if admin_count > 0:
                admins = db.query(Admin).all()
                for admin in admins:
                    masked_email = admin.email[:3] + '***' + admin.email[-10:] if len(admin.email) > 13 else '***'
                    print(f"   Admin: {masked_email} (Active: {admin.is_active}, Super: {admin.is_superadmin})")
            else:
                print("⚠️  No admin users found - this could cause 401 errors")
                
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
    """Test HMAC configuration"""
    print_section("HMAC Configuration Test")
    
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        print("❌ SECRET_KEY not set")
        return
    
    print(f"✅ SECRET_KEY is set (length: {len(secret_key)})")
    
    try:
        sys.path.insert(0, os.getcwd())
        from app.core.security import generate_app_signature
        import time
        
        # Test HMAC generation
        test_payload = "test-payload"
        timestamp = str(int(time.time()))
        signature = generate_app_signature(test_payload, timestamp, secret_key)
        
        print("✅ HMAC generation successful")
        print(f"   Test payload: {test_payload}")
        print(f"   Generated signature: {signature[:16]}...")
        print(f"   Timestamp: {timestamp}")
        
    except Exception as e:
        print(f"❌ HMAC generation failed: {e}")

def check_application_status():
    """Check if application is running"""
    print_section("Application Status")
    
    try:
        # Check if any Python processes are running
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        python_processes = [line for line in result.stdout.split('\n') if 'python' in line.lower() and 'app' in line.lower()]
        
        if python_processes:
            print("✅ Found Python application processes:")
            for process in python_processes[:3]:  # Show first 3
                print(f"   {process}")
        else:
            print("⚠️  No Python application processes found")
            
    except Exception as e:
        print(f"❌ Error checking processes: {e}")

def check_network_ports():
    """Check network ports"""
    print_section("Network Ports")
    
    ports_to_check = [8000, 5432, 6379]  # App, Postgres, Redis
    
    for port in ports_to_check:
        try:
            result = subprocess.run(['lsof', '-i', f':{port}'], capture_output=True, text=True)
            if result.stdout:
                print(f"✅ Port {port} is in use")
                lines = result.stdout.split('\n')[:2]  # Show first 2 lines
                for line in lines:
                    if line.strip():
                        print(f"   {line}")
            else:
                print(f"❌ Port {port} is not in use")
        except Exception as e:
            print(f"❌ Error checking port {port}: {e}")

def check_logs():
    """Check recent application logs"""
    print_section("Recent Application Logs")
    
    log_files = [
        'logs/server.log',
        'logs/dashboard.log',
        'logs/reminders-api.log'
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            try:
                # Get last 5 lines
                result = subprocess.run(['tail', '-5', log_file], capture_output=True, text=True)
                if result.stdout:
                    print(f"📄 {log_file} (last 5 lines):")
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            print(f"   {line}")
                else:
                    print(f"📄 {log_file}: Empty")
            except Exception as e:
                print(f"❌ Error reading {log_file}: {e}")
        else:
            print(f"❌ {log_file}: Not found")

def generate_recommendations(missing_vars):
    """Generate recommendations based on findings"""
    print_section("Recommendations")
    
    if missing_vars:
        print("🔧 Missing Environment Variables:")
        for var in missing_vars:
            if var == 'SECRET_KEY':
                print("   export SECRET_KEY='your-secret-key-here'")
            elif var == 'VALID_API_KEYS':
                print("   export VALID_API_KEYS='[\"key1\",\"key2\"]'")
            elif var.startswith('POSTGRES_'):
                print(f"   export {var}='your-value-here'")
            elif var == 'DATABASE_URL':
                print("   export DATABASE_URL='postgresql://user:pass@host:port/db'")
            elif var == 'ENVIRONMENT':
                print("   export ENVIRONMENT='production'")
    
    print("\n🚀 Next Steps:")
    print("1. Set the missing environment variables")
    print("2. Restart your application")
    print("3. Check application logs for errors")
    print("4. Verify the dashboard can authenticate")

def main():
    """Main diagnostic function"""
    print("🚀 AWS Instance Diagnostic Tool")
    print("=" * 60)
    
    # Run all checks
    check_system_info()
    missing_vars = check_environment_variables()
    check_api_keys_detailed()
    check_database_connection()
    check_hmac_configuration()
    check_application_status()
    check_network_ports()
    check_logs()
    generate_recommendations(missing_vars)
    
    print(f"\n{'='*60}")
    print("🏁 Diagnostic Complete")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
