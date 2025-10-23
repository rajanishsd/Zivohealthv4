#!/usr/bin/env python3
"""
Backfill duration_minutes for existing sleep records in VitalsDailyAggregate table.

This script converts sleep data stored in total_value (hours) to duration_minutes (minutes)
for records where duration_minutes is NULL.

Safe to run multiple times - only processes records with NULL duration_minutes.
"""
import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import and_, func
from app.models import VitalsDailyAggregate
from app.db.session import SessionLocal

def backfill_sleep_duration_minutes(user_id=None, batch_size=100, dry_run=False):
    """
    Backfill duration_minutes for sleep records where it's NULL.
    
    Args:
        user_id: Optional user_id to process. If None, processes all users.
        batch_size: Number of records to process in each batch (default: 100)
        dry_run: If True, only show what would be done without making changes
    
    Returns:
        Tuple of (records_fixed, records_skipped, errors)
    """
    db = SessionLocal()
    
    try:
        # Build query for sleep records with NULL duration_minutes
        query = db.query(VitalsDailyAggregate).filter(
            and_(
                VitalsDailyAggregate.metric_type == "Sleep",
                VitalsDailyAggregate.duration_minutes == None
            )
        )
        
        # Filter by user if specified
        if user_id is not None:
            query = query.filter(VitalsDailyAggregate.user_id == user_id)
        
        # Order by date for consistent processing
        query = query.order_by(VitalsDailyAggregate.user_id, VitalsDailyAggregate.date)
        
        # Count total records to process
        total_count = query.count()
        
        print(f"Found {total_count} sleep records with NULL duration_minutes")
        if user_id is not None:
            print(f"Filtering by user_id: {user_id}")
        
        if dry_run:
            print("\n*** DRY RUN MODE - No changes will be made ***\n")
        
        if total_count == 0:
            print("No records to process.")
            return 0, 0, 0
        
        fixed_count = 0
        skipped_count = 0
        error_count = 0
        processed = 0
        
        # Process in batches
        # Track records we've seen to avoid infinite loop
        processed_ids = set()
        safety_stop = False
        
        while True:
            # Fetch batch, excluding already processed records
            batch = query.filter(
                ~VitalsDailyAggregate.id.in_(processed_ids) if processed_ids else True
            ).limit(batch_size).all()
            
            if not batch:
                break
            
            for record in batch:
                # Mark as processed to avoid reprocessing
                processed_ids.add(record.id)
                processed += 1
                
                # Safety check: prevent infinite processing
                if processed > total_count * 2:
                    print(f"\n⚠️ Safety limit reached! Processed {processed} records but expected {total_count}")
                    print("This might indicate an infinite loop. Stopping.")
                    safety_stop = True
                    break
                
                try:
                    # Try to infer duration_minutes from total_value
                    if record.total_value is not None and record.total_value > 0:
                        # total_value is in hours, convert to minutes
                        duration_mins = record.total_value * 60.0
                        
                        log_msg = f"  [{processed}/{total_count}] User {record.user_id}, {record.date}: "
                        log_msg += f"duration_minutes={duration_mins:.0f} min (from {record.total_value:.1f}h)"
                        
                        if not dry_run:
                            record.duration_minutes = duration_mins
                            print(f"✓ Fixed {log_msg}")
                            fixed_count += 1
                        else:
                            print(f"[DRY RUN] Would fix {log_msg}")
                            fixed_count += 1
                            
                    elif record.average_value is not None and record.average_value > 0:
                        # Fallback to average_value
                        duration_mins = record.average_value * 60.0
                        
                        log_msg = f"  [{processed}/{total_count}] User {record.user_id}, {record.date}: "
                        log_msg += f"duration_minutes={duration_mins:.0f} min (from average_value={record.average_value:.1f}h)"
                        
                        if not dry_run:
                            record.duration_minutes = duration_mins
                            print(f"✓ Fixed {log_msg}")
                            fixed_count += 1
                        else:
                            print(f"[DRY RUN] Would fix {log_msg}")
                            fixed_count += 1
                    else:
                        # Cannot fix - no valid value
                        skipped_count += 1
                        if processed <= 20 or processed % 100 == 0:  # Only log first 20 or every 100th
                            print(f"  ⚠️  [{processed}/{total_count}] User {record.user_id}, {record.date}: Cannot fix - no valid value")
                        
                except Exception as e:
                    error_count += 1
                    print(f"  ✗ Error processing user {record.user_id}, {record.date}: {e}")
            
            # Commit batch if not dry run
            if not dry_run:
                db.commit()
                print(f"\n  Committed batch of {len(batch)} records\n")
            
            # Check if we should stop
            if safety_stop:
                break
        
        return fixed_count, skipped_count, error_count
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description='Backfill duration_minutes for sleep records',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be changed (recommended first)
  python backfill_sleep_duration.py --dry-run
  
  # Process all users
  python backfill_sleep_duration.py
  
  # Process specific user only
  python backfill_sleep_duration.py --user-id 1
  
  # Process with smaller batch size
  python backfill_sleep_duration.py --batch-size 50
        """
    )
    
    parser.add_argument(
        '--user-id',
        type=int,
        help='Optional: Process only this user_id',
        default=None
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        help='Number of records to process in each batch (default: 100)',
        default=100
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("BACKFILL SLEEP DURATION_MINUTES")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Batch size: {args.batch_size}")
    if args.user_id:
        print(f"User ID filter: {args.user_id}")
    if args.dry_run:
        print("Mode: DRY RUN (no changes will be made)")
    print("=" * 80)
    print()
    
    try:
        fixed, skipped, errors = backfill_sleep_duration_minutes(
            user_id=args.user_id,
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )
        
        print()
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Records fixed: {fixed}")
        print(f"Records skipped (no valid value): {skipped}")
        print(f"Errors: {errors}")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if args.dry_run:
            print("\n*** This was a DRY RUN - no changes were made ***")
            print("Run without --dry-run to apply changes")
        elif fixed > 0:
            print(f"\n✓ Successfully backfilled {fixed} sleep records")
        
        print("=" * 80)
        
        return 0 if errors == 0 else 1
        
    except Exception as e:
        print(f"\n✗ Script failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

