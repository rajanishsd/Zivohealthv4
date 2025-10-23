# Email Verification Implementation Guide

## Overview
Implemented a complete email verification flow for users who sign up with email/password. Users must verify their email address before they can log in and access the app.

## Implementation Summary

### Backend Changes

#### 1. **New API Endpoints** (`backend/app/api/v1/endpoints/dual_auth.py`)
- `POST /dual-auth/email/register` - Register new user and send verification email
- `POST /dual-auth/email/verify` - Verify email using token from email link
- `POST /dual-auth/email/resend-verification` - Resend verification email

#### 2. **Auth Service** (`backend/app/core/auth_service.py`)
Added methods:
- `register_with_email()` - Creates inactive user and sends verification email
- `verify_email()` - Activates user when they click verification link
- `resend_verification_email()` - Resends verification email
- `_generate_verification_token()` - Generates secure verification token
- `_hash_token()` - Hashes tokens for secure storage

#### 3. **Email Service** (`backend/app/services/email_service.py`)
Added:
- `send_verification_email()` - Sends beautifully formatted verification email
- HTML and text templates for verification emails

#### 4. **Schemas** (`backend/app/schemas/auth.py`)
New request/response models:
- `EmailRegisterRequest`
- `EmailRegisterResponse`
- `EmailVerifyRequest`
- `EmailVerifyResponse`

### iOS Changes

#### 1. **Network Service** (`apps/iOS/Zivohealth/Sources/Services/NetworkService.swift`)
Added methods:
- `register()` - Updated to use new verification flow
- `verifyEmail()` - Verify email with token
- `resendVerificationEmail()` - Resend verification email

Added response models:
- `EmailRegisterResponse`
- `EmailVerifyResponse`

#### 2. **Registration Views** (`apps/iOS/Zivohealth/Sources/Views/DualAuthViews.swift`)
Added:
- `emailVerificationWaiting` registration step
- Email verification waiting screen with:
  - Clear instructions
  - Email display
  - Resend verification email button
  - Back to sign in option
- `resendVerificationEmail()` method

#### 3. **Deep Link Handling** (`apps/iOS/Zivohealth/Sources/App/ZivoHealthApp.swift`)
Added:
- `.onOpenURL` handler in app body
- `handleDeepLink()` - Routes deep links
- `handleEmailVerification()` - Processes verification tokens
- Notification broadcasting for verification success/failure

## User Flow

### Registration Flow

1. **User Registration**
   - User enters name, email, and password
   - Accepts privacy policy and terms
   - Clicks "Create Account"

2. **Verification Email Sent**
   - Backend creates inactive user account
   - Generates secure verification token (24-hour expiry)
   - Sends verification email
   - User sees "Verify Your Email" screen

3. **Email Verification Waiting**
   - User sees their email address
   - Instructions to check inbox
   - Option to resend verification email
   - Back to sign in button

4. **Email Verification**
   - User clicks link in email
   - App opens via deep link
   - Token is verified on backend
   - User account is activated
   - Success message shown

5. **Login**
   - User navigates to sign in
   - Enters credentials
   - Successfully logs in (now that account is active)

### Sign-In Flow (Email/Password Users)

Users with unverified emails cannot log in:
- Backend checks `is_active` status
- Inactive users are rejected with error message
- User must verify email first

### SSO Users (Google)

Google sign-in users bypass email verification:
- Google already verifies email
- User account is active immediately
- Can access app right away

## Configuration Requirements

### Backend Configuration

#### Environment Variables Required
Ensure these are set in your `.env` or SSM:

```env
# SMTP Configuration (required for email sending)
SMTP_SERVER=smtp.zoho.com  # or your SMTP server
SMTP_PORT=587
SMTP_USERNAME=your-email@zivohealth.ai
SMTP_PASSWORD=your-smtp-password
FROM_EMAIL=your-email@zivohealth.ai

# Frontend URL (for verification links)
FRONTEND_URL=https://app.zivohealth.ai  # or your app URL

# Redis (for token storage)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

#### Email Verification Token Settings
- **Expiry**: 24 hours (86400 seconds)
- **Storage**: Redis
- **Format**: URL-safe token (32 bytes)

### iOS Configuration

#### Info.plist - URL Schemes

Add the following to your `Info.plist` to enable deep links:

```xml
<key>CFBundleURLTypes</key>
<array>
    <dict>
        <key>CFBundleURLName</key>
        <string>com.zivohealth.app</string>
        <key>CFBundleURLSchemes</key>
        <array>
            <string>zivohealth</string>
        </array>
    </dict>
</array>
```

This allows the app to handle URLs like:
- `zivohealth://verify-email?token=xxx`

#### Universal Links (Optional but Recommended)

For production, also configure Universal Links in Xcode:
1. Add Associated Domains capability
2. Add domains: `applinks:app.zivohealth.ai`

