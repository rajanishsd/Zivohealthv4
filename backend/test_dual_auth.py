#!/usr/bin/env python3
"""
Test script for dual authentication system
Run this after setting up the database and starting the server
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
API_KEY = "your_api_key_here"  # Replace with actual API key

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
    "X-Device-Id": "test-device-123",
    "X-Device-Model": "iPhone 15 Pro",
    "X-OS-Version": "iOS 17.0",
    "X-App-Version": "1.0.0"
}

def test_email_start():
    """Test email existence check"""
    print("Testing email start...")
    response = requests.post(
        f"{BASE_URL}/auth/email/start",
        headers=headers,
        json={"email": "test@example.com"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_email_password_login():
    """Test email + password login"""
    print("\nTesting email + password login...")
    response = requests.post(
        f"{BASE_URL}/auth/email/password",
        headers=headers,
        json={
            "email": "test@example.com",
            "password": "testpassword"
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_otp_request():
    """Test OTP request"""
    print("\nTesting OTP request...")
    response = requests.post(
        f"{BASE_URL}/auth/email/otp/request",
        headers=headers,
        json={"email": "test@example.com"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_otp_verify():
    """Test OTP verification (will fail without real OTP)"""
    print("\nTesting OTP verify...")
    response = requests.post(
        f"{BASE_URL}/auth/email/otp/verify",
        headers=headers,
        json={
            "email": "test@example.com",
            "code": "123456"
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_google_verify():
    """Test Google SSO verification (will fail without real token)"""
    print("\nTesting Google SSO verify...")
    response = requests.post(
        f"{BASE_URL}/auth/google/verify",
        headers=headers,
        json={"id_token": "fake_google_token"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_refresh_token():
    """Test token refresh (will fail without valid refresh token)"""
    print("\nTesting token refresh...")
    response = requests.post(
        f"{BASE_URL}/auth/refresh",
        headers=headers,
        json={"refresh_token": "fake_refresh_token"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def main():
    """Run all tests"""
    print("🧪 Testing Dual Authentication System")
    print("=" * 50)
    
    tests = [
        ("Email Start", test_email_start),
        ("Email Password Login", test_email_password_login),
        ("OTP Request", test_otp_request),
        ("OTP Verify", test_otp_verify),
        ("Google SSO Verify", test_google_verify),
        ("Token Refresh", test_refresh_token)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
        
        time.sleep(1)  # Small delay between tests
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")

if __name__ == "__main__":
    main()
