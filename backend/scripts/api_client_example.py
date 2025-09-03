#!/usr/bin/env python3
"""
Example client showing how to use API keys with ZivoHealth API
"""

import requests
import json
import time
import hashlib
import hmac
from typing import Dict, Any

class ZivoHealthAPIClient:
    def __init__(self, base_url: str, api_key: str, app_secret: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.app_secret = app_secret
        self.session = requests.Session()
        
        # Set default headers (without API key to avoid conflicts)
        self.session.headers.update({
            'Content-Type': 'application/json',
        })
    
    def _generate_signature(self, payload: str, timestamp: str) -> str:
        """
        Generate HMAC signature for request authentication
        """
        if not self.app_secret:
            return ""
        
        message = f"{payload}.{timestamp}"
        signature = hmac.new(
            self.app_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Debug output
        print(f"🔐 [Debug] Payload: '{payload}'")
        print(f"🔐 [Debug] Timestamp: {timestamp}")
        print(f"🔐 [Debug] Message: '{message}'")
        print(f"🔐 [Debug] Signature: {signature}")
        
        return signature
    
    def _add_auth_headers(self, data: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Add authentication headers to request
        """
        headers = {
            'X-API-Key': self.api_key  # Always include API key
        }
        
        # Add timestamp for signature
        timestamp = str(int(time.time()))
        headers['X-Timestamp'] = timestamp
        
        # Add signature if app secret is available
        if self.app_secret:
            if data:
                payload = json.dumps(data, sort_keys=True)
            else:
                payload = ""
            signature = self._generate_signature(payload, timestamp)
            headers['X-App-Signature'] = signature
        
        return headers
    
    def register_user(self, email: str, password: str, full_name: str) -> Dict[str, Any]:
        """
        Register a new user
        """
        url = f"{self.base_url}/api/v1/auth/register"
        data = {
            "email": email,
            "password": password,
            "full_name": full_name
        }
        
        headers = self._add_auth_headers(data)
        
        response = self.session.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Login user and get access token
        """
        url = f"{self.base_url}/api/v1/auth/login"
        data = {
            "username": email,
            "password": password
        }
        
        headers = self._add_auth_headers(data)
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        response = self.session.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        """
        Get user profile (requires authentication)
        """
        url = f"{self.base_url}/api/v1/users/me"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'X-API-Key': self.api_key
        }
        
        response = self.session.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> Dict[str, Any]:
        """
        Health check endpoint (requires API key and HMAC signature)
        """
        url = f"{self.base_url}/health"
        headers = self._add_auth_headers()  # Add API key and HMAC signature
        response = self.session.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

def main():
    """
    Example usage of the API client
    """
    # Configuration
    BASE_URL = "http://localhost:8000"  # Local development server
    API_KEY = "UMYpN67NeR0W13cP13O62Mn04yG3tpEx"  # ZivoHealth iOS API key
    APP_SECRET = "c7357b83f692134381cbd7cadcd34be9c6150121aa274599317b5a1283c0205f"  # App secret
    
    # Create client
    client = ZivoHealthAPIClient(BASE_URL, API_KEY, APP_SECRET)
    
    try:
        # Test health check
        print("🏥 Health Check:")
        health = client.health_check()
        print(json.dumps(health, indent=2))
        
        # Test user registration
        print("\n📝 User Registration:")
        user_data = client.register_user(
            email="test2@example.com",
            password="securepassword123",
            full_name="Test User 2"
        )
        print(json.dumps(user_data, indent=2))
        
        # Test login
        print("\n🔐 User Login:")
        login_data = client.login(
            email="test2@example.com",
            password="securepassword123"
        )
        print(json.dumps(login_data, indent=2))
        
        # Test authenticated endpoint
        if 'access_token' in login_data:
            print("\n👤 User Profile:")
            profile = client.get_user_profile(login_data['access_token'])
            print(json.dumps(profile, indent=2))
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")

if __name__ == "__main__":
    main()
