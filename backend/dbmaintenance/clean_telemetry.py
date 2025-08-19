#!/usr/bin/env python3
"""
Telemetry Data Cleanup Script

This script cleans up telemetry data stored in Redis.
Use with caution - this will permanently delete telemetry data.
"""

import redis
import sys
import time
from typing import List, Dict, Any

def connect_to_redis() -> redis.Redis:
    """Connect to Redis server"""
    try:
        client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        # Test connection
        client.ping()
        print("✅ Connected to Redis successfully")
        return client
    except redis.ConnectionError:
        print("❌ Failed to connect to Redis. Make sure Redis is running.")
        sys.exit(1)

def get_telemetry_stats(redis_client: redis.Redis) -> Dict[str, Any]:
    """Get statistics about telemetry data"""
    print("📊 Analyzing telemetry data...")
    
    # Get all telemetry keys
    all_keys = redis_client.keys('telemetry:*')
    
    # Categorize keys
    span_keys = [k for k in all_keys if k.startswith('telemetry:span:')]
    agent_keys = [k for k in all_keys if k.startswith('telemetry:agent:')]
    session_keys = [k for k in all_keys if k.startswith('telemetry:session:')]
    metrics_keys = [k for k in all_keys if k.startswith('telemetry:metrics:')]
    other_keys = [k for k in all_keys if not any(k.startswith(prefix) for prefix in [
        'telemetry:span:', 'telemetry:agent:', 'telemetry:session:', 'telemetry:metrics:'
    ])]
    
    stats = {
        'total_keys': len(all_keys),
        'span_keys': len(span_keys),
        'agent_keys': len(agent_keys),
        'session_keys': len(session_keys),
        'metrics_keys': len(metrics_keys),
        'other_keys': len(other_keys),
        'categories': {
            'spans': span_keys[:5],  # Show first 5 as examples
            'agents': agent_keys,
            'sessions': session_keys[:5],
            'metrics': metrics_keys,
            'other': other_keys
        }
    }
    
    return stats

def display_stats(stats: Dict[str, Any]):
    """Display telemetry statistics"""
    print(f"\n📈 Telemetry Data Summary:")
    print(f"   Total Keys: {stats['total_keys']}")
    print(f"   └── Span Data: {stats['span_keys']} keys")
    print(f"   └── Agent Data: {stats['agent_keys']} keys")
    print(f"   └── Session Data: {stats['session_keys']} keys")
    print(f"   └── Metrics Data: {stats['metrics_keys']} keys")
    print(f"   └── Other Data: {stats['other_keys']} keys")
    
    print(f"\n🔍 Sample Keys:")
    if stats['categories']['spans']:
        print(f"   Spans: {stats['categories']['spans'][:3]}...")
    if stats['categories']['agents']:
        print(f"   Agents: {stats['categories']['agents']}")
    if stats['categories']['sessions']:
        print(f"   Sessions: {stats['categories']['sessions'][:3]}...")
    if stats['categories']['metrics']:
        print(f"   Metrics: {stats['categories']['metrics']}")
    if stats['categories']['other']:
        print(f"   Other: {stats['categories']['other']}")

