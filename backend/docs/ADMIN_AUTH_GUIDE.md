# Admin Authentication Guide

## Overview

Admin authentication for the ZivoHealth dashboard supports **3 methods**:
1. **Password Login** - Traditional email/password authentication
2. **OTP Login** - One-Time Password sent via email
3. **Forgot Password** - Password reset via email link

All methods are **admin-specific** and separate from user/patient authentication.

---

## 🔐 Authentication Methods

### 1. Password Login

**Endpoint**: `POST /api/v1/auth/admin/login`

**Request**:
```json
{
  "email": "admin@example.com",
  "password": "SecurePassword123"
}
```

**Response**:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "admin": {
    "id": 1,
    "email": "admin@example.com",
    "full_name": "John Doe",
    "is_superadmin": true
  }
}
```

---

### 2. OTP Login

#### Step 1: Request OTP

**Endpoint**: `POST /api/v1/auth/admin/otp/request`

**Request**:
```json
{
  "email": "admin@example.com"
}
```

**Response**:
```json
{
  "message": "OTP has been sent to your email address.",
  "expires_in": 600
}
```

**Email Sent**:
- Subject: "Your ZivoHealth Admin Login Code"
- Contains: 6-digit numeric OTP
- Expires: 10 minutes
- Template: Admin-branded with security warnings

#### Step 2: Verify OTP

**Endpoint**: `POST /api/v1/auth/admin/otp/verify`

**Request**:
```json
{
  "email": "admin@example.com",
  "code": "123456"
}
```

**Response**: Same as password login

**Security Features**:
- OTP stored in Redis with 10-minute TTL
- OTP deleted after successful verification
- Rate limiting to prevent brute force
- IP address logging for audit trail

---

### 3. Forgot Password

#### Step 1: Request Password Reset

**Endpoint**: `POST /api/v1/auth/admin/password/forgot`

**Request**:
```json
{
  "email": "admin@example.com"
}
```

**Response** (always success for security):
```json
{
  "message": "If this email is registered as an admin, a password reset link has been sent."
}
```

**Email Sent**:
- Subject: "Reset Your ZivoHealth Admin Password"
- Contains: Secure reset link with token
- Expires: 1 hour
- Template: Admin-branded with security warnings

#### Step 2: Reset Password

**Endpoint**: `POST /api/v1/auth/admin/password/reset`

**Request**:
```json
{
  "token": "secure_token_here",
  "new_password": "NewSecurePassword123"
}
```

**Response**:
```json
{
  "message": "Password has been reset successfully. You can now login with your new password."
}
```

**Validations**:
- Token must be valid and not expired
- Password minimum 8 characters
- Token deleted after successful reset

#### Token Verification (Optional)

**Endpoint**: `GET /api/v1/auth/admin/password/verify-token/{token}`

**Response**:
```json
{
  "valid": true,
  "message": "Token is valid"
}
```

---

## 🖥️ Dashboard Integration

### Login Flow

The dashboard at `/backend-dashboard` provides a unified login interface:

1. **Default**: Password login form
2. **OTP Mode**: Triggered by "Login with OTP" button
3. **Forgot Password**: Triggered by "Forgot Password" button

### UI Features

- **Email Input**: Required for all methods
- **Password Input**: Only for password login
- **OTP Input**: Only for OTP verification
- **Mode Switching**: Easy toggle between password and OTP
- **Error Handling**: Displays detailed error messages
- **Success Messages**: Confirmation for OTP/reset requests

### State Management

```typescript
interface AuthState {
  isAuthenticated: boolean;
  token: string | null;
  user: any | null;
  isSuperAdmin: boolean;
}
```

**Storage**:
- `localStorage.dashboard_token` - JWT token
- `localStorage.dashboard_user` - User info
- `localStorage.dashboard_is_superadmin` - Super admin flag

---

## 🔒 Security Features

### OTP Security

1. **Storage**: Redis with TTL (10 minutes)
2. **One-Time Use**: Deleted after verification
3. **Rate Limiting**: Prevents brute force
4. **IP Logging**: Audit trail for all requests
5. **Email Branding**: Clear admin branding to prevent phishing

### Password Reset Security

1. **Token Storage**: Redis with TTL (1 hour)
2. **Secure Tokens**: 32-byte URL-safe tokens
3. **One-Time Use**: Deleted after successful reset
4. **Information Disclosure**: Never reveals if email exists
5. **IP Logging**: Audit trail for all requests

### General Security

1. **HMAC Signatures**: All requests signed with HMAC
2. **API Key**: Required for all endpoints
3. **JWT Tokens**: Short-lived (configurable expiration)
4. **Email Verification**: Only sends to registered admins
5. **Inactive Admins**: Blocked from authentication

---

## 📧 Email Templates

### OTP Email

**Subject**: Your ZivoHealth Admin Login Code  
**From**: ZivoHealth Security Team  
**Design**: Dark blue theme (#2c3e50)  
**Content**:
- Large, centered OTP code
- 10-minute expiration warning
- Security notices
- Admin dashboard branding

### Password Reset Email

**Subject**: Reset Your ZivoHealth Admin Password  
**From**: ZivoHealth Security Team  
**Design**: Dark blue theme (#2c3e50)  
**Content**:
- Reset button with link
- Plain text link fallback
- 1-hour expiration warning
- Security notices
- Admin dashboard branding

---

## 🧪 Testing

### Test OTP Login

```bash
# 1. Request OTP
curl -X POST http://localhost:8000/api/v1/auth/admin/otp/request \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{"email":"admin@example.com"}'

