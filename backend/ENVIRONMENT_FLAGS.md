# Environment Flags Configuration

The ZivoHealth platform now supports environment-based configuration using the `ENVIRONMENT` flag. This allows you to easily switch between development, staging, and production configurations.

## Environment Types

### 1. Development (`ENVIRONMENT=development`)
- **Purpose**: Local development and testing
- **CORS Origins**: Localhost and local IP addresses
- **HTTPS**: Not required
- **SMTP**: Can use development servers
- **Validation**: Relaxed validation rules

### 2. Staging (`ENVIRONMENT=staging`)
- **Purpose**: Pre-production testing
- **CORS Origins**: Both development and production origins
- **HTTPS**: Recommended but not enforced
- **SMTP**: Production-like configuration
- **Validation**: Moderate validation rules

### 3. Production (`ENVIRONMENT=production`)
- **Purpose**: Live production environment
- **CORS Origins**: Only production domains
- **HTTPS**: Required for all URLs
- **SMTP**: Production servers only
- **Validation**: Strict validation rules

## Quick Setup

### Option 1: Use Pre-configured Files
```bash
# For development
cp .env.development .env

# For production
cp .env.production .env
```

### Option 2: Manual Configuration
```bash
# Copy the example file
cp .env.example .env

# Edit and set your environment
nano .env
# Set: ENVIRONMENT=development
```

## Environment-Specific Features

### Automatic CORS Configuration
The system automatically sets CORS origins based on environment:

**Development:**
```python
[
    "http://localhost:3000",
    "http://127.0.0.1:3000", 
    "http://192.168.0.106:3000",
    "http://192.168.0.106:8000"
]
```

**Production:**
```python
[
    "https://zivohealth.ai",
    "https://www.zivohealth.ai",
    "https://app.zivohealth.ai"
]
```

**Staging:**
```python
# Combines both development and production origins
```

### Environment Validation

The system automatically validates configuration based on environment:

**Production Validations:**
- `FRONTEND_URL` must use HTTPS
- Cannot use development SMTP servers
- Strict security requirements

**Development Validations:**
- Warns if using HTTPS without localhost
- Allows development SMTP servers
- Relaxed security requirements

### Environment Properties

You can use these properties in your code:

```python
from app.core.config import settings

# Environment checks
if settings.is_development:
    print("Running in development mode")
elif settings.is_production:
    print("Running in production mode")

# Feature flags
if settings.debug_mode:
    print("Debug mode enabled")

if settings.require_https:
    print("HTTPS required")
```

## Configuration Examples

### Development Environment
```env
ENVIRONMENT=development
FRONTEND_URL=http://192.168.0.106:8000
SMTP_SERVER=smtp.zoho.in
SMTP_PORT=587
```

### Production Environment
```env
ENVIRONMENT=production
FRONTEND_URL=https://zivohealth.ai
SMTP_SERVER=smtp.zoho.in
SMTP_PORT=587
```

## React App Configuration

The password reset React app uses **relative URLs** and requires **no environment configuration**:

### How It Works
```javascript
// React app uses relative URLs
const API_BASE_URL = '/api/v1';
```

### Benefits
- **No Environment Files**: React app needs no .env files
- **Automatic Adaptation**: Works with any backend URL automatically
- **Simplified Deployment**: No need to manage React app environment variables
- **Single Source of Truth**: Only backend .env file needed

## Starting Services with Environment Configuration

Use the existing `start-all.sh` script with environment parameters:

### Development Environment
```bash
./scripts/dev/start-all.sh dev
```
This will:
- Set up development environment configuration
- Start all services (PostgreSQL, Redis, Backend, Dashboard)
- Build password reset app locally

### Production Environment (AWS)
```bash
./scripts/dev/deploy-to-production.sh
```
This will:
- Set up production environment configuration
- Build Docker image (React app builds inside Docker)
- Push to ECR and deploy to EC2

### Start All Services (Default)
```bash
./scripts/dev/start-all.sh
```
Uses existing `.env` configuration

### Start Individual Services
```bash
# Start specific service with development environment
./scripts/dev/start-all.sh dev backend

# Start specific service with production environment
./scripts/dev/start-all.sh prod backend
```

### Manual Environment Setup
```bash
# For development
cp .env.development .env
./scripts/dev/start-all.sh

# For production
cp .env.production .env
./scripts/dev/start-all.sh
```

## Validation Messages

The system provides clear feedback about environment configuration:

```
🛠️ Development environment detected - applying development validations
🔒 Production environment detected - applying strict validations
🧪 Staging environment detected
✅ Configuration validation passed for development environment
```

## Benefits

1. **Easy Environment Switching**: Change one flag to switch entire configuration
2. **Automatic Validation**: Environment-specific rules prevent misconfigurations
3. **Security**: Production automatically enforces security requirements
4. **CORS Management**: Automatic CORS configuration based on environment
5. **Clear Feedback**: Detailed logging about environment-specific behavior

## Troubleshooting

### Common Issues

1. **"Production requires HTTPS" error:**
   - Set `FRONTEND_URL=https://your-domain.com` for production
   - Or change `ENVIRONMENT=development` for local testing

2. **CORS errors:**
   - Check that your frontend URL is in the allowed origins for your environment
   - Development allows localhost, production only allows production domains

3. **SMTP validation errors:**
   - Production doesn't allow development SMTP servers
   - Use production SMTP configuration for production environment

### Environment Detection

The system logs the detected environment at startup:
```
Validating application configuration for development environment...
CORS configured for development environment with origins: [...]
```
