# Dual Login System Implementation

## Overview

This implementation provides a comprehensive dual login system for patients with both email-based authentication (password or OTP) and Google SSO integration. The system includes complete audit logging of login events with device and location tracking.

## Features

### 1. Email Authentication
- **Email + Password**: Traditional login with email and password
- **Email + OTP**: Passwordless login using one-time codes sent via email
- **Seamless Signup**: New users can be created through OTP verification

### 2. Google SSO
- **Google Sign-In**: Integration with Google OAuth 2.0 using PKCE for iOS
- **PKCE Security**: Uses Proof Key for Code Exchange (no client secret needed for mobile)
- **Account Linking**: Automatic linking of Google accounts with existing email accounts
- **Verified Email**: Google-verified emails are automatically marked as verified

### 3. Audit & Security
- **Login Events**: Complete audit trail of all login attempts
- **Device Tracking**: Capture device ID, model, OS version, app version
- **Location Tracking**: IP-based geolocation (country, region, city)
- **Rate Limiting**: OTP rate limiting per email address
- **Security Headers**: Support for device identification headers

### 4. Core Architecture
- **AuthService**: Centralized authentication service in `app/core/`
- **Modular Design**: Clean separation between auth logic and API endpoints
- **Extensible**: Easy to add new authentication providers

## Database Schema

### New Tables

#### `user_identities`
- Links users to multiple authentication providers
- Supports email, Google, and future providers
- Tracks email verification status per provider

#### `login_events`
- Complete audit log of all login attempts
- Captures method, device info, location, success/failure
- Indexed for efficient querying by user and time

#### Updated `users` table
- `hashed_password`: Made nullable for Google-only users
- `email_verified_at`: Timestamp of email verification
- `last_login_at`: Timestamp of last successful login

## API Endpoints

### Email Flow
- `POST /auth/email/start` - Check if email exists
- `POST /auth/email/password` - Login with email and password
- `POST /auth/email/otp/request` - Request OTP code
- `POST /auth/email/otp/verify` - Verify OTP and login

### Google SSO Flow
- `POST /auth/google/verify` - Verify Google ID token and login

### Token Management
- `POST /auth/refresh` - Refresh access tokens

## Configuration

### Environment Variables
Add these to your `.env` file:

```env
# Google OAuth Configuration (iOS Mobile App)
GOOGLE_CLIENT_ID=your_ios_client_id  # iOS client ID from Google Cloud Console
GOOGLE_WEB_CLIENT_ID=your_web_client_id  # Optional: Web client ID for server-side operations
GOOGLE_WEB_CLIENT_SECRET=your_web_client_secret  # Optional: Web client secret for server-side operations

# OTP Configuration
OTP_LENGTH=6
OTP_EXPIRY_MINUTES=10
OTP_MAX_ATTEMPTS=5
OTP_RATE_LIMIT_PER_EMAIL=5
```

### SSM Parameter Store
Store Google OAuth credentials in AWS SSM Parameter Store:
- `/zivohealth/google/client_id` (iOS client ID)
- `/zivohealth/google/web_client_id` (Optional: Web client ID)
- `/zivohealth/google/web_client_secret` (Optional: Web client secret)

## Mobile App Integration

### Device Headers
Include these headers in all auth requests:
```
X-Device-Id: unique_device_identifier
X-Device-Model: iPhone 15 Pro
X-OS-Version: iOS 17.0
X-App-Version: 1.0.0
```

### Google Sign-In SDK (iOS)
1. **Configure Google Sign-In SDK** in your iOS app
2. **Set up OAuth 2.0 client** in Google Cloud Console:
   - Create an iOS OAuth 2.0 client
   - Add your iOS bundle identifier
   - Download the `GoogleService-Info.plist` file
3. **Implement PKCE flow** (handled automatically by Google Sign-In SDK)
4. **Obtain `id_token`** from Google Sign-In response
5. **Send `id_token`** to `/auth/google/verify` endpoint

**Important**: iOS apps use PKCE (Proof Key for Code Exchange) for security, so no client secret is needed or stored in the mobile app.

### Google Cloud Console Setup for iOS

1. **Go to Google Cloud Console** → APIs & Services → Credentials
2. **Create OAuth 2.0 Client ID**:
   - Application type: **iOS**
   - Name: "ZivoHealth iOS App"
   - Bundle ID: Your iOS app's bundle identifier (e.g., `com.zivohealth.app`)
3. **Download Configuration**:
   - Download the `GoogleService-Info.plist` file
   - Add it to your iOS project
