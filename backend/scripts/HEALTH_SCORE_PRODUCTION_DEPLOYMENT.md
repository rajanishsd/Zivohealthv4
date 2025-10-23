# Health Score Production Deployment Guide

## Overview

This guide covers deploying the health score calculation fixes to production. Two scripts need to be run to complete the deployment.

## Prerequisites

- SSH access to production server
- Python virtual environment activated
- Database access configured

## Deployment Steps

### Step 1: Add Metric Anchors to Database

This script adds the missing scoring configurations (metric anchors) required for health score calculation.

**Script:** `backend/scripts/add_health_score_anchors.py`

**What it does:**
- Adds 17 metric anchors for vitals, biomarkers, activity, sleep, nutrition, and medications
- Safe to run multiple times (idempotent) - skips existing anchors
- No user data is modified

**Run on production:**

```bash
# SSH to production server
ssh your-production-server

# Navigate to backend directory
cd /path/to/backend

# Activate virtual environment
source venv/bin/activate

# Run the script
python scripts/add_health_score_anchors.py
```

**Expected output:**
```
================================================================================
ADDING MISSING METRIC ANCHORS FOR HEALTH SCORE
================================================================================

  - Skipped: biomarker.a1c_pct (already exists)
  + Added: biomarker.hs_crp_mg_l (LOINC: 30522-7)
  + Added: activity.steps_per_day
  ... (more entries)

================================================================================
✓ SUCCESS: 11 added, 0 updated, 6 skipped
================================================================================
```

**Rollback (if needed):**
```sql
-- To remove added anchors (only if something goes wrong)
DELETE FROM metric_anchor_registry WHERE introduced_in = 'v1' AND created_at > 'YYYY-MM-DD HH:MM:SS';
```

---

### Step 2: Backfill Sleep Duration Data

This script converts existing sleep data from hours to minutes in the `duration_minutes` field.

**Script:** `backend/scripts/backfill_sleep_duration.py`

**What it does:**
- Finds all sleep records with NULL `duration_minutes`
- Converts `total_value` (hours) → `duration_minutes` (minutes)
- Processes in batches to avoid memory issues
- Safe to run multiple times (only processes NULL records)

**IMPORTANT: Run dry-run first!**

```bash
# DRY RUN - See what will be changed WITHOUT making changes
python scripts/backfill_sleep_duration.py --dry-run
```

**Review the output carefully.** If everything looks good:

```bash
# Run the actual backfill (processes all users)
python scripts/backfill_sleep_duration.py

# OR process a specific user first to test
python scripts/backfill_sleep_duration.py --user-id 1

# OR use smaller batch size for large datasets
python scripts/backfill_sleep_duration.py --batch-size 50
```

**Expected output:**
```
================================================================================
BACKFILL SLEEP DURATION_MINUTES
================================================================================
Started at: 2025-10-23 15:30:00
Batch size: 100
================================================================================

Found 565 sleep records with NULL duration_minutes
  ✓ Fixed User 1, 2021-02-05: duration_minutes=410 min (from 6.8h)
  ✓ Fixed User 1, 2021-03-08: duration_minutes=280 min (from 4.7h)
  ... (more entries)

  Committed batch of 100 records

================================================================================
SUMMARY
================================================================================
Records fixed: 541
Records skipped (no valid value): 24
Errors: 0
Completed at: 2025-10-23 15:32:00

✓ Successfully backfilled 541 sleep records
================================================================================
```

**Rollback (if needed):**
```sql
-- To revert backfilled sleep records (only if something goes wrong)
UPDATE vitals_daily_aggregates 
SET duration_minutes = NULL 
WHERE metric_type = 'Sleep' 
  AND updated_at > 'YYYY-MM-DD HH:MM:SS';  -- Use timestamp when script started
```

---

### Step 3: Recalculate Health Scores

After updating the metrics, recalculate health scores for existing data.

**Option A: Python Script (Recommended)**

```bash
# Recalculate last 30 days for all users with data
python scripts/recalculate_health_scores.py --all-users --days 30

# Test with single user first
python scripts/recalculate_health_scores.py --user-id 1 --days 7

# Force recalculation (overwrite existing scores)
python scripts/recalculate_health_scores.py --user-id 1 --days 30 --force

# Specific date range
python scripts/recalculate_health_scores.py --user-id 1 \
  --start-date 2025-10-01 --end-date 2025-10-23
```

**Option B: SQL Script**

```bash
# Review and run the SQL script
psql -d your_database -f scripts/sql/03_recalculate_health_scores.sql

# Choose one of the options in the script:
# - Delete all scores (full recalc)
# - Delete last N days only
# - Delete specific users
# - Delete only zero scores
```

**Option C: API Endpoint (Per User)**

