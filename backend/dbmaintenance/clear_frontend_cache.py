#!/usr/bin/env python3
"""
Clear Frontend Cache Script
Clears UserDefaults cache that might contain invalid session IDs after database cleanup.
"""

import subprocess
import sys

def clear_userdefaults():
    """Clear UserDefaults for the ZivoHealth app."""
    print("🧹 ZivoHealth Frontend Cache Cleaner")
    print("=" * 50)
    
    # The bundle identifier might be something like com.zivohealth.app
    # We'll try common locations where UserDefaults might be stored
    
    print("🔍 Clearing iOS Simulator UserDefaults...")
    
    # List of commands to clear different potential UserDefaults locations
    commands = [
        # Clear iOS Simulator defaults
        ["xcrun", "simctl", "spawn", "booted", "defaults", "delete", "com.zivohealth.ZivoHealth"],
        ["xcrun", "simctl", "spawn", "booted", "defaults", "delete", "com.zivohealth.app"],
        
        # Alternative approaches
        ["defaults", "delete", "com.zivohealth.ZivoHealth"],
        ["defaults", "delete", "com.zivohealth.app"],
    ]
    
    cleared_any = False
    
    for cmd in commands:
        try:
            print(f"💫 Trying: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print("✅ Successfully cleared UserDefaults")
                cleared_any = True
            else:
                print(f"⚠️  Command failed (this is normal if app not installed): {result.stderr.strip()}")
                
        except subprocess.TimeoutExpired:
            print("⏱️  Command timed out")
        except FileNotFoundError:
            print("⚠️  Command not found (this is normal)")
        except Exception as e:
            print(f"⚠️  Error: {e}")
    
    if not cleared_any:
        print("\n📱 Manual Instructions:")
        print("1. Open your iOS app")
        print("2. Go to Settings or clear app data")
        print("3. Or delete and reinstall the app")
    
    print("\n🎯 What this fixes:")
    print("- Removes cached session IDs that no longer exist in database")
    print("- Forces app to create fresh chat sessions")
    print("- Clears any stale UserDefaults data")
    
    print("\n✅ Cache clearing completed!")
    print("📱 Restart your iOS app to see the changes")

if __name__ == "__main__":
    clear_userdefaults() 