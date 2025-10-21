# User Deletion Guide

This document explains the two types of user deletion available in the ZivoHealth admin dashboard.

## Overview

ZivoHealth provides two deletion options for admin users:

1. **Mark for Deletion (Soft Delete)** - Deactivates accounts but preserves data
2. **Delete Permanently (Hard Delete)** - Removes users and ALL associated data

---

## 1. Mark for Deletion (Soft Delete)

### Endpoint
```
POST /api/v1/admin/users/mark-for-deletion
```

### What It Does
- Sets `is_active = False` (user cannot log in)
- Sets `is_tobe_deleted = True` (marked for deletion)
- Sets `delete_date = now`

### What Is Preserved
✅ **Everything is kept in the database:**
- User account (id, email, created_at, etc.)
- User profile (name, age, height, weight, etc.)
- All health data (nutrition logs, vitals, lab reports)
- All chat sessions and messages
- All appointments and prescriptions
- All related records across all tables

### Use Cases
- Compliance requirements (GDPR, HIPAA data retention)
- Potential account recovery
- Data analysis and auditing
- Temporary account deactivation
- User requested account closure (with grace period)

### Dashboard UI
- **Button:** Orange "Mark for Deletion" button
- **Confirmation:** Single confirmation dialog
- **Effect:** User appears as "inactive" and "to be deleted" in dashboard

---

## 2. Delete Permanently (Hard Delete)

### Endpoint
```
POST /api/v1/admin/users/delete-permanently
```

### What It Does
⚠️ **IRREVERSIBLY DELETES:**
- User account and profile
- All health data (nutrition, vitals, lab reports)
- All chat sessions and messages
- All appointments and prescriptions
- All related records across ALL tables
- Everything associated with the user

### Database Behavior
- Relies on CASCADE foreign key constraints
- Deletes user record, which triggers cascade deletion of related data
- Cannot be undone

### Use Cases
- User explicitly requests complete data removal
- Compliance with "right to be forgotten" (GDPR Article 17)
- Removing test accounts
- Data cleanup for terminated accounts

### Dashboard UI
- **Button:** Red "Delete Permanently" button
- **Confirmation:** Double confirmation dialog with explicit warnings
- **Effect:** User and all data removed from database

---

## API Endpoints

### Mark for Deletion (Soft Delete)

**Request:**
```json
POST /api/v1/admin/users/mark-for-deletion
{
  "user_ids": [1, 2, 3]
}
```

**Response:**
```json
{
  "updated": 3,
  "message": "Marked 3 user(s) for deletion"
}
```

---

### Delete Permanently (Hard Delete)

**Request:**
```json
POST /api/v1/admin/users/delete-permanently
{
  "user_ids": [1, 2, 3]
}
```

**Response (Success):**
```json
{
  "deleted": 3,
  "message": "Permanently deleted 3 user(s) and all associated data"
}
```

**Response (With Errors):**
```json
{
  "deleted": 2,
  "message": "Permanently deleted 2 user(s) and all associated data",
  "errors": [
    "User 3 not found"
  ]
}
```

---

## Backwards Compatibility

The old endpoint `/api/v1/admin/users/delete` is maintained for backwards compatibility and now redirects to `/users/mark-for-deletion` (soft delete).

**Deprecated Endpoint:**
```
POST /api/v1/admin/users/delete
```

**Migration:** Update your clients to use:
- `/api/v1/admin/users/mark-for-deletion` for soft delete
- `/api/v1/admin/users/delete-permanently` for hard delete

---

## Safety Features

### Soft Delete
- Single confirmation dialog
- Clear message that data is preserved
- Can be queried/recovered later

### Hard Delete
- **Double confirmation dialogs**
- Explicit warnings about irreversibility
- Lists all data types that will be deleted
- Transaction-based (all or nothing)
- Error reporting for failed deletions

---

## Dashboard Usage

