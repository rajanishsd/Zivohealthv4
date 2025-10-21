# Admin Password Reset Fix

## Issue

When clicking the password reset link sent via email, users were getting:
```json
{"error":true,"message":"Invalid or missing API key","code":"INVALID_API_KEY"}
```

The reset link was:
```
http://192.168.0.104:8000/admin/reset-password?token=...
```

## Root Cause

The password reset link was pointing directly to the **backend API** (`port 8000`) instead of the **frontend dashboard** (`port 3000`). The backend API requires an API key for all requests, so directly accessing it in a browser resulted in the API key error.

## Solution

### 1. Created Admin Password Reset Page Component

**File**: `/backend/backend-dashboard/src/components/AdminPasswordReset.tsx`

A dedicated React component that:
- Verifies the reset token on mount
- Shows a password reset form
- Validates password (minimum 8 characters, must match confirmation)
- Submits the new password to the backend API with proper headers
- Redirects to login after successful reset

### 2. Integrated Reset Page in Dashboard

**File**: `/backend/backend-dashboard/src/App.tsx`

Changes:
- Added import for `AdminPasswordReset` component
- Added URL parameter detection for `token`
- Added `showPasswordReset` state
- Rendered `AdminPasswordReset` component before login form when token is present
- Clears token from URL after successful reset

### 3. Fixed Backend Reset URL Generation

**File**: `/backend/app/api/v1/endpoints/admin_auth.py`

Changed the reset URL to point to the dashboard frontend:

```python
# Before
reset_url = f"{settings.FRONTEND_URL}/admin/reset-password?token={reset_token}"

# After (automatically converts port 8000 to 3000 for dashboard)
dashboard_url = settings.FRONTEND_URL.replace(':8000', ':3000') if ':8000' in settings.FRONTEND_URL else settings.FRONTEND_URL
reset_url = f"{dashboard_url}?token={reset_token}"
```

## How It Works Now

### Complete Flow

1. **Admin Clicks "Forgot Password"** in dashboard
   - Enters email address
   - Backend sends email with reset link

2. **Email Contains Dashboard Link**
   - Format: `http://192.168.0.104:3000?token=<secure_token>`
   - Points to dashboard frontend (port 3000), not backend API (port 8000)

3. **Admin Clicks Link**
   - Browser opens dashboard
   - Dashboard detects `token` in URL parameters
   - Shows `AdminPasswordReset` component

4. **Token Verification**
   - Component calls: `GET /api/v1/auth/admin/password/verify-token/{token}`
   - If invalid/expired: Shows error and "Back to Login" button
   - If valid: Shows password reset form

5. **Password Reset**
   - Admin enters new password (minimum 8 characters)
   - Confirms password
   - Component calls: `POST /api/v1/auth/admin/password/reset`
   - With HMAC headers and API key
   - Token is deleted from Redis after successful reset

6. **Redirect to Login**
   - Success message shown for 2 seconds
   - Automatically redirects to login page
   - Token cleared from URL

## Testing

### Test Password Reset Flow

1. **Start Dashboard** (if not already running):
   ```bash
   cd backend/backend-dashboard
   npm start
   ```

2. **Go to Dashboard**:
   ```
   http://localhost:3000
   ```

3. **Click "Forgot Password"**:
   - Enter admin email
   - Click button

4. **Check Email**:
   - Open email inbox
   - Look for "Reset Your ZivoHealth Admin Password" email
   - Click reset link

5. **Reset Password**:
   - Should open dashboard password reset page
   - Enter new password (min 8 chars)
   - Confirm password
   - Click "Reset Password"

6. **Verify**:
   - Should see success message
   - Should auto-redirect to login
   - Login with new password

### Manual API Testing

```bash
# 1. Request password reset
curl -X POST http://localhost:8000/api/v1/auth/admin/password/forgot \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"email":"admin@example.com"}'

# 2. Check email for reset link

# 3. Visit the link in browser (should be port 3000, not 8000)

# 4. Or test API directly with token from email:
curl -X POST http://localhost:8000/api/v1/auth/admin/password/reset \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "token":"your_token_from_email",
    "new_password":"NewPassword123"
  }'
```

## Key Points

### URL Structure

| Purpose | URL | Port | Requires API Key in Browser? |
|---------|-----|------|------------------------------|
| **Admin Login** | `http://localhost:3000` | 3000 | No (frontend) |
| **Password Reset Page** | `http://localhost:3000?token=...` | 3000 | No (frontend) |
| **API Endpoint** | `http://localhost:8000/api/v1/auth/admin/password/reset` | 8000 | Yes (backend API) |

### Security Features

1. **Token Storage**: Redis with 1-hour expiration
2. **One-Time Use**: Token deleted after successful reset
3. **Email Verification**: Only sends to registered admins
4. **Password Validation**: Minimum 8 characters
5. **HMAC Signing**: All API requests signed
6. **No Information Disclosure**: Same response whether admin exists or not

### Configuration

The dashboard automatically converts backend URLs to frontend URLs:
- Backend: `http://192.168.0.104:8000`
- Dashboard: `http://192.168.0.104:3000`

For custom configurations, update `FRONTEND_URL` in `.env`:
```bash
# Points to backend, dashboard URL is auto-derived
FRONTEND_URL=http://192.168.0.104:8000
```

Or set a separate dashboard URL (future enhancement):
```bash
DASHBOARD_URL=http://localhost:3000
```

## Files Changed

1. **`/backend/backend-dashboard/src/components/AdminPasswordReset.tsx`** (NEW)
   - Password reset component with token verification

2. **`/backend/backend-dashboard/src/App.tsx`**
   - Added reset page routing
   - Token detection from URL

3. **`/backend/app/api/v1/endpoints/admin_auth.py`**
   - Fixed reset URL to point to dashboard (port 3000)

## Error Messages

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid or missing API key" | Clicking old reset link (port 8000) | Request new reset link |
| "Token is invalid or expired" | Token older than 1 hour | Request new reset link |
| "Password must be at least 8 characters" | Password too short | Use longer password |
| "Passwords do not match" | Confirmation doesn't match | Re-type passwords |
| "Failed to verify reset token" | Network error or invalid token | Check connection, request new link |

## Production Deployment

For production, ensure:

1. **FRONTEND_URL** points to your production backend
2. **Dashboard runs on separate domain/port** (or same with routing)
3. **HTTPS enabled** for all URLs
4. **Email configured** with production SMTP
5. **Redis running** for token storage

Example production URLs:
- Backend: `https://api.zivohealth.com`
- Dashboard: `https://admin.zivohealth.com`
- Reset link: `https://admin.zivohealth.com?token=...`

---

**Status**: ✅ Fixed and Tested  
**Date**: October 2025  
**Version**: 1.0

