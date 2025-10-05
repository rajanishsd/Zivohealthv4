#!/bin/bash

# AWS Environment Verification Script
# Run this on the AWS instance to check configuration

echo "🚀 AWS Environment Verification"
echo "=================================="
echo "Timestamp: $(date)"
echo "Hostname: $(hostname)"
echo "User: $(whoami)"
echo "Working Directory: $(pwd)"
echo ""

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    echo "❌ Not in the backend directory. Please run from /path/to/backend/"
    exit 1
fi

echo "📋 Environment Variables Check"
echo "=============================="

# Check critical environment variables
check_var() {
    local var_name=$1
    local var_value=$(printenv "$var_name")
    if [ -n "$var_value" ]; then
        # Mask sensitive values
        if [[ "$var_name" == *"SECRET"* ]] || [[ "$var_name" == *"KEY"* ]] || [[ "$var_name" == *"URL"* ]]; then
            local masked_value="${var_value:0:8}...${var_value: -4}"
            echo "✅ $var_name: $masked_value"
        else
            echo "✅ $var_name: $var_value"
        fi
    else
        echo "❌ $var_name: NOT SET"
    fi
}

check_var "APP_SECRET_KEY"
check_var "VALID_API_KEYS"
check_var "DATABASE_URL"
check_var "ENVIRONMENT"
check_var "DEBUG"

echo ""
echo "🐍 Python Environment Check"
echo "============================"

# Check Python version
echo "Python version: $(python3 --version)"

# Check if virtual environment is activated
if [ -n "$VIRTUAL_ENV" ]; then
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
else
    echo "⚠️  No virtual environment detected"
fi

# Check if required packages are installed
echo ""
echo "📦 Package Check"
echo "================"

python3 -c "
try:
    import fastapi
    print('✅ FastAPI installed')
except ImportError:
    print('❌ FastAPI not installed')

try:
    import sqlalchemy
    print('✅ SQLAlchemy installed')
except ImportError:
    print('❌ SQLAlchemy not installed')

try:
    import alembic
    print('✅ Alembic installed')
except ImportError:
    print('❌ Alembic not installed')
"

echo ""
echo "🗄️ Database Check"
echo "=================="

# Check database connection
python3 -c "
try:
    from app.db.session import SessionLocal
    from app.models.admin import Admin
    
    db = SessionLocal()
    try:
        admin_count = db.query(Admin).count()
        print(f'✅ Database connection successful')
        print(f'✅ Found {admin_count} admin users')
        
        if admin_count == 0:
            print('⚠️  No admin users found - you may need to create one')
        else:
            admins = db.query(Admin).all()
            for admin in admins:
                masked_email = admin.email[:3] + '***' + admin.email[-10:] if len(admin.email) > 13 else '***'
                print(f'   Admin: {masked_email} (Active: {admin.is_active})')
    except Exception as e:
        print(f'❌ Database error: {e}')
    finally:
        db.close()
except ImportError as e:
    print(f'❌ Import error: {e}')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"

echo ""
echo "🔐 HMAC Configuration Check"
echo "============================"

python3 -c "
try:
    from app.utils.hmac import hmac_generator
    test_payload = 'test'
    headers = hmac_generator.generateHeaders(test_payload)
    print('✅ HMAC generation working')
    print(f'   Test signature: {headers.get(\"X-Signature\", \"N/A\")[:16]}...')
except Exception as e:
    print(f'❌ HMAC configuration error: {e}')
"

echo ""
echo "🌐 Network Check"
echo "================"

# Check if the application can bind to the expected port
echo "Checking if port 8000 is available..."
if lsof -i :8000 > /dev/null 2>&1; then
    echo "⚠️  Port 8000 is already in use"
    lsof -i :8000
else
    echo "✅ Port 8000 is available"
fi

echo ""
echo "📋 Summary and Recommendations"
echo "==============================="

# Check if all critical variables are set
missing_vars=()
for var in "APP_SECRET_KEY" "VALID_API_KEYS" "DATABASE_URL"; do
    if [ -z "$(printenv "$var")" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -eq 0 ]; then
    echo "✅ All critical environment variables are set"
else
    echo "❌ Missing environment variables: ${missing_vars[*]}"
    echo "💡 Set these variables in your AWS environment"
fi

echo ""
echo "🔧 Next Steps:"
echo "1. If any variables are missing, set them in your AWS environment"
echo "2. If no admin users exist, run: python3 scripts/create_admin_user.py"
echo "3. If database connection fails, check DATABASE_URL"
echo "4. Restart the application after fixing any issues"
echo "5. Check application logs for detailed error messages"

echo ""
echo "📝 To run detailed verification:"
echo "   python3 scripts/verify_aws_keys.py"
echo ""
echo "👤 To create admin user:"
echo "   python3 scripts/create_admin_user.py"
