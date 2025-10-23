# Health Score SQL Scripts - Production Deployment

## Quick Start

```bash
# Run scripts in order:
psql -d your_database -f 01_add_metric_anchors.sql
psql -d your_database -f 02_backfill_sleep_duration.sql
```

---

## Script 1: Add Metric Anchors

**File:** `01_add_metric_anchors.sql`

**Purpose:** Adds 17 metric scoring configurations to `metric_anchor_registry` table

**Safe to run multiple times:** ✅ Yes (uses `ON CONFLICT DO NOTHING`)

**Execution:**
```bash
psql -d your_database -f 01_add_metric_anchors.sql
```

**What it adds:**
- 8 biomarker anchors (A1c, LDL, HDL, Triglycerides, ALT, AST, hs-CRP, Vitamin D)
- 5 vital sign anchors (Heart Rate, BP Systolic, BP Diastolic, SpO2, Temperature)
- 1 activity anchor (Steps)
- 1 sleep anchor (Duration)
- 1 medication anchor (PDC/adherence)
- 1 nutrition anchor (Energy balance)

**Expected output:**
```
 domain      | anchor_count
-------------+--------------
 activity    |            1
 biomarker   |            8
 medication  |            1
 nutrition   |            1
 sleep       |            1
 vitals      |            5
(6 rows)

NOTICE:  ✓ Metric anchors added successfully
NOTICE:  Total active anchors: 17
```

---

## Script 2: Backfill Sleep Duration

**File:** `02_backfill_sleep_duration.sql`

**Purpose:** Converts sleep hours to minutes in `vitals_daily_aggregates.duration_minutes`

**⚠️ IMPORTANT:** Review dry-run queries BEFORE uncommenting the UPDATE statements!

### Step 1: Preview Changes (Dry Run)

Run the script as-is first. It will show you what will be changed:

```bash
psql -d your_database -f 02_backfill_sleep_duration.sql
```

**Review the output carefully:**
```
 user_id |    date    | current_hours | new_duration_minutes | action
---------+------------+---------------+----------------------+------------------
       1 | 2021-02-05 |           6.8 |                  408 | Use total_value
       1 | 2021-03-08 |           4.7 |                  282 | Use total_value
...

 status                          | record_count
---------------------------------+--------------
 Will fix from total_value       |          541
 Will fix from average_value     |            0
 Cannot fix                      |           24
(3 rows)
```

### Step 2: Execute Update

**Edit the SQL file:**
1. Uncomment the `BEGIN;` line (around line 51)
2. Uncomment the `COMMIT;` line (around line 77)
3. Run again:

```bash
psql -d your_database -f 02_backfill_sleep_duration.sql
```

**Expected output:**
```
NOTICE:  ✓ Updated 541 records from total_value
NOTICE:  ✓ Updated 0 records from average_value (fallback)
```

### Step 3: Verify Results

The script includes verification queries that show:
- Total sleep records
- Records with `duration_minutes` populated
- Sample of updated records
- Any remaining NULL records

---

## Alternative: Run Individual Commands

If you prefer to run commands step by step:

### 1. Add Metric Anchors

```bash
psql -d your_database << 'EOF'
BEGIN;

-- Insert biomarker anchors
INSERT INTO metric_anchor_registry (domain, key, loinc_code, unit, pattern, anchors, half_life_days, group_key, active, introduced_in, created_at, updated_at)
VALUES 
    ('biomarker', 'hs_crp_mg_l', '30522-7', 'mg/L', 'lower', 
     '[[1.0,100],[3.0,75],[5.0,60],[10,40],[20,20],[50,5]]'::jsonb,
     180, 'inflammation', true, 'v1', NOW(), NOW()),
    ('activity', 'steps_per_day', NULL, 'steps', 'higher',
     '[[0,0],[2000,20],[5000,50],[7000,70],[10000,90],[12000,95],[15000,100]]'::jsonb,
     NULL, 'physical_activity', true, 'v1', NOW(), NOW())
     -- Add more as needed
ON CONFLICT (domain, key) DO NOTHING;

COMMIT;
EOF
```

### 2. Preview Sleep Backfill

```bash
psql -d your_database << 'EOF'
SELECT 
    COUNT(*) as records_to_update,
    ROUND(AVG(total_value * 60.0), 2) as avg_duration_minutes
FROM vitals_daily_aggregates
WHERE metric_type = 'Sleep'
  AND duration_minutes IS NULL
  AND total_value IS NOT NULL;
EOF
```

### 3. Execute Sleep Backfill

```bash
psql -d your_database << 'EOF'
BEGIN;

UPDATE vitals_daily_aggregates
SET 
    duration_minutes = total_value * 60.0,
    updated_at = NOW()
WHERE metric_type = 'Sleep'
  AND duration_minutes IS NULL
  AND total_value IS NOT NULL
  AND total_value > 0;

COMMIT;
EOF
```

---

## Verification Queries

### Check Metric Anchors

```sql
SELECT domain, key, loinc_code, active 
FROM metric_anchor_registry 
WHERE active = true 
ORDER BY domain, key;
```

### Check Sleep Duration Population

```sql
SELECT 
    COUNT(*) as total_sleep_records,
    COUNT(duration_minutes) as with_duration,
    COUNT(*) FILTER (WHERE duration_minutes IS NULL) as missing_duration,
    ROUND(AVG(duration_minutes), 2) as avg_duration_min
FROM vitals_daily_aggregates 
WHERE metric_type = 'Sleep';
```

### Check Health Score Calculation

```sql
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
```

---

## Rollback Instructions

### Rollback Metric Anchors

```sql
BEGIN;

-- Remove anchors added in this deployment
DELETE FROM metric_anchor_registry 
WHERE introduced_in = 'v1' 
  AND created_at > '2025-10-23 12:00:00';  -- Replace with deployment timestamp

COMMIT;
```

### Rollback Sleep Duration

```sql
BEGIN;

-- Revert duration_minutes to NULL
UPDATE vitals_daily_aggregates
SET duration_minutes = NULL
WHERE metric_type = 'Sleep'
  AND updated_at > '2025-10-23 12:00:00';  -- Replace with deployment timestamp

COMMIT;
```

---

## Troubleshooting

### Issue: Permission Denied

**Error:** `ERROR: permission denied for table metric_anchor_registry`

**Solution:** Ensure you're connected as a user with INSERT/UPDATE privileges:
```bash
psql -d your_database -U admin_user -f script.sql
```

### Issue: Constraint Violation

**Error:** `ERROR: duplicate key value violates unique constraint`

**Solution:** This means anchors already exist. The script uses `ON CONFLICT DO NOTHING`, so this shouldn't happen. If it does, the anchors are already present.

### Issue: NULL Values After Update

**Query to investigate:**
```sql
SELECT user_id, date, total_value, average_value, unit
FROM vitals_daily_aggregates
WHERE metric_type = 'Sleep'
  AND duration_minutes IS NULL
LIMIT 10;
```

These records have no valid data to convert. They can be safely ignored or deleted.

---

## Timeline

**Estimated execution time:**
- Script 1 (Add anchors): ~1-2 seconds
- Script 2 preview: ~5 seconds
- Script 2 update: ~10-60 seconds (depends on data volume)

**Total: ~1-2 minutes**

---

## Support

For issues or questions:
1. Check the PostgreSQL logs for detailed errors
2. Verify database connection and permissions
3. Use the verification queries to diagnose the issue
4. Refer to the rollback instructions if needed

Scripts location: `backend/scripts/sql/`