4. **Configure iOS App**:
   - Add the `GoogleService-Info.plist` to your Xcode project
   - Configure URL schemes in `Info.plist`
   - Add Google Sign-In SDK to your project

**No client secret is generated or needed for iOS OAuth clients** - this is the correct and secure approach for mobile applications.

### Example Request Flow

#### Email + Password
```swift
// 1. Check email exists
POST /auth/email/start
{
  "email": "user@example.com"
}

// 2. Login with password
POST /auth/email/password
{
  "email": "user@example.com",
  "password": "userpassword"
}
```

#### Email + OTP
```swift
// 1. Request OTP
POST /auth/email/otp/request
{
  "email": "user@example.com"
}

// 2. Verify OTP
POST /auth/email/otp/verify
{
  "email": "user@example.com",
  "code": "123456"
}
```

#### Google SSO (iOS with PKCE)
```swift
// 1. Configure Google Sign-In (done once in AppDelegate)
GIDSignIn.sharedInstance.configuration = GIDConfiguration(
    clientID: "YOUR_IOS_CLIENT_ID"
)

// 2. Sign in with Google (handles PKCE automatically)
GIDSignIn.sharedInstance.signIn(withPresenting: viewController) { result, error in
    guard let result = result else { return }
    
    // 3. Get id_token from Google SDK
    let idToken = result.user.idToken?.tokenString
    
    // 4. Send to backend for verification
    // POST /auth/google/verify
    // {
    //   "id_token": idToken
    // }
}
```

## Security Features

### Rate Limiting
- OTP requests: 5 per email per day
- OTP verification: 5 attempts per code
- Automatic cleanup of expired OTPs

### Token Management
- Short-lived access tokens (configurable expiry)
- Long-lived refresh tokens
- Secure token generation using JWT

### Audit Logging
- All login attempts logged (successful and failed)
- Device fingerprinting
- IP-based geolocation
- Error code tracking for failed attempts

## Email Templates

### OTP Email
- Professional HTML and text templates
- Large, easy-to-read OTP code
- Clear expiry information
- Branded with ZivoHealth styling

## Error Handling

### Common Error Codes
- `invalid_credentials`: Wrong email/password
- `invalid_otp`: Wrong or expired OTP
- `invalid_google_token`: Invalid Google ID token
- `rate_limited`: Too many OTP requests
- `account_locked`: Account temporarily locked

### Response Format
```json
{
  "detail": "Error message",
  "error_code": "invalid_credentials"
}
```

## Migration

### Database Migration
Run the Alembic migration to create new tables:
```bash
alembic upgrade head
```

### Data Migration
- Existing users will have their `hashed_password` preserved
- New `email` identity will be created for existing users
- No data loss during migration

## Testing

### Test Scenarios
1. **Email + Password**: Valid and invalid credentials
2. **Email + OTP**: Request, verify, and rate limiting
3. **Google SSO**: Valid and invalid tokens
4. **Account Linking**: Google account with existing email
5. **New User Creation**: Via OTP and Google SSO
6. **Rate Limiting**: OTP request limits
7. **Device Tracking**: Verify device info capture
8. **Audit Logging**: Verify all events are logged

### Test Data
- Use test Google OAuth credentials for development
- Mock email service for OTP testing
- Test device headers for device tracking

## Monitoring

### Key Metrics
- Login success/failure rates by method
- OTP request patterns
- Device and location distribution
- Error code frequency

### Alerts
- High failure rates
- Unusual login patterns
- Rate limit violations
- Geographic anomalies

## Future Enhancements

### Planned Features
- Apple Sign-In integration
- Multi-factor authentication
- Biometric authentication
- Advanced fraud detection
- Real-time location verification

### Scalability
- Redis clustering for OTP storage
- Database partitioning for login events
- CDN for email templates
- Microservice architecture

## Troubleshooting

### Common Issues
1. **Google OAuth not working**: 
   - Check iOS client ID is correct
   - Verify bundle identifier matches Google Cloud Console
   - Ensure `GoogleService-Info.plist` is properly configured
2. **OTP emails not sending**: Verify SMTP configuration
3. **Rate limiting too strict**: Adjust `OTP_RATE_LIMIT_PER_EMAIL`
4. **Device tracking missing**: Ensure headers are sent from mobile app
5. **PKCE flow issues**: Google Sign-In SDK handles PKCE automatically - don't implement manually

### Debug Mode
Set `ENVIRONMENT=development` to enable:
- Email content logging
- Detailed error messages
- Debug headers in responses

## Support

For issues or questions:
1. Check the audit logs in `login_events` table
2. Verify configuration in SSM Parameter Store
3. Test with development environment first
4. Review error codes and messages