def cleanup_telemetry_data(redis_client: redis.Redis, categories: List[str] = None, dry_run: bool = True) -> Dict[str, int]:
    """
    Clean up telemetry data
    
    Args:
        redis_client: Redis client instance
        categories: List of categories to clean ['spans', 'agents', 'sessions', 'metrics', 'other', 'all']
        dry_run: If True, only simulate the cleanup without actually deleting
    
    Returns:
        Dictionary with cleanup results
    """
    if categories is None:
        categories = ['all']
    
    print(f"\n🧹 {'[DRY RUN] ' if dry_run else ''}Starting cleanup...")
    
    results = {
        'spans_deleted': 0,
        'agents_deleted': 0,
        'sessions_deleted': 0,
        'metrics_deleted': 0,
        'other_deleted': 0,
        'total_deleted': 0
    }
    
    all_keys = redis_client.keys('telemetry:*')
    
    # Define patterns for each category
    patterns = {
        'spans': 'telemetry:span:*',
        'agents': 'telemetry:agent:*',
        'sessions': 'telemetry:session:*',
        'metrics': 'telemetry:metrics:*',
        'other': None  # Will be handled separately
    }
    
    for category in categories:
        if category == 'all':
            # Delete all telemetry keys
            if all_keys:
                print(f"   {'[DRY RUN] ' if dry_run else ''}Deleting {len(all_keys)} telemetry keys...")
                if not dry_run:
                    deleted = redis_client.delete(*all_keys)
                    results['total_deleted'] = deleted
                else:
                    results['total_deleted'] = len(all_keys)
            break
        
        elif category in patterns and patterns[category]:
            # Delete specific category
            keys = redis_client.keys(patterns[category])
            if keys:
                print(f"   {'[DRY RUN] ' if dry_run else ''}Deleting {len(keys)} {category} keys...")
                if not dry_run:
                    deleted = redis_client.delete(*keys)
                    results[f'{category}_deleted'] = deleted
                else:
                    results[f'{category}_deleted'] = len(keys)
                results['total_deleted'] += results[f'{category}_deleted']
        
        elif category == 'other':
            # Delete keys that don't match other patterns
            other_keys = [k for k in all_keys if not any(k.startswith(prefix) for prefix in [
                'telemetry:span:', 'telemetry:agent:', 'telemetry:session:', 'telemetry:metrics:'
            ])]
            if other_keys:
                print(f"   {'[DRY RUN] ' if dry_run else ''}Deleting {len(other_keys)} other keys...")
                if not dry_run:
                    deleted = redis_client.delete(*other_keys)
                    results['other_deleted'] = deleted
                else:
                    results['other_deleted'] = len(other_keys)
                results['total_deleted'] += results['other_deleted']
    
    return results

def cleanup_old_spans_only(redis_client: redis.Redis, keep_recent_hours: int = 1, dry_run: bool = True) -> int:
    """
    Clean up only old span data, keeping recent spans
    
    Args:
        redis_client: Redis client instance
        keep_recent_hours: Number of hours of recent data to keep
        dry_run: If True, only simulate the cleanup
    
    Returns:
        Number of spans deleted
    """
    print(f"\n🕒 {'[DRY RUN] ' if dry_run else ''}Cleaning old spans (keeping last {keep_recent_hours} hours)...")
    
    import json
    from datetime import datetime, timedelta
    
    cutoff_time = datetime.now() - timedelta(hours=keep_recent_hours)
    
    # Get all span keys
    span_keys = redis_client.keys('telemetry:span:*')
    old_spans = []
    
    for span_key in span_keys:
        try:
            span_data = redis_client.get(span_key)
            if span_data:
                span = json.loads(span_data)
                span_time = datetime.fromtimestamp(span['start_time'])
                if span_time < cutoff_time:
                    old_spans.append(span_key)
        except (json.JSONDecodeError, KeyError, ValueError):
            # If we can't parse the span, consider it for deletion
            old_spans.append(span_key)
    
    if old_spans:
        print(f"   Found {len(old_spans)} old spans to delete...")
        if not dry_run:
            # Also remove from recent_spans sorted set
            for span_key in old_spans:
                span_id = span_key.replace('telemetry:span:', '')
                redis_client.zrem('telemetry:recent_spans', span_id)
            
            # Delete the span keys
            deleted = redis_client.delete(*old_spans)
            return deleted
        else:
            return len(old_spans)
    else:
        print("   No old spans found to delete.")
        return 0

