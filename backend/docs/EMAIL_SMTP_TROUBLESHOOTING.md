# Email SMTP Troubleshooting Guide

This guide helps troubleshoot common email sending issues in the ZivoHealth platform.

## Common Issues

### 1. 553 Error: "Sender is not allowed to relay emails"

**Symptom:**
```
Failed to send email: (553, b'Sender is not allowed to relay emails')
```

**Cause:**
- For Zoho SMTP, the `FROM_EMAIL` must match the `SMTP_USERNAME` you're authenticating with
- Zoho doesn't allow sending emails with a different "From" address than the authenticated account

**Solution:**

#### Option 1: Match FROM_EMAIL to SMTP_USERNAME (Recommended)
In your `.env` file:
```env
SMTP_SERVER=smtp.zoho.in
SMTP_PORT=587
SMTP_USERNAME=your-email@yourdomain.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=your-email@yourdomain.com  # Must match SMTP_USERNAME for Zoho
```

#### Option 2: Set up Domain Authentication (Advanced)
1. Log in to Zoho Mail admin console
2. Go to Email Configuration → Domain Authentication
3. Set up SPF, DKIM, and DMARC records for your domain
4. Add authorized sender addresses
5. This allows sending from different email addresses under your domain

**Automatic Fix:**
The system now automatically detects Zoho SMTP and replaces the From header with SMTP_USERNAME if they don't match, but it's better to fix the configuration.

---

### 2. API Returns Success But Email Fails

**Previous Behavior:**
The API would return `200 OK` even if the email failed to send, misleading the client.

**Fixed:**
- The system now checks the email sending result
- If email fails, the API returns a `400 Bad Request` with error message
- The OTP is removed from Redis if email sending fails
- Login events are logged with `error_code="email_send_failed"`

---

## Configuration Best Practices

### For Zoho SMTP

```env
# Zoho Configuration
SMTP_SERVER=smtp.zoho.in
SMTP_PORT=587  # or 465 for SSL
SMTP_USERNAME=noreply@zivohealth.ai
SMTP_PASSWORD=your_zoho_app_password
FROM_EMAIL=noreply@zivohealth.ai  # Must match SMTP_USERNAME
FRONTEND_URL=https://zivohealth.ai
ENVIRONMENT=production
```

**Getting Zoho App Password:**
1. Log in to Zoho Mail
2. Go to Settings → Security → App Passwords
3. Generate a new app password
4. Use this password in `SMTP_PASSWORD` (not your regular password)

### For Gmail SMTP

```env
# Gmail Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
FROM_EMAIL=noreply@yourdomain.com  # Can be different for Gmail
FRONTEND_URL=https://zivohealth.ai
ENVIRONMENT=production
```

**Getting Gmail App Password:**
1. Enable 2-factor authentication on your Gmail account
2. Go to Google Account → Security → 2-Step Verification → App passwords
3. Generate a password for "Mail"
4. Use this password in `SMTP_PASSWORD`

### For AWS SES

```env
# AWS SES Configuration
SMTP_SERVER=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USERNAME=your_ses_smtp_username
SMTP_PASSWORD=your_ses_smtp_password
FROM_EMAIL=verified-email@yourdomain.com  # Must be verified in SES
FRONTEND_URL=https://zivohealth.ai
ENVIRONMENT=production
```

---

## Debugging Email Issues

### Enable SMTP Debug Mode

The system now enables SMTP debug output by default with `server.set_debuglevel(1)`.

Check your Docker logs:
```bash
docker logs zivohealth-api 2>&1 | grep -A 20 "Attempting to send email"
```

### Check Configuration

Look for these lines in the logs:
```
Attempting to send email via smtp.zoho.in:587
SMTP Username: your-email@yourdomain.com
From Email: noreply@zivohealth.ai
```

If you see the warning:
```
⚠️  WARNING: For Zoho SMTP, FROM_EMAIL (noreply@zivohealth.ai) should match SMTP_USERNAME (your-email@yourdomain.com)
⚠️  This mismatch will cause '553 Sender is not allowed to relay emails' error
✅ Automatically updated From header to: your-email@yourdomain.com
```

This means your configuration needs to be updated.

### Test Email Sending

You can test email sending with a simple Python script:

```python
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Your configuration
smtp_server = "smtp.zoho.in"
smtp_port = 587
smtp_username = "your-email@yourdomain.com"  # Same as FROM
smtp_password = "your_app_password"
from_email = "your-email@yourdomain.com"  # Must match smtp_username for Zoho
to_email = "test@example.com"

msg = MIMEMultipart()
msg["Subject"] = "Test Email"
msg["From"] = from_email
msg["To"] = to_email
msg.attach(MIMEText("This is a test email", "plain"))

context = ssl.create_default_context()
with smtplib.SMTP(smtp_server, smtp_port) as server:
    server.set_debuglevel(1)
    server.starttls(context=context)
    server.login(smtp_username, smtp_password)
    server.send_message(msg)
    
print("Email sent successfully!")
```

---

## Deployment Checklist

When deploying to production:

- [ ] `SMTP_SERVER` is set correctly
- [ ] `SMTP_PORT` is set (587 for TLS, 465 for SSL)
- [ ] `SMTP_USERNAME` is set to your email account
- [ ] `SMTP_PASSWORD` is set to app-specific password (not regular password)
- [ ] `FROM_EMAIL` matches `SMTP_USERNAME` (for Zoho)
- [ ] `FROM_EMAIL` is verified (for AWS SES)
- [ ] `FRONTEND_URL` points to your production domain
- [ ] `ENVIRONMENT=production` is set
- [ ] Test email sending after deployment

---

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `SMTP_SERVER` | Yes | SMTP server address | `smtp.zoho.in` |
| `SMTP_PORT` | Yes | SMTP port (587=TLS, 465=SSL) | `587` |
| `SMTP_USERNAME` | Yes | SMTP authentication username | `noreply@zivohealth.ai` |
| `SMTP_PASSWORD` | Yes | SMTP app-specific password | `your_app_password` |
| `FROM_EMAIL` | Yes | Email sender address | `noreply@zivohealth.ai` |
| `FRONTEND_URL` | Yes | Base URL for email links | `https://zivohealth.ai` |
| `ENVIRONMENT` | No | Environment mode | `production` or `development` |

---

## Still Having Issues?

1. Check that your SMTP credentials are correct
2. Verify that your email account is active and not locked
3. Check firewall rules allow outbound connections to SMTP port
4. For Zoho: Verify your domain is properly configured in Zoho admin
5. For AWS SES: Verify your email/domain in SES console
6. Check Docker network allows external SMTP connections
7. Review application logs for detailed error messages

---

## Changes Made (October 2025)

### Fixed in `auth_service.py`:
- Now checks the return value of `send_otp_email()`
- Raises `ValueError` with clear message if email fails
- Cleans up OTP from Redis if email sending fails
- Logs failed attempts with `error_code="email_send_failed"`

### Fixed in `email_service.py`:
- Added detailed logging showing SMTP config being used
- Auto-detects Zoho SMTP and adjusts From header if needed
- Separate exception handling for SMTP errors vs general errors
- Better error messages for 553 relay errors
- Enabled SMTP debug output for troubleshooting

