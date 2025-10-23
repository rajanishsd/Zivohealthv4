# Health Score Recalculation - Quick Reference

## 🚀 Quick Start (3 Commands)

```bash
# 1. Add metric anchors
python scripts/add_health_score_anchors.py

# 2. Backfill sleep data
python scripts/backfill_sleep_duration.py

# 3. Recalculate health scores
python scripts/recalculate_health_scores.py --all-users --days 30
```

---

## 📋 Three Ways to Recalculate

### Method 1: Python Script (Recommended) ⭐

```bash
# All users, last 30 days
python scripts/recalculate_health_scores.py --all-users --days 30

# Single user, last 7 days
python scripts/recalculate_health_scores.py --user-id 1 --days 7

# Force overwrite existing scores
python scripts/recalculate_health_scores.py --user-id 1 --days 30 --force

# Custom date range
python scripts/recalculate_health_scores.py --user-id 1 \
  --start-date 2025-10-01 --end-date 2025-10-23

# Test with limited users
python scripts/recalculate_health_scores.py --all-users --days 7 --limit-users 5
```

**Pros:**
- ✅ Direct calculation using service layer
- ✅ Progress feedback
- ✅ Error handling
- ✅ Batch processing

---

### Method 2: SQL Script

```bash
# Run SQL script
psql -d your_database -f scripts/sql/03_recalculate_health_scores.sql
```

**Then choose an option in the SQL file:**

```sql
-- Option 1: Delete all scores (full recalc)
DELETE FROM health_score_results_daily;

-- Option 2: Delete last 30 days
DELETE FROM health_score_results_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days';

-- Option 3: Delete specific user
DELETE FROM health_score_results_daily
WHERE user_id = 1;

-- Option 4: Delete only zero scores
DELETE FROM health_score_results_daily
WHERE overall_score = 0;
```

**Pros:**
- ✅ Fast for bulk deletion
- ✅ Direct database access
- ✅ Easy to customize

**Cons:**
- ⚠️ Scores recalculate lazily (on-demand)
- ⚠️ Requires app/API to trigger actual calculation

---

### Method 3: API Endpoint

```bash
# Single user, single date
curl -X POST "https://your-api.com/internal/health-score/recompute?user_id=1&date_str=2025-10-23" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Use cases:**
- Manual recalculation for specific user/date
- Debugging
- On-demand recalc from UI

---

## 🔍 Verification Queries

### Check scores exist
```sql
SELECT 
    COUNT(*) as total_scores,
    COUNT(DISTINCT user_id) as unique_users,
    MIN(date) as oldest,
    MAX(date) as newest,
    ROUND(AVG(overall_score), 2) as avg_score
FROM health_score_results_daily;
```

### Check recent scores
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
LIMIT 20;
```

### Find users without scores
```sql
SELECT u.id, u.email, COUNT(hs.id) as score_count
FROM users u
LEFT JOIN health_score_results_daily hs ON u.id = hs.user_id
WHERE u.id IN (SELECT DISTINCT user_id FROM vitals_daily_aggregates)
GROUP BY u.id, u.email
HAVING COUNT(hs.id) = 0;
```

### Check score distribution
```sql
SELECT 
    CASE 
        WHEN overall_score = 0 THEN '0 (broken)'
        WHEN overall_score < 25 THEN '1-24 (very low)'
        WHEN overall_score < 50 THEN '25-49 (low)'
        WHEN overall_score < 75 THEN '50-74 (medium)'
        ELSE '75-100 (good)'
    END as score_range,
    COUNT(*) as count
FROM health_score_results_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY score_range
ORDER BY score_range;
```

---

## 🎯 Common Scenarios

### Scenario 1: First time deployment
```bash
# Fresh installation - calculate all
python scripts/add_health_score_anchors.py
python scripts/backfill_sleep_duration.py
python scripts/recalculate_health_scores.py --all-users --days 365
```

### Scenario 2: Fix broken scores
```bash
# Only recalculate zero scores
psql -d db << 'EOF'
DELETE FROM health_score_results_daily WHERE overall_score = 0;
EOF

python scripts/recalculate_health_scores.py --all-users --days 30
```

### Scenario 3: Test with one user
```bash
# Test calculation before rolling out
python scripts/recalculate_health_scores.py --user-id 1 --days 7
# Check results, then run for all users
```

### Scenario 4: Incremental update
```bash
# Only recalculate last 7 days (for recent fixes)
python scripts/recalculate_health_scores.py --all-users --days 7 --force
```

### Scenario 5: Large dataset
```bash
# Process in batches to avoid timeout
python scripts/recalculate_health_scores.py --all-users --days 30 --limit-users 100
# Run multiple times or remove limit
```

---

## ⏱️ Performance

| Users | Days | Estimated Time |
|-------|------|----------------|
| 1     | 7    | ~10 seconds    |
| 1     | 30   | ~30 seconds    |
| 10    | 30   | ~5 minutes     |
| 100   | 30   | ~30-45 minutes |
| 1000  | 30   | ~5-8 hours     |

**Tips:**
- Run during off-peak hours
- Use `--limit-users` for testing
- Monitor database CPU/memory
- Can run in background

---

## 🔧 Troubleshooting

### Issue: Script is slow
**Solution:**
```bash
# Process fewer users at a time
python scripts/recalculate_health_scores.py --all-users --days 30 --limit-users 50

# Or reduce date range
python scripts/recalculate_health_scores.py --all-users --days 7
```

### Issue: Many errors
**Check:**
1. Metric anchors are installed
2. Sleep data is backfilled
3. Users have actual data

```sql
-- Check setup
SELECT 'Anchors' as check, COUNT(*) FROM metric_anchor_registry WHERE active = true
UNION ALL
SELECT 'Sleep with duration', COUNT(*) FROM vitals_daily_aggregates 
WHERE metric_type = 'Sleep' AND duration_minutes IS NOT NULL;
```

### Issue: Scores still zero
**Debug single user:**
```bash
python scripts/recalculate_health_scores.py --user-id 1 --days 1 --force
```

Check their data:
```sql
-- Check user has data
SELECT metric_type, COUNT(*) 
FROM vitals_daily_aggregates 
WHERE user_id = 1 AND date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY metric_type;
```

---

## 📝 What Each Script Does

| Script | Purpose | Safe to re-run? |
|--------|---------|-----------------|
| `add_health_score_anchors.py` | Add scoring configs | ✅ Yes (idempotent) |
| `backfill_sleep_duration.py` | Fix sleep data | ✅ Yes (skips non-NULL) |
| `recalculate_health_scores.py` | Calculate scores | ✅ Yes (use --force to overwrite) |

---

## 🚨 Important Notes

1. **Run scripts in order:** Anchors → Sleep → Recalculate
2. **Test first:** Use single user or `--limit-users` for testing
3. **Off-peak hours:** Large recalculations should run during low traffic
4. **Monitor:** Watch database CPU and memory during bulk operations
5. **Backup:** Always backup before bulk operations (though these scripts are safe)

---

## 📞 Support

If scores are still incorrect after recalculation:
1. Check metric anchors are present
2. Verify sleep duration_minutes is populated
3. Check user has actual data for those dates
4. Review calculation logs in `health_score_calculations_log` table
5. Enable SQL logging: `echo=True` in `backend/app/db/session.py`

