# CASCADE Delete Migration Guide

## Overview

This guide explains the proper CASCADE delete configuration for user deletion in ZivoHealth.

Instead of manually deleting related data, we've configured database foreign key constraints with `ON DELETE CASCADE`, which automatically handles cleanup when a user is deleted.

---

## The Problem

Previously, the system attempted to manually delete all related data in a specific order. This approach was:
- ❌ Error-prone (easy to miss tables)
- ❌ Difficult to maintain (new tables require code updates)
- ❌ Not following database best practices
- ❌ Causing errors like: "tried to blank-out primary key column"

---

## The Solution

Configure all foreign key constraints to the `users` table with `ON DELETE CASCADE`. When a user is deleted, the database automatically:
1. Identifies all related records
2. Deletes them in the correct order
3. Maintains referential integrity
4. Handles complex relationships automatically

---

## Running the Migration

### Step 1: Backup Your Database (CRITICAL!)

```bash
# Create a backup before running the migration
pg_dump -h localhost -U your_user zivohealth > backup_before_cascade_$(date +%Y%m%d).sql
```

### Step 2: Run the Migration

```bash
cd backend
alembic upgrade head
```

The migration `067_fix_cascade_delete_constraints.py` will:
- Check each table for existing foreign key constraints
- Drop constraints without CASCADE
- Recreate constraints with `ON DELETE CASCADE`
- Skip tables that don't exist
- Report progress for each table

### Step 3: Verify the Migration

```sql
-- Check that CASCADE is configured
SELECT 
    tc.table_name,
    kcu.column_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.referential_constraints AS rc
  ON rc.constraint_name = tc.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND ccu.table_name = 'users'
ORDER BY tc.table_name;
```

You should see `delete_rule = 'CASCADE'` for all constraints.

---

## Tables Updated

The migration updates CASCADE for the following tables:

### Core User Tables
- `user_profiles`
- `user_identities`
- `login_events`
- `user_devices`
- `user_notifications`

### Health Data
- `vitals`, `vitals_aggregates`, `vitals_categorized`, `vitals_raw_categorized`
- `mental_health_logs`, `mental_health_entries`
- `health_scores`

### Lab Reports
- `lab_reports`
- `lab_report_categorized`

### Nutrition
- `nutrition_logs`
- `nutrition_goals` (which cascades to `nutrition_goal_targets`, `nutrition_meal_plans`, `user_nutrient_focus`)

### Communication
- `chat_sessions` (cascades to `chat_messages`)

### Appointments
- `appointments` (cascades to `prescriptions`)

### Other
- `feedback`
- `password_reset_tokens`
- `pharmacy_medications`, `pharmacy_bills`
- `user_health_conditions`, `user_dietary_restrictions`, `user_allergies`, `user_medications`, `user_health_goals`

---

## Testing the CASCADE

### Test 1: Create a Test User with Data

```sql
-- Create test user
INSERT INTO users (email, hashed_password, is_active)
VALUES ('test_cascade@example.com', 'hashed_pwd', true)
RETURNING id;

-- Add related data (profile, vitals, etc.)
-- Use the returned user id
```

### Test 2: Delete the User

```sql
-- This should automatically delete all related data
DELETE FROM users WHERE email = 'test_cascade@example.com';
```

### Test 3: Verify Cleanup

```sql
-- Check that related data was deleted
SELECT COUNT(*) FROM user_profiles WHERE user_id = <test_user_id>;  -- Should be 0
SELECT COUNT(*) FROM vitals WHERE user_id = <test_user_id>;          -- Should be 0
SELECT COUNT(*) FROM nutrition_logs WHERE user_id = <test_user_id>;  -- Should be 0
-- etc.
```

---

## How It Works Now

### Before (Manual Deletion - BAD)
```python
# Had to manually delete 20+ tables in specific order
db.execute("DELETE FROM user_profiles WHERE user_id = :uid")
db.execute("DELETE FROM vitals WHERE user_id = :uid")
db.execute("DELETE FROM nutrition_logs WHERE user_id = :uid")
# ... 20 more DELETE statements
db.delete(user)
```

### After (CASCADE - GOOD)
```python
# Database handles everything automatically
db.delete(user)
db.commit()
# All related data automatically deleted by CASCADE
```

