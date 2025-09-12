# Google Sign-In Setup Guide

## Current Status
✅ Google Sign-In SDK integrated  
✅ Placeholder GoogleService-Info.plist created  
⚠️ **Action Required**: Replace placeholder values with real Google OAuth credentials

## Setup Steps

### 1. Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing project
3. Enable the Google Sign-In API

### 2. Configure OAuth 2.0 Client
1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth 2.0 Client ID**
3. Select **iOS** as application type
4. Enter bundle ID: `com.zivohealth.app`
5. Download the configuration file

### 3. Update GoogleService-Info.plist
Replace the placeholder file with the downloaded configuration:

```bash
# Replace the placeholder file
cp ~/Downloads/GoogleService-Info.plist /path/to/apps/Zivohealth/GoogleService-Info.plist
```

### 4. Update project.yml URL Scheme
Update the URL scheme in `project.yml` to match your actual client ID:

```yaml
INFOPLIST_KEY_CFBundleURLTypes: |
  <array>
    <dict>
      <key>CFBundleURLName</key>
      <string>GoogleSignIn</string>
      <key>CFBundleURLSchemes</key>
      <array>
        <string>com.googleusercontent.apps.YOUR_ACTUAL_CLIENT_ID</string>
      </array>
    </dict>
  </array>
```

### 5. Regenerate Xcode Project
After updating the configuration:

```bash
cd apps/Zivohealth
xcodegen generate
```

## Testing
1. Build and run the app
2. Navigate to the dual login screen
3. Test Google Sign-In button
4. Verify authentication flow

## Troubleshooting

### Error: "GoogleService-Info.plist not found"
- Ensure the file is in the app bundle
- Check that it's added to the Xcode project resources

### Error: "CLIENT_ID missing or using placeholder values"
- Replace placeholder values with actual Google OAuth credentials
- Ensure the CLIENT_ID matches your iOS OAuth client

### Error: "Configuration error"
- Verify GoogleService-Info.plist has valid values
- Check that the bundle ID matches your OAuth client configuration

## Development vs Production
- **Development**: Use placeholder values (current setup)
- **Production**: Must use real Google OAuth credentials

## Security Notes
- Never commit real GoogleService-Info.plist to version control
- Use environment-specific configurations for different builds
- Consider using build scripts to inject credentials during CI/CD
