# Admin Management Guide

This document explains the Admin Management system in the ZivoHealth dashboard.

## Overview

The Admin Management page allows administrators to:
1. **View all admin users** in the system
2. **Create new admin users** (regular admins only)
3. **Change passwords** for any admin (including super admin)
4. **Delete admin users** (except super admin)

---

## Access

### Requirements
- Must be logged in as an admin user
- Available from Dashboard → Admin Management tab

### URL
```
/api/v1/admin/admins/*
```

---

## User Types

### Super Admin
- **Icon:** 🏆 Gold badge
- **Rights:**
  - Can create regular admins
  - Can delete regular admins
  - Can change any admin's password (including their own)
  - **Cannot** be deleted
  - **Cannot** create another super admin
  - Only ONE super admin exists in the system

### Regular Admin
- **Icon:** 👤 Blue badge
- **Rights:**
  - Can change their own password only
  - Can view other admins
  - **Cannot** delete any admin (including self)
  - **Cannot** create admins (super admin only)

---

## Features

### 1. View Admins

**Display:**
- ID
- Email
- Full Name
- Type (Super Admin / Admin)
- Actions

**Visual Indicators:**
- Super Admin: Gold badge with "Super Admin" label
- Regular Admin: Blue badge with "Admin" label

---

### 2. Create Admin

**Requirements:**
- Must be logged in as super admin
- Cannot create super admins (only regular admins)

**Form Fields:**
- Email * (required, must be unique)
- Password * (required, minimum 8 characters)
- First Name * (required)
- Middle Name (optional)
- Last Name * (required)

**Endpoint:**
```http
POST /api/v1/admin/admins/create
```

**Request:**
```json
{
  "email": "admin@example.com",
  "password": "securepassword",
  "first_name": "John",
  "middle_name": "Michael",
  "last_name": "Doe",
  "full_name": null
}
```

**Response:**
```json
{
  "message": "Admin created successfully",
  "admin": {
    "id": 2,
    "email": "admin@example.com",
    "full_name": "John Michael Doe",
    "is_superadmin": false
  }
}
```

**Validations:**
- Email must be unique
- Password must be at least 8 characters
- Email, first name, last name are required
- Super admin cannot be created via this endpoint

---

### 3. Change Password

**Who Can Change:**
- Super admin can change **any** admin's password
- Regular admin can change **only their own** password

**Form Fields:**
- New Password * (minimum 8 characters)
- Confirm Password * (must match new password)

**Endpoint:**
```http
POST /api/v1/admin/admins/change-password
```

**Request:**
```json
{
  "admin_id": 2,
  "new_password": "newsecurepassword"
}
```

**Response:**
```json
{
  "message": "Password changed successfully for admin admin@example.com"
}
```

**Validations:**
- Password must be at least 8 characters
- Passwords must match
- Regular admins can only change their own password
- Super admin can change any admin's password

---

### 4. Delete Admin

**Who Can Delete:**
- Only super admin can delete admins
- Cannot delete super admin
- Cannot delete yourself

**Confirmation:**
Single confirmation dialog with admin email

**Endpoint:**
```http
DELETE /api/v1/admin/admins/{admin_id}
```

**Response:**
```json
{
  "message": "Admin admin@example.com deleted successfully"
}
```

**Protection Rules:**
- ❌ Cannot delete super admin
- ❌ Cannot delete yourself
- ✅ Can delete other regular admins

---

## API Endpoints Summary

### List Admins
```http
GET /api/v1/admin/admins
Authorization: Bearer {token}
```

### Create Admin
```http
POST /api/v1/admin/admins/create
Authorization: Bearer {token}
Content-Type: application/json

{
  "email": "string",
  "password": "string",
  "first_name": "string",
  "middle_name": "string | null",
  "last_name": "string",
  "full_name": "string | null"
}
```

### Change Password
```http
POST /api/v1/admin/admins/change-password
Authorization: Bearer {token}
Content-Type: application/json

{
  "admin_id": number,
  "new_password": "string"
}
```

### Delete Admin
```http
DELETE /api/v1/admin/admins/{admin_id}
Authorization: Bearer {token}
```

### Check Super Admin
```http
GET /api/v1/admin/admins/check-superadmin
Authorization: Bearer {token}
```

---

## Security Rules

### Super Admin Protection
1. **Cannot be deleted** - Protected at API level
2. **Only one exists** - System ensures single super admin
3. **Cannot create more** - Super admin flag is not exposed in create endpoint
4. **Password can change** - For security maintenance

### Regular Admin Restrictions
1. **Can only change own password** - Authorization check
2. **Cannot delete admins** - Feature not available
3. **Cannot create admins** - Feature not available
4. **Can view all admins** - Read-only access

### General Security
- All endpoints require admin authentication
- API key and HMAC signature verification
- JWT token validation
- Database transaction integrity

---

## Dashboard UI

### Navigation
- Dashboard → 🔐 Admin Management tab