### Soft Delete Flow
1. Navigate to "Users" tab
2. Select one or more users (checkboxes)
3. Click orange "Mark for Deletion" button
4. Confirm action
5. Users are deactivated, data preserved

### Hard Delete Flow
1. Navigate to "Users" tab
2. Select one or more users (checkboxes)
3. Click red "Delete Permanently" button
4. Read and confirm FIRST warning dialog
5. Read and confirm SECOND warning dialog
6. Users and ALL data permanently deleted

---

## Best Practices

### When to Use Soft Delete
- ✅ Default option for most cases
- ✅ Compliance requirements mandate data retention
- ✅ Uncertain if data might be needed later
- ✅ User requests account closure but might return
- ✅ Testing or temporary deactivation

### When to Use Hard Delete
- ⚠️ User explicitly requests complete data removal
- ⚠️ Legal requirement to delete data (GDPR right to be forgotten)
- ⚠️ Removing test/demo accounts
- ⚠️ Data cleanup after account migration
- ⚠️ Security incident requires data removal

### Never Use Hard Delete For
- ❌ Regular account deactivation
- ❌ Temporary suspensions
- ❌ Without explicit user consent (unless legally required)
- ❌ Without double-checking the user list

---

## Database Schema Considerations

### Soft Delete Fields
The `users` table includes fields for tracking deletion:
```sql
is_active BOOLEAN DEFAULT TRUE
is_tobe_deleted BOOLEAN DEFAULT FALSE
delete_date TIMESTAMP NULL
```

### CASCADE Configuration
Ensure your foreign key constraints have `ON DELETE CASCADE` configured for hard delete to work properly:

```sql
ALTER TABLE user_profiles 
ADD CONSTRAINT fk_user 
FOREIGN KEY (user_id) REFERENCES users(id) 
ON DELETE CASCADE;
```

---

## Monitoring and Auditing

### Logging
Both deletion types are logged with:
- Admin user who performed the action
- Timestamp
- User IDs affected
- Success/failure status

### Queries for Marked Users
```sql
-- Find all users marked for deletion
SELECT id, email, delete_date, is_active 
FROM users 
WHERE is_tobe_deleted = TRUE;

-- Find users marked for deletion in last 7 days
SELECT id, email, delete_date 
FROM users 
WHERE is_tobe_deleted = TRUE 
AND delete_date >= NOW() - INTERVAL '7 days';
```

---

## Security

### Authorization
Both endpoints require:
- ✅ Valid authentication token
- ✅ Admin user role
- ✅ API key authentication
- ✅ HMAC signature verification

### Rate Limiting
Consider implementing rate limiting for deletion endpoints to prevent:
- Accidental bulk deletions
- Malicious mass deletion attempts

---

## Troubleshooting

### Hard Delete Fails
**Issue:** "Failed to delete user" errors

**Possible Causes:**
1. Missing CASCADE foreign key constraints
2. Circular foreign key dependencies
3. Database lock/timeout

**Solution:**
```sql
-- Check for foreign key constraints without CASCADE
SELECT 
    tc.table_name, 
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
JOIN information_schema.referential_constraints AS rc
  ON rc.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND ccu.table_name = 'users'
  AND rc.delete_rule != 'CASCADE';
```

---

## Related Documentation

- [Backend Dashboard Guide](BACKEND_DASHBOARD.md)
- [Database Maintenance](../dbmaintenance/README.md)
- [API Security](API_SECURITY.md)

---

## Change Log

**October 2025:**
- Added soft delete (mark for deletion) endpoint
- Added hard delete (permanent deletion) endpoint
- Updated dashboard UI with two separate buttons
- Maintained backwards compatibility with old endpoint
- Added double confirmation for hard delete
- Created comprehensive documentation

---

## Contact

For questions or issues with user deletion:
- Email: contactus@zivohealth.ai
- Documentation: `/backend/docs/USER_DELETION_GUIDE.md`