This allows HTTPS URLs like:
- `https://app.zivohealth.ai/verify-email?token=xxx`

## Testing

### Backend Testing

1. **Register New User**
```bash
curl -X POST https://your-api.com/dual-auth/email/register \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123",
    "first_name": "Test",
    "last_name": "User"
  }'
```

Expected response:
```json
{
  "message": "Registration successful. Please check your email to verify your account.",
  "email": "test@example.com",
  "verification_required": true
}
```

2. **Check Email**
   - Verification email should be sent to the user
   - Extract token from the email link

3. **Verify Email**
```bash
curl -X POST https://your-api.com/dual-auth/email/verify \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "token": "extracted_token_here"
  }'
```

Expected response:
```json
{
  "message": "Email verified successfully. You can now sign in.",
  "email": "test@example.com",
  "verified": true
}
```

4. **Resend Verification Email**
```bash
curl -X POST https://your-api.com/dual-auth/email/resend-verification \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "email": "test@example.com"
  }'
```

### iOS Testing

1. **Test Deep Links in Simulator**
```bash
# Method 1: Using xcrun
xcrun simctl openurl booted "zivohealth://verify-email?token=test_token_here"

# Method 2: Safari
# Open Safari in simulator and navigate to:
# zivohealth://verify-email?token=test_token_here
```

2. **Test Registration Flow**
   - Launch app
   - Navigate to "Sign Up"
   - Enter details and create account
   - Verify "Verify Your Email" screen appears
   - Check email for verification link
   - Click link (should open app)
   - Verify success message appears

3. **Test Resend Email**
   - On verification waiting screen
   - Click "Resend Verification Email"
   - Check that new email is sent
   - Verify no errors occur

## Database Changes

### User Table
The existing `users` table already has the required fields:
- `is_active` - Set to `False` for unverified users
- `email_verified_at` - Set when email is verified

### Token Storage
Verification tokens are stored in Redis:
- Key format: `email_verification:{user_id}`
- Value: SHA256 hash of token
- TTL: 24 hours

## Security Considerations

1. **Token Security**
   - Tokens are 32-byte URL-safe random strings
   - Stored as SHA256 hashes in Redis
   - 24-hour expiry
   - Single-use (deleted after verification)

2. **User Account Security**
   - Unverified users cannot log in
   - `is_active` = `False` until verification
   - Email verification required for password-based registration

3. **SSO Users**
   - Google users skip email verification
   - Google already verifies email ownership
   - Accounts are active immediately

## Troubleshooting

### User Not Receiving Verification Email

**Possible causes:**
1. SMTP credentials not configured
2. Email in spam folder
3. Email service rate limiting
4. FROM_EMAIL doesn't match SMTP_USERNAME (for Zoho)

**Solutions:**
- Check backend logs for email sending errors
- Verify SMTP configuration
- Use resend verification email feature
- Check email service dashboard

### Deep Links Not Working

**Possible causes:**
1. URL scheme not configured in Info.plist
2. App not installed
3. Token expired

**Solutions:**
- Add URL scheme to Info.plist
- Reinstall app
- Resend verification email for new token

### "Registration Failed" Error

**Possible causes:**
1. Email already exists
2. SMTP configuration issue
3. Redis not available

**Solutions:**
- Use different email
- Check backend logs
- Verify Redis is running
- Check SMTP credentials

## Migration Notes

### Existing Users
Existing users (registered before this implementation) are not affected:
- They already have `is_active = True`
- They can continue logging in normally
- Email verification is only required for new registrations

### Backward Compatibility
The old `/auth/register` endpoint still exists but:
- Creates inactive users if email verification is enabled
- New apps should use `/dual-auth/email/register`

## Future Enhancements

1. **Email Verification Reminder**
   - Send reminder email after 24 hours if not verified
   - Auto-cleanup unverified accounts after 7 days

2. **In-App Verification Check**
   - Poll backend for verification status
   - Auto-navigate when verified (without deep link)

3. **Email Change Verification**
   - Require verification when user changes email
   - Send verification to both old and new email

4. **Phone Verification**
   - Add SMS verification as alternative
   - Support phone-only accounts

## Support

For issues or questions:
1. Check backend logs: `backend/logs/server.log`
2. Check iOS console logs for [DeepLink] and [NetworkService] messages
3. Verify SMTP configuration in environment variables
4. Test email sending manually using backend scripts

## Summary

✅ **Backend**: Complete email verification system with secure token management
✅ **iOS**: Full registration flow with verification waiting screen
✅ **Deep Links**: URL handling for email verification links
✅ **User Experience**: Clear messaging and easy resend functionality
✅ **Security**: Inactive users until verification, secure token storage
✅ **SSO**: Google sign-in bypasses verification (already verified)

The implementation is production-ready and follows security best practices!