### Admin List Table
| ID | Email | Full Name | Type | Actions |
|----|-------|-----------|------|---------|
| 1 | super@admin.com | Super Admin | 🏆 Super Admin | 🔑 Password |
| 2 | admin@example.com | John Doe | 👤 Admin | 🔑 Password 🗑️ Delete |

### Buttons
- **🔄 Refresh**: Reload admin list
- **+ Create Admin**: Open create modal (green button)
- **🔑 Password**: Change password for that admin (orange button)
- **🗑️ Delete**: Delete admin (red button, not shown for super admin)

---

## Error Handling

### Common Errors

#### 400 - Email Already Exists
```json
{
  "detail": "An admin with this email already exists"
}
```

#### 403 - Cannot Delete Super Admin
```json
{
  "detail": "Cannot delete super admin. Super admin is protected and cannot be removed."
}
```

#### 403 - Insufficient Permissions
```json
{
  "detail": "You can only change your own password"
}
```

#### 404 - Admin Not Found
```json
{
  "detail": "Admin not found"
}
```

#### 400 - Cannot Delete Self
```json
{
  "detail": "Cannot delete your own admin account"
}
```

---

## Use Cases

### Creating a New Admin
1. Super admin logs in
2. Navigates to Admin Management
3. Clicks "+ Create Admin"
4. Fills in required fields:
   - Email: admin@company.com
   - Password: SecurePass123
   - First Name: Jane
   - Last Name: Smith
5. Clicks "Create Admin"
6. New admin appears in list

### Changing Admin Password
1. Admin logs in
2. Navigates to Admin Management
3. Finds their own entry or any admin entry (if super admin)
4. Clicks "🔑 Password" button
5. Enters new password twice
6. Clicks "Change Password"
7. Password updated successfully

### Deleting an Admin
1. Super admin logs in
2. Navigates to Admin Management
3. Finds regular admin to delete
4. Clicks "🗑️ Delete" button
5. Confirms deletion in dialog
6. Admin removed from system

---

## Best Practices

### Password Management
- ✅ Use strong passwords (8+ characters, mix of letters, numbers, symbols)
- ✅ Change passwords regularly
- ✅ Don't share admin passwords
- ✅ Use unique passwords per admin

### Admin Creation
- ✅ Create admins only when needed
- ✅ Use real email addresses for admins
- ✅ Document admin accounts in secure location
- ✅ Review admin list periodically

### Super Admin
- ✅ Keep super admin credentials extremely secure
- ✅ Limit super admin access to necessary personnel
- ✅ Change super admin password regularly
- ✅ Never share super admin credentials

### Account Hygiene
- ✅ Delete unused admin accounts promptly
- ✅ Review active admins monthly
- ✅ Investigate suspicious admin activity
- ✅ Maintain audit logs of admin changes

---

## Database Schema

### Admins Table
```sql
CREATE TABLE admins (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(255),
    middle_name VARCHAR(255),
    last_name VARCHAR(255),
    hashed_password VARCHAR(255) NOT NULL,
    is_superadmin BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timezone_id INTEGER REFERENCES timezone_dictionary(id)
);
```

### Key Fields
- `is_superadmin`: Boolean flag for super admin status
- `is_active`: Boolean flag for active/inactive status
- `hashed_password`: Bcrypt hashed password

---

## Troubleshooting

### Issue: Can't create admin
**Solution:** Only super admin can create admins. Check if logged in as super admin.

### Issue: Can't delete admin
**Solutions:**
- Check if trying to delete super admin (not allowed)
- Check if trying to delete yourself (not allowed)
- Check if logged in as regular admin (not allowed)

### Issue: Can't change another admin's password
**Solution:** Only super admin can change other admins' passwords. Regular admins can only change their own.

### Issue: Password too short
**Solution:** Passwords must be at least 8 characters long. Use a stronger password.

### Issue: Email already exists
**Solution:** Each admin must have a unique email. Use a different email address.

---

## Migration Notes

### Initial Setup
1. Ensure one super admin exists in the system
2. Super admin should be created via database migration or script
3. Never delete or modify super admin status directly in database

### From Legacy System
If migrating from a system where multiple super admins exist:
1. Choose one primary super admin
2. Convert others to regular admins
3. Update `is_superadmin` flag in database

---

## Related Documentation

- [Backend Dashboard Guide](BACKEND_DASHBOARD.md)
- [User Deletion Guide](USER_DELETION_GUIDE.md)
- [API Security](API_SECURITY.md)
- [Database Schema](../alembic/README.md)

---

## Change Log

**October 2025:**
- Created admin management system
- Added create, delete, change password features
- Implemented super admin protection
- Created dashboard UI component
- Added comprehensive documentation

---

## Contact

For questions or issues with admin management:
- Email: contactus@zivohealth.ai
- Documentation: `/backend/docs/ADMIN_MANAGEMENT_GUIDE.md`

