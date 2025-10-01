# Password Reset Setup Guide

This guide explains how to set up the password reset functionality for ZivoHealth. The system supports password reset for both **users** (patients) and **doctors**.

## Environment Variables Required

Add these environment variables to your `.env` file:

```bash
# Email Configuration (for password reset)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@zivohealth.ai
FRONTEND_URL=https://zivohealth.ai

# Password Reset Configuration
PASSWORD_RESET_TOKEN_EXPIRY_MINUTES=30
```

## Email Service Setup

### Option 1: Gmail SMTP
1. Enable 2-factor authentication on your Gmail account
2. Generate an App Password:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate a password for "Mail"
3. Use the app password in `SMTP_PASSWORD`

### Option 2: AWS SES
1. Set up AWS SES in your AWS account
2. Verify your sending domain
3. Update SMTP settings:
   ```bash
   SMTP_SERVER=email-smtp.us-east-1.amazonaws.com
   SMTP_PORT=587
   SMTP_USERNAME=your-ses-smtp-username
   SMTP_PASSWORD=your-ses-smtp-password
   ```

### Option 3: SendGrid
1. Create a SendGrid account
2. Get your SMTP credentials
3. Update SMTP settings:
   ```bash
   SMTP_SERVER=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USERNAME=apikey
   SMTP_PASSWORD=your-sendgrid-api-key
   ```

## Database Migration

Run the database migrations to create and update the password reset tokens table:

```bash
cd backend
alembic upgrade head
```

This will run both migrations:
- `025_add_password_reset_tokens.py` - Creates the initial password reset tokens table
- `026_update_password_reset_for_doctors.py` - Updates the table to support both users and doctors

## Frontend Deployment

### Build the Password Reset App
```bash
cd backend/password-reset-app
npm install
npm run build
```

### Deploy to Static Site
Copy the build files to your static site directory:

```bash
# Copy build files to www directory
cp -r backend/password-reset-app/build/* /opt/zivohealth/www/reset-password/
```

### Update Caddyfile (if needed)
Ensure your Caddyfile handles the reset-password route:

```caddy
zivohealth.ai, www.zivohealth.ai {
  encode zstd gzip
  root * /srv/www
  file_server
  
  # Handle SPA routing for reset-password
  handle_path /reset-password* {
    try_files {path} /reset-password/index.html
    file_server
  }
}
```

## Testing the Flow

1. **Request Password Reset**:
   - Use the mobile app or API: `POST /api/v1/auth/forgot-password`
   - Works for both user and doctor emails
   - Check email for reset link

2. **Reset Password**:
   - Click the link in email
   - Enter new password on the web page
   - Verify password was changed (works for both users and doctors)

3. **API Endpoints**:
   - `POST /api/v1/auth/forgot-password` - Request reset (supports both users and doctors)
   - `POST /api/v1/auth/reset-password` - Reset with token (works for both user types)
   - `GET /api/v1/auth/verify-reset-token/{token}` - Verify token

## Security Features

- ✅ Tokens expire in 30 minutes (configurable)
- ✅ Tokens are one-time use only
- ✅ Tokens are hashed before storage
- ✅ Rate limiting on reset requests
- ✅ No user enumeration (always returns success message)
- ✅ Secure token generation using `secrets.token_urlsafe()`
- ✅ Supports both users and doctors with proper type validation
- ✅ Database constraints ensure either user_id or doctor_id is set, but not both

## Troubleshooting

### Email Not Sending
1. Check SMTP credentials
2. Verify email service is working
3. Check server logs for errors
4. Ensure firewall allows SMTP traffic

### Token Issues
1. Check token expiration time
2. Verify database migration ran successfully
3. Check if token was already used

### Frontend Issues
1. Verify build files are in correct location
2. Check Caddyfile routing
3. Ensure HTTPS is working
4. Check browser console for errors
