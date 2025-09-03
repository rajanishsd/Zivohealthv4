# Mobile App API Key Configuration Guide

## 🚀 Complete Setup Process

### Step 1: Generate API Keys

```bash
cd backend
python scripts/generate_api_keys.py
```

### Step 2: Update Backend Configuration

Add to your `.env` file:
```env
VALID_API_KEYS=["key1", "key2", "key3", "key4"]
APP_SECRET_KEY=your_app_secret_here
REQUIRE_API_KEY=true
REQUIRE_APP_SIGNATURE=true
```

### Step 3: Update Mobile Apps

#### ZivoHealth iOS
```swift
// In NetworkService.swift, lines ~30-35
private let apiKey = "YOUR_ZIVOHEALTH_IOS_KEY"
private let appSecret = "YOUR_APP_SECRET"
```

#### ZivoDoc iOS  
```swift
// In NetworkService.swift, lines ~30-35
private let apiKey = "YOUR_ZIVODOC_IOS_KEY"
private let appSecret = "YOUR_APP_SECRET"
```

### Step 4: Test Configuration

```bash
# Test with curl
curl -X GET https://zivohealth.ai/api/v1/health \
  -H "X-API-Key: YOUR_API_KEY"
```

## 📱 App-Specific Configuration

### ZivoHealth App
- **Purpose**: Patient-facing app
- **API Key**: Unique key for patient app
- **Authentication**: Patient login flow
- **Endpoints**: Patient-specific features

### ZivoDoc App  
- **Purpose**: Doctor-facing app
- **API Key**: Unique key for doctor app
- **Authentication**: Doctor login flow
- **Endpoints**: Doctor-specific features

## 🔐 Security Implementation

### Request Headers
```http
X-API-Key: your_app_api_key
X-Timestamp: 1640995200
X-App-Signature: hmac_signature_here
Content-Type: application/json
Accept: application/json
Authorization: Bearer user_jwt_token (if authenticated)
```

### Authentication Flow
1. API Key verification (every request)
2. HMAC signature verification (every request)
3. User JWT token validation (if authenticated)
4. Request processing

## 🧪 Testing Checklist

- [ ] API key generation successful
- [ ] Backend configuration updated
- [ ] Mobile app NetworkService updated
- [ ] Health endpoint accessible
- [ ] User registration works
- [ ] User login works
- [ ] Authenticated endpoints work
- [ ] Error handling works correctly

## 🔄 Deployment Process

1. **Development**: Test with generated keys
2. **Staging**: Use staging-specific keys
3. **Production**: Use production keys
4. **App Store**: Verify production keys

## 📞 Support

For issues:
1. Check API key is correct
2. Verify backend configuration
3. Test with curl commands
4. Check server logs
5. Contact development team