```bash
# Recalculate via API
curl -X POST "https://your-api/internal/health-score/recompute?user_id=1&date_str=2025-10-23" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

---

### Step 4: Verify Health Score Calculation

After recalculating, verify health scores are correct:

```bash
# Option 1: Run diagnostic (if you kept the script)
python scripts/diagnose_health_score.py

# Option 2: Query database directly
psql -d your_database << EOF
SELECT 
    user_id, 
    date, 
    overall_score, 
    chronic_score, 
    acute_score, 
    confidence
FROM health_score_results_daily 
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC, overall_score DESC
LIMIT 10;
EOF
```

---

## Script Options Reference

### add_health_score_anchors.py

**No arguments** - Run as-is, safe and idempotent.

### backfill_sleep_duration.py

| Argument | Description | Example |
|----------|-------------|---------|
| `--dry-run` | Show changes without applying | `--dry-run` |
| `--user-id USER_ID` | Process specific user only | `--user-id 1` |
| `--batch-size N` | Records per batch (default: 100) | `--batch-size 50` |

**Examples:**

```bash
# Recommended: Dry run first
python scripts/backfill_sleep_duration.py --dry-run

# Process all users
python scripts/backfill_sleep_duration.py

# Test with one user first
python scripts/backfill_sleep_duration.py --user-id 1

# Large dataset? Use smaller batches
python scripts/backfill_sleep_duration.py --batch-size 50

# Dry run for specific user
python scripts/backfill_sleep_duration.py --user-id 1 --dry-run
```

---

## Monitoring

### Database Queries

```sql
-- Check metric anchor counts
SELECT domain, COUNT(*) as count 
FROM metric_anchor_registry 
WHERE active = true 
GROUP BY domain;

-- Check sleep records with duration_minutes
SELECT 
    COUNT(*) as total_sleep_records,
    COUNT(duration_minutes) as with_duration,
    COUNT(*) - COUNT(duration_minutes) as missing_duration
FROM vitals_daily_aggregates 
WHERE metric_type = 'Sleep';

-- Check recent health scores
SELECT 
    COUNT(DISTINCT user_id) as users_with_scores,
    AVG(overall_score) as avg_score,
    MIN(overall_score) as min_score,
    MAX(overall_score) as max_score
FROM health_score_results_daily 
WHERE date >= CURRENT_DATE - INTERVAL '7 days';
```

---

## Troubleshooting

### Issue: Metric anchors not being used

**Check if anchors exist:**
```sql
SELECT domain, key, loinc_code, active 
FROM metric_anchor_registry 
WHERE active = true;
```

**Solution:** Re-run `add_health_score_anchors.py`

### Issue: Sleep scores still zero

**Check if duration_minutes is populated:**
```sql
SELECT date, total_value, duration_minutes, unit 
FROM vitals_daily_aggregates 
WHERE metric_type = 'Sleep' 
  AND user_id = 1 
ORDER BY date DESC 
LIMIT 10;
```

**Solution:** Re-run `backfill_sleep_duration.py` for affected user

### Issue: Health scores not updating

**Force recomputation via API:**
```bash
curl -X POST "https://your-api/internal/health-score/recompute?user_id=1&date_str=2025-10-23" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

---

## Code Changes Summary

**Files modified:**
1. `backend/app/crud/vitals.py` - Aggregation now populates `duration_minutes`
2. `backend/app/health_scoring/services.py` - Defensive unit handling

**Database changes:**
1. `metric_anchor_registry` - 11-17 new rows
2. `vitals_daily_aggregates` - `duration_minutes` populated for sleep records

**New scripts:**
1. `backend/scripts/add_health_score_anchors.py` - Add metric anchors
2. `backend/scripts/backfill_sleep_duration.py` - Backfill sleep data
3. `backend/scripts/recalculate_health_scores.py` - Batch recalculate scores
4. `backend/scripts/sql/01_add_metric_anchors.sql` - SQL version (add anchors)
5. `backend/scripts/sql/02_backfill_sleep_duration.sql` - SQL version (backfill)
6. `backend/scripts/sql/03_recalculate_health_scores.sql` - SQL version (recalc guide)

---

## Timeline

**Estimated duration:**
- Step 1 (Add anchors): ~5 seconds
- Step 2 (Backfill sleep): ~1-5 minutes (depends on data volume)
- Step 3 (Recalculate scores): ~5-30 minutes (depends on users and date range)
- Step 4 (Verification): ~1 minute

**Total: ~10-40 minutes**

**Note:** Recalculation can run in background while system is live

---

## Support

If issues occur:
1. Check logs for errors
2. Verify database connections
3. Review script output for specific error messages
4. Use rollback SQL if needed

For questions, refer to the code comments in the scripts or contact the development team.

