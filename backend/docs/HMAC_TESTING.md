# HMAC Signature Testing Guide

## 🔐 Overview

HMAC (Hash-based Message Authentication Code) signatures provide an additional layer of security by ensuring request authenticity and preventing replay attacks.

## 🧪 Testing HMAC Signatures

### 1. Manual Testing with curl

#### Test without HMAC (should fail)
```bash
curl -X POST https://zivohealth.ai/api/v1/auth/register \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","full_name":"Test User"}'
```

Expected response: `401 Unauthorized - Invalid app signature`

#### Test with HMAC (should succeed)
```bash
# Generate timestamp
TIMESTAMP=$(date +%s)

# Create payload
PAYLOAD='{"email":"test@example.com","password":"test123","full_name":"Test User"}'

# Generate HMAC signature (replace with your app secret)
APP_SECRET="your_app_secret_here"
MESSAGE="${PAYLOAD}.${TIMESTAMP}"
SIGNATURE=$(echo -n "$MESSAGE" | openssl dgst -sha256 -hmac "$APP_SECRET" | cut -d' ' -f2)

# Make request with HMAC signature
curl -X POST https://zivohealth.ai/api/v1/auth/register \
  -H "X-API-Key: your_api_key" \
  -H "X-Timestamp: $TIMESTAMP" \
  -H "X-App-Signature: $SIGNATURE" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
```

Expected response: `200 OK` with user data

### 2. Test with Python Client

Use the provided example client:

```bash
cd backend
python scripts/api_client_example.py
```

### 3. Test with Mobile Apps

#### Enable Debug Logging

Add this to your NetworkService.swift:

```swift
// Add to headers() method
print("🔐 [NetworkService] HMAC Headers:")
print("  X-Timestamp: \(timestamp)")
print("  X-App-Signature: \(signature)")
```

#### Test Different Scenarios

1. **Valid HMAC**: Should work normally
2. **Invalid HMAC**: Should return 401
3. **Missing HMAC**: Should return 401
4. **Expired timestamp**: Should return 401 (if > 5 minutes old)
5. **Future timestamp**: Should return 401

## 🔧 HMAC Configuration

### Backend Settings

```env
REQUIRE_APP_SIGNATURE=true
APP_SECRET_KEY=your_app_secret_here
```

### Mobile App Settings

```swift
// Enable/disable HMAC
private let enableHMAC = true

// App secret for HMAC generation
private let appSecret = "your_app_secret_here"
```

## 🚨 Common Issues

### 1. Signature Mismatch

**Symptoms**: 401 Unauthorized with "Invalid app signature"
**Causes**:
- Wrong app secret
- Incorrect message format
- Encoding issues

**Solutions**:
- Verify app secret is correct
- Check message format: `payload.timestamp`
- Ensure consistent encoding (UTF-8)

### 2. Timestamp Issues

**Symptoms**: 401 Unauthorized with timestamp errors
**Causes**:
- Clock drift between client and server
- Timestamp too old (> 5 minutes)
- Future timestamp

**Solutions**:
- Sync device time
- Check timestamp generation
- Verify timezone settings

### 3. Missing Headers

**Symptoms**: 401 Unauthorized with missing signature/timestamp
**Causes**:
- Headers not being set
- HMAC disabled in app
- Network issues

**Solutions**:
- Check header generation
- Verify HMAC is enabled
- Test network connectivity

## 📊 Debug Information

### Backend Logs

Look for these log entries:
```
🔐 [APIKeyMiddleware] HMAC verification: SUCCESS/FAILED
🔐 [APIKeyMiddleware] Timestamp validation: SUCCESS/FAILED
🔐 [APIKeyMiddleware] Signature validation: SUCCESS/FAILED
```

### Mobile App Logs

Look for these log entries:
```
🔐 [NetworkService] HMAC Headers:
  X-Timestamp: 1640995200
  X-App-Signature: abc123...
```

## 🔄 Testing Checklist

- [ ] HMAC signature generation works
- [ ] Timestamp validation works
- [ ] Signature validation works
- [ ] Replay attack prevention works
- [ ] Error handling works correctly
- [ ] Performance impact is acceptable
- [ ] Mobile app integration works
- [ ] Backend validation works

## 🛡️ Security Considerations

1. **App Secret Security**: Keep app secret secure and rotate regularly
2. **Timestamp Window**: 5-minute window prevents replay attacks
3. **Signature Algorithm**: Uses HMAC-SHA256 for strong security
4. **Message Format**: `payload.timestamp` format prevents tampering
5. **Error Messages**: Generic error messages prevent information leakage

## 📞 Troubleshooting

### Enable Debug Mode

Set environment variable:
```env
LOG_LEVEL=DEBUG
```

### Check Configuration

Verify all settings:
```bash
# Backend
echo $REQUIRE_APP_SIGNATURE
echo $APP_SECRET_KEY

# Mobile app
# Check NetworkService.swift settings
```

### Test Step by Step

1. Test API key only (disable HMAC)
2. Test HMAC only (disable API key)
3. Test both together
4. Test error conditions

---

**⚠️ Security Note**: HMAC signatures significantly improve security but require proper key management and regular rotation.
