#!/usr/bin/env python3
"""
Script to generate secure API keys for mobile app authentication
"""

import secrets
import string
import hashlib
import base64
import json
from datetime import datetime
from pathlib import Path

def generate_api_key(length: int = 32) -> str:
    """
    Generate a secure API key
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_app_secret(length: int = 64) -> str:
    """
    Generate a secure app secret for HMAC signing
    """
    return secrets.token_hex(length // 2)

def main():
    print("🔐 ZivoHealth API Key Generator")
    print("=" * 40)
    
    # Generate API keys for different apps
    api_keys = {
        "zivohealth_ios": generate_api_key(32),
        "zivohealth_android": generate_api_key(32),
        "zivodoc_ios": generate_api_key(32),
        "zivodoc_android": generate_api_key(32),
    }
    
    # Generate app secret for HMAC signing
    app_secret = generate_app_secret(64)
    
    print("\n📱 Generated API Keys:")
    print("-" * 20)
    for app, key in api_keys.items():
        print(f"{app}: {key}")
    
    print(f"\n🔑 App Secret Key:")
    print("-" * 20)
    print(f"APP_SECRET_KEY: {app_secret}")
    
    # Create environment configuration
    env_config = {
        "VALID_API_KEYS": list(api_keys.values()),
        "APP_SECRET_KEY": app_secret,
        "REQUIRE_API_KEY": True,
        "REQUIRE_APP_SIGNATURE": True,  # Set to True if you want HMAC signing
    }
    
    print(f"\n📝 Environment Configuration:")
    print("-" * 30)
    print(f"VALID_API_KEYS={json.dumps(list(api_keys.values()))}")
    print(f"APP_SECRET_KEY={app_secret}")
    print(f"REQUIRE_API_KEY=true")
    print(f"REQUIRE_APP_SIGNATURE=true")
    
    # Save to file
    output_file = Path("generated_api_keys.json")
    with open(output_file, "w") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "api_keys": api_keys,
            "app_secret": app_secret,
            "env_config": env_config
        }, f, indent=2)
    
    print(f"\n💾 Configuration saved to: {output_file}")
    
    print(f"\n🚀 Next Steps:")
    print("1. Add these keys to your .env file")
    print("2. Update your mobile apps with the corresponding API keys")
    print("3. Restart your backend server")
    print("4. Test authentication with the new keys")
    
    print(f"\n⚠️  Security Notes:")
    print("- Keep these keys secure and don't commit them to version control")
    print("- Rotate keys periodically")
    print("- Use different keys for different environments (dev/staging/prod)")
    print("- Consider enabling HMAC signing for additional security")

if __name__ == "__main__":
    main()
