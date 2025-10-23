# Google SSO Configuration

## Problem
Google Sign-In is failing with "Invalid Google token" error. This happens when the backend's `GOOGLE_CLIENT_ID` environment variable doesn't match the iOS app's Google Client ID.

## Solution

### 1. Get the correct Client ID from iOS app

From `apps/iOS/Zivohealth/Sources/Resources/GoogleService-Info.plist`:
```
CLIENT_ID: 859676155552-1rvd88iiqk7nkaa5eethknv8gqurjfgg.apps.googleusercontent.com
```

### 2. Set the environment variable in your backend

Add to your backend `.env` file or environment configuration:

```bash
GOOGLE_CLIENT_ID=859676155552-1rvd88iiqk7nkaa5eethknv8gqurjfgg.apps.googleusercontent.com
```

### 3. Restart the backend

After setting the environment variable, restart your backend service:

```bash
# If using docker:
docker-compose restart zivohealth-api

# If running directly:
# Stop and restart your FastAPI server
```

### 4. Verify the configuration

Check the backend logs when attempting Google Sign-In. You should see:
```
🔍 [AuthService] Verifying Google token with CLIENT_ID: 859676155552-1rvd88iiqk7nkaa5eethknv8gqurjfgg.apps.googleusercontent.com
✅ [AuthService] Google token verified - email: user@example.com, sub: ..., name: ...
```

If you see `CLIENT_ID: None`, the environment variable is not being loaded correctly.

## How it works

1. **iOS App** signs in with Google and gets an ID token
2. **iOS App** sends the ID token to backend at `/api/v1/dual-auth/google/verify`
3. **Backend** verifies the token using Google's public keys and the expected CLIENT_ID
4. **Backend** extracts user info (email, name, etc.) from the verified token
5. **Backend** finds or creates the user automatically
6. **Backend** returns JWT tokens for app authentication

## Auto-registration

When a user signs in with Google for the first time:
- Backend automatically creates a new user account
- Email is marked as verified (since Google verified it)
- User is linked to their Google identity
- No additional registration step required