def main():
    """Main function with interactive menu"""
    print("🧹 Telemetry Data Cleanup Tool")
    print("=" * 40)
    
    redis_client = connect_to_redis()
    
    while True:
        # Get current stats
        stats = get_telemetry_stats(redis_client)
        display_stats(stats)
        
        if stats['total_keys'] == 0:
            print("\n✨ No telemetry data found. Redis is clean!")
            break
        
        print(f"\n🛠️  Cleanup Options:")
        print(f"   1. Clean ALL telemetry data ({stats['total_keys']} keys)")
        print(f"   2. Clean only span data ({stats['span_keys']} keys)")
        print(f"   3. Clean only old spans (keep last 1 hour)")
        print(f"   4. Clean only old spans (keep last 6 hours)")
        print(f"   5. Clean agent data ({stats['agent_keys']} keys)")
        print(f"   6. Clean session data ({stats['session_keys']} keys)")
        print(f"   7. Clean metrics data ({stats['metrics_keys']} keys)")
        print(f"   8. Custom cleanup")
        print(f"   9. Exit")
        
        choice = input(f"\nSelect option (1-9): ").strip()
        
        if choice == '9':
            print("👋 Goodbye!")
            break
        
        # Confirm before proceeding
        if choice in ['1', '2', '3', '4', '5', '6', '7', '8']:
            dry_run = input("Run in dry-run mode first? (y/N): ").strip().lower() == 'y'
            
            if choice == '1':
                results = cleanup_telemetry_data(redis_client, ['all'], dry_run)
            elif choice == '2':
                results = cleanup_telemetry_data(redis_client, ['spans'], dry_run)
            elif choice == '3':
                deleted = cleanup_old_spans_only(redis_client, keep_recent_hours=1, dry_run=dry_run)
                results = {'total_deleted': deleted}
            elif choice == '4':
                deleted = cleanup_old_spans_only(redis_client, keep_recent_hours=6, dry_run=dry_run)
                results = {'total_deleted': deleted}
            elif choice == '5':
                results = cleanup_telemetry_data(redis_client, ['agents'], dry_run)
            elif choice == '6':
                results = cleanup_telemetry_data(redis_client, ['sessions'], dry_run)
            elif choice == '7':
                results = cleanup_telemetry_data(redis_client, ['metrics'], dry_run)
            elif choice == '8':
                print("Custom categories: spans, agents, sessions, metrics, other, all")
                categories = input("Enter categories (comma-separated): ").strip().split(',')
                categories = [c.strip() for c in categories if c.strip()]
                results = cleanup_telemetry_data(redis_client, categories, dry_run)
            
            # Display results
            print(f"\n{'🧪 DRY RUN RESULTS:' if dry_run else '✅ CLEANUP COMPLETE:'}")
            if 'total_deleted' in results:
                print(f"   Total keys {'would be' if dry_run else ''} deleted: {results['total_deleted']}")
            
            if not dry_run and results['total_deleted'] > 0:
                print("   ✨ Cleanup completed successfully!")
            elif dry_run:
                confirm = input("\nProceed with actual cleanup? (y/N): ").strip().lower()
                if confirm == 'y':
                    # Re-run without dry_run
                    if choice == '1':
                        results = cleanup_telemetry_data(redis_client, ['all'], False)
                    elif choice == '2':
                        results = cleanup_telemetry_data(redis_client, ['spans'], False)
                    elif choice == '3':
                        deleted = cleanup_old_spans_only(redis_client, keep_recent_hours=1, dry_run=False)
                        results = {'total_deleted': deleted}
                    elif choice == '4':
                        deleted = cleanup_old_spans_only(redis_client, keep_recent_hours=6, dry_run=False)
                        results = {'total_deleted': deleted}
                    elif choice == '5':
                        results = cleanup_telemetry_data(redis_client, ['agents'], False)
                    elif choice == '6':
                        results = cleanup_telemetry_data(redis_client, ['sessions'], False)
                    elif choice == '7':
                        results = cleanup_telemetry_data(redis_client, ['metrics'], False)
                    elif choice == '8':
                        results = cleanup_telemetry_data(redis_client, categories, False)
                    
                    print(f"\n✅ ACTUAL CLEANUP COMPLETE:")
                    print(f"   Total keys deleted: {results['total_deleted']}")
        else:
            print("❌ Invalid option. Please try again.")
        
        input("\nPress Enter to continue...")
        print("\n" + "=" * 50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Cleanup cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1) 