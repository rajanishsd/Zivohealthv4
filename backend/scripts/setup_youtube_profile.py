#!/usr/bin/env python3
"""
YouTube Profile Setup Helper
This script helps users find and configure their browser profile for YouTube authentication.
"""

import os
import platform
from pathlib import Path

def find_chrome_profile_paths():
    """Find Chrome profile paths on different operating systems."""
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        base_path = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    elif system == "windows":
        base_path = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    elif system == "linux":
        base_path = Path.home() / ".config" / "google-chrome"
    else:
        return []
    
    profiles = []
    if base_path.exists():
        profiles.append(str(base_path))
        # Look for additional profiles
        for item in base_path.iterdir():
            if item.is_dir() and item.name.startswith("Profile"):
                profiles.append(str(item))
    
    return profiles

def find_firefox_profile_paths():
    """Find Firefox profile paths on different operating systems."""
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        base_path = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
    elif system == "windows":
        base_path = Path.home() / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles"
    elif system == "linux":
        base_path = Path.home() / ".mozilla" / "firefox"
    else:
        return []
    
    profiles = []
    if base_path.exists():
        for item in base_path.iterdir():
            if item.is_dir():
                profiles.append(str(item))
    
    return profiles

def setup_youtube_profile():
    """Interactive setup for YouTube profile configuration."""
    print("🎥 YouTube Profile Setup Helper")
    print("=" * 40)
    
    print("\nThis tool will help you configure browser profile authentication for YouTube.")
    print("Using a browser profile allows access to age-restricted and login-required videos.\n")
    
    # Choose browser
    print("Available browsers:")
    print("1. Chrome")
    print("2. Firefox")
    
    while True:
        choice = input("\nChoose your browser (1 or 2): ").strip()
        if choice == "1":
            browser = "chrome"
            profiles = find_chrome_profile_paths()
            break
        elif choice == "2":
            browser = "firefox"
            profiles = find_firefox_profile_paths()
            break
        else:
            print("Please enter 1 or 2")
    
    if not profiles:
        print(f"\n❌ No {browser.title()} profiles found on your system.")
        print(f"Please make sure {browser.title()} is installed and has been run at least once.")
        return
    
    print(f"\n✅ Found {browser.title()} profiles:")
    for i, profile in enumerate(profiles, 1):
        print(f"{i}. {profile}")
    
    # Choose profile
    while True:
        try:
            choice = int(input(f"\nChoose a profile (1-{len(profiles)}): ").strip())
            if 1 <= choice <= len(profiles):
                selected_profile = profiles[choice - 1]
                break
            else:
                print(f"Please enter a number between 1 and {len(profiles)}")
        except ValueError:
            print("Please enter a valid number")
    
    print(f"\n✅ Selected profile: {selected_profile}")
    
    # Generate environment variables
    print("\n📝 Configuration:")
    print("Add these environment variables to your .env file or system environment:")
    print(f"YOUTUBE_USER_PROFILE_PATH='{selected_profile}'")
    print(f"BROWSER_TYPE='{browser}'")
    
    # Create .env entry
    env_file = Path(".env")
    env_content = f"\n# YouTube Profile Configuration\nYOUTUBE_USER_PROFILE_PATH='{selected_profile}'\nBROWSER_TYPE='{browser}'\n"
    
    if env_file.exists():
        with open(env_file, "a") as f:
            f.write(env_content)
        print(f"\n✅ Configuration added to {env_file}")
    else:
        with open(env_file, "w") as f:
            f.write(env_content)
        print(f"\n✅ Created {env_file} with configuration")
    
    print("\n🔒 Security Notes:")
    print("- Make sure you're logged into YouTube in the selected browser profile")
    print("- The profile will be used to access YouTube with your authentication")
    print("- Keep your browser profile secure and don't share it")
    
    print("\n🚀 You're all set!")
    print("The nutrition tools will now use your browser profile for YouTube access.")

if __name__ == "__main__":
    setup_youtube_profile() 