# ZivoHealth Backend Configuration Setup

This document explains how to properly configure the ZivoHealth backend application with all required environment variables.

## Quick Setup

1. **Copy the example configuration file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file with your actual values:**
   ```bash
   nano .env
   ```

3. **Password reset React app requires no configuration** (uses relative URLs)

## Required Configuration

### Email Configuration (Required for Password Reset)

The following email settings are **mandatory** and the application will fail to start if any are missing:

```env
SMTP_SERVER=smtp.zoho.in
SMTP_PORT=587
SMTP_USERNAME=your_email@domain.com
SMTP_PASSWORD=your_app_password_here
FROM_EMAIL=your_email@domain.com
FRONTEND_URL=http://192.168.0.106:8000
PASSWORD_RESET_TOKEN_EXPIRY_MINUTES=30
```

**Important Notes:**
- `SMTP_PASSWORD` should be an app-specific password, not your regular email password
- `FROM_EMAIL` must match the authenticated email account
- `FRONTEND_URL` should point to your backend server for local development

### Password Reset App Configuration

**No configuration needed!** The React app uses relative URLs (`/api/v1`) and automatically works with any backend URL.

## Configuration Validation

The application now includes strict configuration validation:

### Backend Validation
- All email configuration variables are validated at startup
- Password reset app directory existence is checked
- Missing configurations will cause the application to fail with clear error messages

### React App Validation
- No environment configuration needed - uses relative URLs
- Automatically works with any backend URL

## Environment-Specific Setup

### Local Development
```env
# Backend .env
FRONTEND_URL=http://192.168.0.106:8000
ENVIRONMENT=development
```

### Production
```env
# Backend .env
FRONTEND_URL=https://zivohealth.ai
ENVIRONMENT=production
```

## Building the Password Reset App

No configuration needed - just build:

```bash
cd password-reset-app
npm run build
```

The built files will be automatically served by the backend at `/reset-password`.

## Troubleshooting

### Common Issues

1. **"Missing required email configuration" error:**
   - Ensure all email variables are set in `.env`
   - Check that no variables are empty or commented out

2. **"Password reset app directory not found" error:**
   - Run `npm run build` in the `password-reset-app` directory
   - Ensure the build completed successfully

3. **React app API errors:**
   - Ensure the React app is built: `cd password-reset-app && npm run build`
   - Check that the backend is running and serving the React app at `/reset-password`

### Validation Messages

The application will show clear validation messages:
- ✅ **Success:** "Configuration validation passed"
- ❌ **Error:** Specific missing configuration details

## Security Notes

- Never commit `.env` files to version control
- Use app-specific passwords for email services
- Regularly rotate API keys and passwords
- Use different configurations for development and production environments
