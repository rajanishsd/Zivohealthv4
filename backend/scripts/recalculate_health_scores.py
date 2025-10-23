#!/usr/bin/env python3
"""
Batch recalculate health scores for users after metrics update.

This script directly calls the HealthScoringService to recalculate scores
for users and date ranges.

Usage:
    # Recalculate all users for last 30 days
    python recalculate_health_scores.py --days 30

    # Recalculate specific user
    python recalculate_health_scores.py --user-id 1 --days 7

    # Recalculate all users with data
    python recalculate_health_scores.py --all-users --days 30
"""
import sys
import os
import argparse
from datetime import date, timedelta, datetime
from typing import List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import func, distinct
from app.models import VitalsDailyAggregate, User
from app.health_scoring.services import HealthScoringService
from app.health_scoring.models import HealthScoreResultDaily
from app.db.session import SessionLocal


def get_users_with_data(db, limit=None) -> List[int]:
    """Get list of user_ids that have vitals data."""
    query = db.query(distinct(VitalsDailyAggregate.user_id))
    
    if limit:
        query = query.limit(limit)
    
    user_ids = [u[0] for u in query.all()]
    return user_ids


def recalculate_user_scores(
    db, 
    user_id: int, 
    start_date: date, 
    end_date: date,
    force: bool = False
) -> Tuple[int, int, int]:
    """
    Recalculate health scores for a user over a date range.
    
    Returns:
        Tuple of (success_count, skipped_count, error_count)
    """
    svc = HealthScoringService(db)
    
    success = 0
    skipped = 0
    errors = 0
    
    current = start_date
    while current <= end_date:
        try:
            # Check if score already exists
            existing = db.query(HealthScoreResultDaily).filter(
                HealthScoreResultDaily.user_id == user_id,
                HealthScoreResultDaily.date == current
            ).first()
            
            if existing and not force:
                skipped += 1
                current += timedelta(days=1)
                continue
            
            # Calculate score
            result = svc.compute_daily(user_id=user_id, day=current)
            
            if result.overall_score >= 0:  # Success (even if score is 0)
                success += 1
                print(f"  ✓ {current}: Score={result.overall_score:.1f}, Confidence={result.confidence:.2f}")
            else:
                errors += 1
                print(f"  ✗ {current}: Calculation failed")
                
        except Exception as e:
            errors += 1
            print(f"  ✗ {current}: Error - {str(e)[:100]}")
        
        current += timedelta(days=1)
    
    return success, skipped, errors


def main():
    parser = argparse.ArgumentParser(
        description='Batch recalculate health scores',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Recalculate last 7 days for user 1
  python recalculate_health_scores.py --user-id 1 --days 7
  
  # Recalculate last 30 days for all users with data
  python recalculate_health_scores.py --all-users --days 30
  
  # Force recalculate (overwrite existing scores)
  python recalculate_health_scores.py --user-id 1 --days 7 --force
  
  # Recalculate specific date range
  python recalculate_health_scores.py --user-id 1 --start-date 2025-10-01 --end-date 2025-10-23
        """
    )
    
    parser.add_argument(
        '--user-id',
        type=int,
        help='User ID to recalculate (omit to use --all-users)',
        default=None
    )
    
    parser.add_argument(
        '--all-users',
        action='store_true',
        help='Recalculate for all users with vitals data'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        help='Number of days back from today to recalculate (default: 30)',
        default=30
    )
    
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date (YYYY-MM-DD) - overrides --days',
        default=None
    )
    
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date (YYYY-MM-DD) - default is today',
        default=None
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force recalculation even if scores already exist'
    )
    
    parser.add_argument(
        '--limit-users',
        type=int,
        help='Limit number of users to process (for testing)',
        default=None
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.user_id and not args.all_users:
        parser.error("Must specify either --user-id or --all-users")
    
    # Determine date range
    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    else:
        start_date = date.today() - timedelta(days=args.days)
    
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    else:
        end_date = date.today()
    
    print("=" * 80)
    print("BATCH HEALTH SCORE RECALCULATION")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Date range: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")
    print(f"Force recalculation: {args.force}")
    print("=" * 80)
    print()
    
    db = SessionLocal()
    
    try:
        # Get list of users to process
        if args.user_id:
            user_ids = [args.user_id]
            print(f"Processing single user: {args.user_id}")
        else:
            user_ids = get_users_with_data(db, limit=args.limit_users)
            print(f"Processing {len(user_ids)} users with vitals data")
            if args.limit_users:
                print(f"(Limited to {args.limit_users} users for testing)")
        
        print()
        
        # Process each user
        total_success = 0
        total_skipped = 0
        total_errors = 0
        
        for idx, user_id in enumerate(user_ids, 1):
            print(f"\n[{idx}/{len(user_ids)}] User {user_id}:")
            
            success, skipped, errors = recalculate_user_scores(
                db,
                user_id,
                start_date,
                end_date,
                force=args.force
            )
            
            total_success += success
            total_skipped += skipped
            total_errors += errors
            
            print(f"  Summary: {success} calculated, {skipped} skipped, {errors} errors")
        
        print()
        print("=" * 80)
        print("FINAL SUMMARY")
        print("=" * 80)
        print(f"Users processed: {len(user_ids)}")
        print(f"Scores calculated: {total_success}")
        print(f"Scores skipped (already exist): {total_skipped}")
        print(f"Errors: {total_errors}")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if total_errors > 0:
            print(f"\n⚠️  {total_errors} errors occurred during calculation")
        elif total_success > 0:
            print(f"\n✓ Successfully calculated {total_success} health scores")
        
        print("=" * 80)
        
        return 0 if total_errors == 0 else 1
        
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

