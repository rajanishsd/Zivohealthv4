# Prescription Grouping Fix

## Problem
Prescriptions from the same consultation were appearing as separate cards in the iOS app instead of being grouped together in one card.

## Root Cause
When doctors added multiple medications during a consultation, each medication was being saved with a different `prescription_group_id` because they were created sequentially with timestamp-based IDs. This caused each medication to appear as a separate card.

## Solution

### 1. Backend API Changes
Updated the doctor API endpoint (`/api/v1/doctors/consultation-requests/{request_id}/prescriptions`) to generate a single `prescription_group_id` for all medications in a consultation:

- **File**: `backend/app/api/v1/endpoints/doctors.py`
- **Change**: Generate one group ID before the loop and pass it to all prescriptions
- **Group ID Format**: `grp_consult_{consultation_id}_{timestamp}`

### 2. Database Migration
The migration `068_add_prescription_group_id.py` adds:
- `prescription_group_id` column (String, 64 chars, nullable)
- Index on `prescription_group_id` for efficient grouping queries

### 3. iOS App Support
The iOS app already has support for grouped prescriptions:
- **iOS 16+**: Uses `PrescriptionGroupsCard` which displays grouped prescriptions
- **iOS 15**: Uses legacy `PrescriptionsListCard` (flat list)

The backend API returns grouped data via `/chat-sessions/prescriptions/patient` endpoint.

## Deployment Steps

### Step 1: Apply Database Migration
```bash
cd backend
alembic upgrade head
```

### Step 2: Backfill Existing Prescriptions
Run the backfill script to fix existing prescriptions:

```bash
cd backend
python scripts/backfill_prescription_groups.py
```

This script will:
- Group prescriptions by `consultation_request_id` (prescriptions from same consultation)
- Group prescriptions by session + doctor + date (for prescriptions without consultation ID)
- Update all prescriptions with proper group IDs

### Step 3: Deploy Backend
Deploy the updated backend with the API changes:

```bash
# Your standard deployment process
./scripts/dev/push-and-deploy.sh
```

### Step 4: Test
1. **Existing Prescriptions**: Check that prescriptions from the same consultation now appear in one card
2. **New Prescriptions**: Have a doctor add multiple medications in a consultation and verify they appear grouped

## Expected Behavior After Fix

### Before:
```
┌─────────────────────────────┐
│ Dr. Name                    │
│ Jul 15, 2025 at 1:20PM     │
│ Medication A                │
└─────────────────────────────┘

┌─────────────────────────────┐
│ Dr. Name                    │
│ Jul 15, 2025 at 1:20PM     │
│ Medication B                │
└─────────────────────────────┘
```

### After:
```
┌─────────────────────────────┐
│ Dr. Name                    │
│ Jul 15, 2025 at 1:20PM     │
│ Medication A - dosage       │
│ Medication B - dosage       │
│ + 2 more                    │
└─────────────────────────────┘
```

## Files Modified
1. `backend/app/api/v1/endpoints/doctors.py` - Generate single group ID for consultations
2. `backend/alembic/versions/068_add_prescription_group_id.py` - Fixed index name
3. `backend/scripts/backfill_prescription_groups.py` - New backfill script

## Notes
- The prescription agent (`prescription_clinical_agent.py`) already generates proper group IDs for uploaded prescriptions
- The grouping logic handles both consultation-based prescriptions and user-uploaded prescriptions
- Existing prescriptions will continue to work during migration (backward compatible)

