# ZivoHealth iOS App - API Key Configuration

## 🔐 Overview

The ZivoHealth iOS app now requires an API key for all API requests to ensure only authorized applications can access the backend services.

## 📋 Configuration Steps

### 1. Generate API Keys

First, generate the API keys using the backend script:

```bash
cd backend
python scripts/generate_api_keys.py
```

This will output something like:
```
📱 Generated API Keys:
--------------------
zivohealth_ios: AbC123XyZ789Def456Ghi789Jkl012Mno345
zivohealth_android: Pqr678Stu901Vwx234Yza567Bcd890Efg123
zivodoc_ios: Hij456Klm789Nop012Qrs345Tuv678Wxy901Zab234
zivodoc_android: Cde567Fgh890Ijk123Lmn456Opq789Rst012Uvw345
```

### 2. Update NetworkService.swift

Replace the placeholder API key and app secret in `Sources/Services/NetworkService.swift`:

```swift
// Find these lines (around line 30-35):
private let apiKey = "ZIVOHEALTH_IOS_API_KEY_HERE"
private let appSecret = "ZIVOHEALTH_APP_SECRET_HERE"

// Replace with your actual keys:
private let apiKey = "AbC123XyZ789Def456Ghi789Jkl012Mno345"
private let appSecret = "your_app_secret_here"
```

### 3. Verify Configuration

The API key is automatically included in all requests via the `headers()` method:

```swift
private func headers(requiresAuth: Bool = true) -> [String: String] {
    var headers = [
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-Key": apiKey, // API key for all requests
    ]

    if requiresAuth {
        headers["Authorization"] = "Bearer \(authToken)"
    }

    return headers
}
```

## 🔧 How It Works

### Request Flow
1. **API Key Verification**: Every request includes the `X-API-Key` header
2. **User Authentication**: After API key verification, user JWT tokens are validated
3. **Request Processing**: If both checks pass, the request is processed

### Headers Sent
```http
X-API-Key: AbC123XyZ789Def456Ghi789Jkl012Mno345
X-Timestamp: 1640995200
X-App-Signature: hmac_signature_here
Content-Type: application/json
Accept: application/json
Authorization: Bearer user_jwt_token (if authenticated)
```

## 🧪 Testing

### Test API Key
```bash
# Test with curl
curl -X GET https://zivohealth.ai/api/v1/health \
  -H "X-API-Key: AbC123XyZ789Def456Ghi789Jkl012Mno345"
```

### Test User Registration
```bash
curl -X POST https://zivohealth.ai/api/v1/auth/register \
  -H "X-API-Key: AbC123XyZ789Def456Ghi789Jkl012Mno345" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","full_name":"Test User"}'
```

## 🚨 Security Notes

1. **Never commit API keys to version control**
2. **Use different keys for different environments** (dev/staging/prod)
3. **Rotate keys periodically** for security
4. **Keep keys secure** and don't share them publicly

## 🔄 Key Rotation

When you need to rotate API keys:

1. Generate new keys using the backend script
2. Update the `apiKey` constant in NetworkService.swift
3. Deploy the updated app
4. Update the backend configuration
5. Remove old keys from backend

## 📞 Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check if API key is correct
   - Verify key is included in request headers
   - Ensure backend has the key in VALID_API_KEYS

2. **403 Forbidden**
   - Check CORS configuration
   - Verify request origin is allowed

3. **Build Errors**
   - Ensure API key is a valid string
   - Check for syntax errors in NetworkService.swift

### Debug Mode

Enable debug logging in Xcode to see request headers:

```swift
// Add this to see request details
print("🔐 [NetworkService] Request headers: \(headers)")
```

## 📱 App Store Deployment

Before deploying to the App Store:

1. ✅ Verify API key is correct
2. ✅ Test all API endpoints
3. ✅ Ensure no debug keys are in production build
4. ✅ Test on different devices and iOS versions

---

**⚠️ Important**: Keep your API keys secure and never expose them in client-side code that could be reverse-engineered. Consider additional security measures like certificate pinning for production apps.
