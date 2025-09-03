# ZivoHealth API Security Implementation

This document explains the security measures implemented to ensure that ZivoHealth API endpoints can only be accessed by authorized mobile applications.

## 🔐 Security Overview

The API security implementation uses a multi-layered approach:

1. **API Key Authentication** - Primary method to identify authorized apps
2. **HMAC Signature Verification** - Optional additional layer for request authenticity
3. **CORS Restrictions** - Limits access to specific domains
4. **JWT Tokens** - For user authentication after API key verification

## 🚀 Quick Start

### 1. Generate API Keys

Run the key generation script:

```bash
cd backend
python scripts/generate_api_keys.py
```

This will generate:
- Unique API keys for each mobile app
- App secret for HMAC signing
- Configuration for your `.env` file

### 2. Update Environment Configuration

Add the generated keys to your `.env` file:

```env
# API Security
VALID_API_KEYS=["key1", "key2", "key3", "key4"]
APP_SECRET_KEY=your_app_secret_here
REQUIRE_API_KEY=true
REQUIRE_APP_SIGNATURE=false
```

### 3. Update Mobile Apps

Add the corresponding API key to each mobile app:

#### iOS (ZivoHealth)
```swift
// In NetworkService.swift
private let apiKey = "your_zivohealth_ios_api_key"
```

#### Android (ZivoHealth)
```kotlin
// In NetworkService.kt
private const val API_KEY = "your_zivohealth_android_api_key"
```

#### iOS (ZivoDoc)
```swift
// In NetworkService.swift
private let apiKey = "your_zivodoc_ios_api_key"
```

#### Android (ZivoDoc)
```kotlin
// In NetworkService.kt
private const val API_KEY = "your_zivodoc_android_api_key"
```

## 🔧 Implementation Details

### API Key Authentication

API keys are verified on every request through middleware. Keys can be provided via:

1. **Authorization Header**: `Authorization: Bearer your_api_key`
2. **X-API-Key Header**: `X-API-Key: your_api_key`
3. **Query Parameter**: `?api_key=your_api_key`

### HMAC Signature Verification (Optional)

For additional security, you can enable HMAC signature verification:

```env
REQUIRE_APP_SIGNATURE=true
```

This requires mobile apps to:
1. Include a timestamp in `X-Timestamp` header
2. Generate HMAC signature of request body + timestamp
3. Include signature in `X-App-Signature` header

### CORS Configuration

CORS is configured to only allow requests from authorized domains:

```env
CORS_ORIGINS=["https://zivohealth.ai", "https://www.zivohealth.ai"]
```

## 📱 Mobile App Integration

### Required Headers

Every API request must include:

```http
X-API-Key: your_app_api_key
Content-Type: application/json
```

### Optional Headers (if HMAC enabled)

```http
X-Timestamp: 1640995200
X-App-Signature: hmac_signature_here
```

### Example Request

```http
POST /api/v1/auth/register
Host: zivohealth.ai
X-API-Key: your_api_key_here
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "John Doe"
}
```

## 🛡️ Security Features

### 1. Request Validation
- API key verification on every request
- Timestamp validation (prevents replay attacks)
- HMAC signature verification (optional)

### 2. Rate Limiting
- Built-in FastAPI rate limiting
- Configurable per endpoint

### 3. Error Handling
- Consistent error responses
- No sensitive information in error messages
- Proper HTTP status codes

### 4. Logging
- All authentication attempts logged
- Failed requests tracked
- Security events monitored

## 🔄 Key Rotation

### When to Rotate Keys
- Security breach suspected
- Regular security maintenance
- App updates with security improvements

### Rotation Process
1. Generate new API keys
2. Update mobile apps with new keys
3. Deploy updated apps
4. Update backend configuration
5. Monitor for any issues
6. Remove old keys after confirmation

## 🚨 Security Best Practices

### 1. Key Management
- Store API keys securely in mobile apps
- Use different keys for different environments
- Rotate keys regularly
- Never commit keys to version control

### 2. Network Security
- Use HTTPS for all API communications
- Implement certificate pinning in mobile apps
- Validate server certificates

### 3. App Security
- Implement app integrity checks
- Use code obfuscation
- Implement anti-tampering measures
- Regular security audits

### 4. Monitoring
- Monitor API usage patterns
- Set up alerts for unusual activity
- Log all authentication attempts
- Regular security reviews

## 🧪 Testing

### Test API Key Generation
```bash
python scripts/generate_api_keys.py
```

### Test API Client
```bash
python scripts/api_client_example.py
```

### Manual Testing
```bash
# Test with curl
curl -X POST https://zivohealth.ai/api/v1/auth/register \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","full_name":"Test User"}'
```

## 📋 Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `REQUIRE_API_KEY` | Enable/disable API key requirement | `true` |
| `REQUIRE_APP_SIGNATURE` | Enable/disable HMAC signature verification | `false` |
| `VALID_API_KEYS` | List of valid API keys | `[]` |
| `APP_SECRET_KEY` | Secret for HMAC signature generation | `None` |

## 🔍 Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check API key is correct
   - Verify key is included in request headers
   - Ensure key is in VALID_API_KEYS list

2. **403 Forbidden**
   - Check CORS configuration
   - Verify request origin is allowed
   - Check HMAC signature if enabled

3. **500 Internal Server Error**
   - Check server logs
   - Verify configuration is correct
   - Ensure all required environment variables are set

### Debug Mode

Enable debug logging by setting:

```env
LOG_LEVEL=DEBUG
```

This will provide detailed information about authentication attempts and failures.

## 📞 Support

For security-related issues or questions:

1. Check the logs for detailed error messages
2. Verify configuration settings
3. Test with the provided example client
4. Contact the development team

---

**⚠️ Security Notice**: This implementation provides strong security for mobile app API access. However, security is an ongoing process. Regular reviews and updates are recommended.