# 2. Check email for OTP

# 3. Verify OTP
curl -X POST http://localhost:8000/api/v1/auth/admin/otp/verify \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{"email":"admin@example.com","code":"123456"}'
```

### Test Forgot Password

```bash
# 1. Request reset
curl -X POST http://localhost:8000/api/v1/auth/admin/password/forgot \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{"email":"admin@example.com"}'

# 2. Check email for reset link

# 3. Reset password
curl -X POST http://localhost:8000/api/v1/auth/admin/password/reset \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{"token":"your_token","new_password":"NewPassword123"}'
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# SMTP Configuration (required for emails)
SMTP_SERVER=smtp.zoho.in
SMTP_PORT=587
SMTP_USERNAME=your_email@domain.com
SMTP_PASSWORD=your_password
FROM_EMAIL=your_email@domain.com  # Must match SMTP_USERNAME for Zoho

# Redis Configuration (required for OTP/tokens)
REDIS_HOST=localhost
REDIS_PORT=6379

# Frontend URL (for reset links)
FRONTEND_URL=http://localhost:3000

# JWT Configuration
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### SMTP Setup

For Zoho (recommended):
1. `FROM_EMAIL` must equal `SMTP_USERNAME`
2. Use App Password (not account password)
3. Enable SMTP in Zoho settings

See: [EMAIL_SMTP_TROUBLESHOOTING.md](EMAIL_SMTP_TROUBLESHOOTING.md)

---

## 🚨 Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Admin account is not active" | Admin is inactive | Contact super admin |
| "OTP has expired or is invalid" | OTP expired (>10min) | Request new OTP |
| "Invalid OTP code" | Wrong code entered | Check email, try again |
| "Invalid or expired reset token" | Token expired (>1h) | Request new reset link |
| "Failed to send OTP email" | SMTP misconfigured | Check SMTP settings |

### Error Response Format

```json
{
  "detail": "Error message here"
}
```

Or for validation errors:
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "email"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

---

## 📊 Monitoring

### Logs

All auth events are logged with:
- Timestamp
- Admin email
- IP address
- Action (OTP request, verify, password reset, etc.)
- Success/failure

**Example**:
```
🔐 Admin OTP requested for admin@example.com from IP 192.168.1.1
✅ Admin OTP verified for admin@example.com from IP 192.168.1.1
🔐 Admin password reset requested for admin@example.com from IP 192.168.1.1
```

### Redis Monitoring

Check active OTP/reset tokens:
```bash
redis-cli
> KEYS admin_otp:*
> KEYS admin_reset:*
> TTL admin_otp:admin@example.com
```

---

## 🔐 Admin Management Integration

After authentication, admins can:
- View dashboard (all admins)
- Manage users (all admins)
- **Manage other admins (super admin only)**
- Change passwords (super admin only)
- View admin management tab (super admin only)

See: [ADMIN_MANAGEMENT_GUIDE.md](ADMIN_MANAGEMENT_GUIDE.md)

---

## 🆕 What's New

### Admin-Specific Authentication

- ✅ Separate OTP flow for admins
- ✅ Separate password reset for admins
- ✅ Admin-branded email templates
- ✅ Enhanced security notices
- ✅ Redis-based token storage
- ✅ IP logging for audit trail
- ✅ Super admin detection on login

### Dashboard Updates

- ✅ OTP login for admins
- ✅ Forgot password for admins
- ✅ Better error handling (FastAPI validation errors)
- ✅ Success message display
- ✅ Super admin flag in auth state

---

## 🔄 Comparison: Admin vs User Auth

| Feature | User Auth | Admin Auth |
|---------|-----------|------------|
| OTP Endpoint | `/api/v1/auth/email/otp/*` | `/api/v1/auth/admin/otp/*` |
| Reset Endpoint | `/api/v1/auth/forgot-password` | `/api/v1/auth/admin/password/forgot` |
| JWT Claim | `is_admin: false` | `is_admin: true` |
| Email Template | User-branded (red) | Admin-branded (dark blue) |
| Dashboard Access | No | Yes |
| Can Manage Users | No | Yes |
| Can Manage Admins | No | Super admin only |

---

## 📝 Best Practices

1. **Use OTP for sensitive operations** - Extra security layer
2. **Rotate passwords regularly** - Use forgot password feature
3. **Monitor auth logs** - Check for suspicious activity
4. **Keep SMTP credentials secure** - Use environment variables
5. **Enable 2FA when available** - Additional security (future feature)
6. **Use strong passwords** - Minimum 8 characters, mix of types
7. **Don't share OTP codes** - They're one-time use only
8. **Check email carefully** - Verify sender before clicking links

---

## 🐛 Troubleshooting

### OTP Not Received

1. Check spam/junk folder
2. Verify admin email is correct
3. Check SMTP configuration
4. Check email service logs
5. Try requesting new OTP

### Reset Link Not Working

1. Check if link expired (1 hour)
2. Verify token in URL is complete
3. Try copying full link
4. Request new reset link if expired

### Login Still Fails After Reset

1. Clear browser cache
2. Try incognito/private mode
3. Verify new password meets requirements
4. Contact super admin if admin inactive

---

## 📞 Support

For authentication issues:
1. Check this guide first
2. Review logs for specific errors
3. Check [EMAIL_SMTP_TROUBLESHOOTING.md](EMAIL_SMTP_TROUBLESHOOTING.md)
4. Contact development team

---

**Last Updated**: October 2025  
**Version**: 1.0  
**Status**: ✅ Production Ready

