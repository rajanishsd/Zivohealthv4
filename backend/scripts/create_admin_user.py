#!/usr/bin/env python3
"""
Script to create an admin user for AWS instance
Run this if no admin users exist in the database
"""

import os
import sys
import getpass
from datetime import datetime

def create_admin_user():
    """Create an admin user interactively"""
    print("👤 Creating Admin User for AWS Instance")
    print("=" * 50)
    
    try:
        from app.db.session import SessionLocal
        from app.models.admin import Admin
        from app.core.security import get_password_hash
        
        db = SessionLocal()
        try:
            # Check if any admin users exist
            existing_admins = db.query(Admin).count()
            if existing_admins > 0:
                print(f"✅ Found {existing_admins} existing admin users")
                response = input("Do you want to create another admin user? (y/N): ")
                if response.lower() != 'y':
                    print("Skipping admin user creation")
                    return
            
            print("\nEnter admin user details:")
            email = input("Email: ").strip()
            if not email:
                print("❌ Email is required")
                return
                
            first_name = input("First Name (optional): ").strip()
            middle_name = input("Middle Name (optional): ").strip()
            last_name = input("Last Name (optional): ").strip()
            password = getpass.getpass("Password: ")
            if not password:
                print("❌ Password is required")
                return
                
            confirm_password = getpass.getpass("Confirm Password: ")
            if password != confirm_password:
                print("❌ Passwords do not match")
                return
            
            # Check if admin with this email already exists
            existing_admin = db.query(Admin).filter(Admin.email == email).first()
            if existing_admin:
                print(f"❌ Admin with email {email} already exists")
                return
            
            # Create new admin user
            hashed_password = get_password_hash(password)
            admin = Admin(
                email=email,
                first_name=first_name or None,
                middle_name=middle_name or None,
                last_name=last_name or None,
                hashed_password=hashed_password,
                is_superadmin=True,  # Make it a super admin
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(admin)
            db.commit()
            db.refresh(admin)
            
            print(f"✅ Admin user created successfully!")
            print(f"   ID: {admin.id}")
            print(f"   Email: {admin.email}")
            name_parts = [p for p in [admin.first_name, admin.middle_name, admin.last_name] if p]
            composed_full_name = " ".join(name_parts)
            print(f"   Full Name: {composed_full_name}")
            print(f"   Super Admin: {admin.is_superadmin}")
            print(f"   Active: {admin.is_active}")
            
        except Exception as e:
            print(f"❌ Error creating admin user: {e}")
            db.rollback()
        finally:
            db.close()
            
    except ImportError as e:
        print(f"❌ Cannot import required modules: {e}")
        print("Make sure you're running this from the backend directory")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def list_admin_users():
    """List existing admin users"""
    print("👥 Existing Admin Users")
    print("=" * 50)
    
    try:
        from app.db.session import SessionLocal
        from app.models.admin import Admin
        
        db = SessionLocal()
        try:
            admins = db.query(Admin).all()
            if not admins:
                print("❌ No admin users found")
                return
                
            print(f"Found {len(admins)} admin users:")
            for admin in admins:
                print(f"  ID: {admin.id}")
                print(f"  Email: {admin.email}")
                name_parts = [p for p in [admin.first_name, admin.middle_name, admin.last_name] if p]
                composed_full_name = " ".join(name_parts)
                print(f"  Full Name: {composed_full_name}")
                print(f"  Super Admin: {admin.is_superadmin}")
                print(f"  Active: {admin.is_active}")
                print(f"  Created: {admin.created_at}")
                print("-" * 30)
                
        except Exception as e:
            print(f"❌ Error listing admin users: {e}")
        finally:
            db.close()
            
    except ImportError as e:
        print(f"❌ Cannot import required modules: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def main():
    """Main function"""
    print("🔧 AWS Admin User Management")
    print("=" * 50)
    
    while True:
        print("\nChoose an option:")
        print("1. List existing admin users")
        print("2. Create new admin user")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == '1':
            list_admin_users()
        elif choice == '2':
            create_admin_user()
        elif choice == '3':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