---

## Benefits

### ✅ Automatic
- Database handles all deletions automatically
- No manual tracking of relationships

### ✅ Reliable
- Database ensures referential integrity
- Impossible to miss related records

### ✅ Maintainable
- New tables with foreign keys work automatically
- No code changes needed for new relationships

### ✅ Performant
- Database optimizes deletion order
- Single transaction for all deletions

### ✅ Correct
- Follows SQL standard best practices
- Prevents orphaned records

---

## Rollback (Not Recommended)

If you need to rollback the migration:

```bash
cd backend
alembic downgrade -1
```

**Warning:** This will remove CASCADE, which means user deletion will fail until you manually delete related data again.

---

## Adding New Tables

When creating new tables with foreign keys to `users`:

```sql
-- CORRECT: Include ON DELETE CASCADE
CREATE TABLE new_user_data (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    data TEXT
);
```

```python
# CORRECT: In SQLAlchemy models
class NewUserData(Base):
    __tablename__ = 'new_user_data'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    data = Column(String)
```

---

## Migration Output Example

```
Fixing CASCADE constraints for user-related tables...
  ✅ Fixed user_profiles
  ✅ Fixed user_identities
  ✅ Fixed login_events
  ✅ Fixed user_devices
  ✅ Fixed vitals
  ✅ Fixed nutrition_logs
  ✅ Fixed chat_sessions
  ⏭️  Skipping test_table (table does not exist)
  ⚠️  Warning: Could not fix old_table: relation does not exist
✅ CASCADE constraints fixed successfully!
```

---

## Troubleshooting

### Issue: Migration fails on a table

**Solution:** The migration will continue with other tables. Check the specific error and manually fix that constraint if needed.

### Issue: CASCADE not working after migration

**Solution:** 
1. Check constraint configuration:
```sql
SELECT * FROM information_schema.referential_constraints 
WHERE constraint_name LIKE '%user_id%';
```

2. Verify delete_rule is 'CASCADE'

### Issue: Need to add CASCADE to custom table

**Solution:**
```sql
-- Drop existing constraint
ALTER TABLE your_table DROP CONSTRAINT your_table_user_id_fkey;

-- Add with CASCADE
ALTER TABLE your_table
ADD CONSTRAINT your_table_user_id_fkey
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
```

---

## Production Deployment

### Pre-deployment Checklist

- [ ] Backup database
- [ ] Test migration in staging environment
- [ ] Verify CASCADE works with test user
- [ ] Plan maintenance window (migration is fast but affects all tables)
- [ ] Notify team of deployment

### Deployment Steps

```bash
# 1. Backup
pg_dump production_db > backup_cascade_$(date +%Y%m%d).sql

# 2. Run migration
cd backend
alembic upgrade head

# 3. Verify
psql -d production_db -f verify_cascade.sql

# 4. Test with dummy user
# Create, add data, delete, verify cleanup

# 5. Monitor logs
tail -f logs/server.log
```

---

## Performance Impact

### Migration
- **Time:** Fast (< 1 minute for most databases)
- **Locks:** Brief table locks during constraint recreation
- **Downtime:** Minimal (consider maintenance window for production)

### User Deletion
- **Before:** Slow (20+ queries, explicit deletes)
- **After:** Fast (1 delete, CASCADE handles rest)
- **Performance:** Better (database optimized)

---

## Related Documentation

- [User Deletion Guide](USER_DELETION_GUIDE.md)
- [Admin Management Guide](ADMIN_MANAGEMENT_GUIDE.md)
- [Database Schema](../alembic/README.md)

---

## Summary

✅ **Run the migration:**
```bash
cd backend
alembic upgrade head
```

✅ **Verify CASCADE:**
```sql
SELECT table_name, delete_rule 
FROM information_schema.referential_constraints
WHERE delete_rule = 'CASCADE';
```

✅ **Test deletion:**
- Create test user → Add data → Delete user → Verify cleanup

✅ **Deploy confidently:**
- Proper database design
- Automatic cleanup
- No more manual deletions

---

**Last Updated:** October 2025  
**Migration:** 067_fix_cascade_delete_constraints.py  
**Status:** Ready for production

