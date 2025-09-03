#!/usr/bin/env python3
"""
Enhanced Smart Delayed Aggregation Monitor
Shows detailed status of the chunk-aware aggregation system
"""

import os
import sys
import asyncio
import time
import json
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

# Add the backend directory to Python path for imports
backend_dir = os.path.dirname(os.path.abspath(__file__))
backend_parent = os.path.dirname(backend_dir)  # This is the backend directory
sys.path.insert(0, backend_parent)

# Load environment variables from .env file before importing app modules
env_file = os.path.join(backend_parent, '.env')  # backend/.env
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"✅ Loaded environment from {env_file}")
else:
    print(f"⚠️  No .env file found at {env_file}")

# Now import app modules after environment is loaded
try:
    from app.db.session import SessionLocal
    from app.crud.vitals import VitalsCRUD
    from app.crud.nutrition import nutrition_data as NutritionCRUD
    from app.core.sync_state import sync_state_manager
    from app.utils.timezone import now_local, isoformat_now
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Make sure you're running this from the zivohealth directory:")
    print("   cd /path/to/zivohealth")
    print("   python backend/aggregation/smart_aggregation_monitor.py")
    sys.exit(1)

class AggregationStatusMonitor:
    """Enhanced monitor for aggregation status with detailed reporting"""
    
    def __init__(self):
        self.start_time = None
        self.last_status = {}
        self.metrics_history = []
        
    async def get_detailed_status(self) -> Dict[str, Any]:
        """Get comprehensive status information"""
        db = SessionLocal()
        try:
            # Get vitals aggregation status breakdown
            from sqlalchemy import text
            vitals_status_result = db.execute(text(
                'SELECT aggregation_status, COUNT(*) as count FROM vitals_raw_data GROUP BY aggregation_status'
            )).fetchall()
            vitals_status_counts = {status: count for status, count in vitals_status_result}
            
            # Get nutrition aggregation status breakdown
            nutrition_status_result = db.execute(text(
                'SELECT aggregation_status, COUNT(*) as count FROM nutrition_raw_data GROUP BY aggregation_status'
            )).fetchall()
            nutrition_status_counts = {status: count for status, count in nutrition_status_result}
            
            # Get chunk session information (recent submissions) for vitals
            vitals_chunk_result = db.execute(text("""
                SELECT 
                    DATE_TRUNC('minute', created_at) as minute_group,
                    COUNT(*) as submissions,
                    COUNT(DISTINCT user_id) as unique_users,
                    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_processing_time
                FROM vitals_raw_data 
                WHERE created_at >= NOW() - INTERVAL '30 minutes'
                GROUP BY DATE_TRUNC('minute', created_at)
                ORDER BY minute_group DESC
                LIMIT 10
            """)).fetchall()
            
            # Get chunk session information (recent submissions) for nutrition
            nutrition_chunk_result = db.execute(text("""
                SELECT 
                    DATE_TRUNC('minute', created_at) as minute_group,
                    COUNT(*) as submissions,
                    COUNT(DISTINCT user_id) as unique_users,
                    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_processing_time
                FROM nutrition_raw_data 
                WHERE created_at >= NOW() - INTERVAL '30 minutes'
                GROUP BY DATE_TRUNC('minute', created_at)
                ORDER BY minute_group DESC
                LIMIT 10
            """)).fetchall()
            
            # Get user-specific aggregation progress for vitals
            vitals_user_progress_result = db.execute(text("""
                SELECT 
                    user_id,
                    aggregation_status,
                    COUNT(*) as count,
                    MIN(created_at) as oldest_entry,
                    MAX(created_at) as newest_entry
                FROM vitals_raw_data 
                WHERE aggregation_status IN ('pending', 'processing', 'queued', 'failed')
                GROUP BY user_id, aggregation_status
                ORDER BY user_id, aggregation_status
            """)).fetchall()
            
            # Get user-specific aggregation progress for nutrition
            nutrition_user_progress_result = db.execute(text("""
                SELECT 
                    user_id,
                    aggregation_status,
                    COUNT(*) as count,
                    MIN(created_at) as oldest_entry,
                    MAX(created_at) as newest_entry
                FROM nutrition_raw_data 
                WHERE aggregation_status IN ('pending', 'processing', 'queued', 'failed')
                GROUP BY user_id, aggregation_status
                ORDER BY user_id, aggregation_status
            """)).fetchall()
            
            # Get sync operations status
            sync_status = sync_state_manager.get_status()
            
            return {
                'timestamp': isoformat_now(),
                'vitals_aggregation_queue': vitals_status_counts,
                'nutrition_aggregation_queue': nutrition_status_counts,
                'vitals_recent_activity': [
                    {
                        'minute': str(row.minute_group),
                        'submissions': row.submissions,
                        'unique_users': row.unique_users,
                        'avg_processing_time': float(row.avg_processing_time or 0)
                    }
                    for row in vitals_chunk_result
                ],
                'nutrition_recent_activity': [
                    {
                        'minute': str(row.minute_group),
                        'submissions': row.submissions,
                        'unique_users': row.unique_users,
                        'avg_processing_time': float(row.avg_processing_time or 0)
                    }
                    for row in nutrition_chunk_result
                ],
                'vitals_user_progress': [
                    {
                        'user_id': row.user_id,
                        'status': row.aggregation_status,
                        'count': row.count,
                        'oldest_entry': row.oldest_entry.isoformat() if row.oldest_entry else None,
                        'newest_entry': row.newest_entry.isoformat() if row.newest_entry else None
                    }
                    for row in vitals_user_progress_result
                ],
                'nutrition_user_progress': [
                    {
                        'user_id': row.user_id,
                        'status': row.aggregation_status,
                        'count': row.count,
                        'oldest_entry': row.oldest_entry.isoformat() if row.oldest_entry else None,
                        'newest_entry': row.newest_entry.isoformat() if row.newest_entry else None
                    }
                    for row in nutrition_user_progress_result
                ],
                'sync_operations': sync_status,
                'vitals_total_pending': sum(vitals_status_counts.get(status, 0) for status in ['pending', 'queued', 'failed']),
                'vitals_total_active': vitals_status_counts.get('processing', 0),
                'vitals_total_completed': vitals_status_counts.get('completed', 0),
                'nutrition_total_pending': sum(nutrition_status_counts.get(status, 0) for status in ['pending', 'queued', 'failed']),
                'nutrition_total_active': nutrition_status_counts.get('processing', 0),
                'nutrition_total_completed': nutrition_status_counts.get('completed', 0)
            }
        finally:
            db.close()
            
    def calculate_metrics(self, current_status: Dict[str, Any], previous_status: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate performance metrics"""
        # Vitals metrics
        vitals_total_records = sum(current_status['vitals_aggregation_queue'].values())
        vitals_completed = current_status['vitals_total_completed']
        vitals_pending = current_status['vitals_total_pending']
        
        # Nutrition metrics
        nutrition_total_records = sum(current_status['nutrition_aggregation_queue'].values())
        nutrition_completed = current_status['nutrition_total_completed']
        nutrition_pending = current_status['nutrition_total_pending']
        
        # Combined metrics
        total_records = vitals_total_records + nutrition_total_records
        total_completed = vitals_completed + nutrition_completed
        total_pending = vitals_pending + nutrition_pending
        
        metrics = {
            'vitals_total_records': vitals_total_records,
            'vitals_completion_percentage': (vitals_completed / vitals_total_records * 100) if vitals_total_records > 0 else 0,
            'vitals_throughput_per_minute': 0,
            'nutrition_total_records': nutrition_total_records,
            'nutrition_completion_percentage': (nutrition_completed / nutrition_total_records * 100) if nutrition_total_records > 0 else 0,
            'nutrition_throughput_per_minute': 0,
            'total_records': total_records,
            'total_completion_percentage': (total_completed / total_records * 100) if total_records > 0 else 0,
            'total_throughput_per_minute': 0,
            'estimated_completion_time': None
        }
            
        # Calculate throughput if we have previous data
        if previous_status and self.start_time:
            time_diff = (datetime.fromisoformat(current_status['timestamp']) - 
                        datetime.fromisoformat(previous_status['timestamp'])).total_seconds() / 60
            
            if time_diff > 0:
                # Vitals throughput
                vitals_completed_diff = current_status['vitals_total_completed'] - previous_status['vitals_total_completed']
                metrics['vitals_throughput_per_minute'] = vitals_completed_diff / time_diff
                
                # Nutrition throughput
                nutrition_completed_diff = current_status['nutrition_total_completed'] - previous_status['nutrition_total_completed']
                metrics['nutrition_throughput_per_minute'] = nutrition_completed_diff / time_diff
                
                # Total throughput
                total_completed_diff = vitals_completed_diff + nutrition_completed_diff
                metrics['total_throughput_per_minute'] = total_completed_diff / time_diff
                
                # Estimate completion time
                if metrics['total_throughput_per_minute'] > 0 and total_pending > 0:
                    minutes_remaining = total_pending / metrics['total_throughput_per_minute']
                    metrics['estimated_completion_time'] = f"{minutes_remaining:.1f} minutes"
        
        return metrics
        
    def print_status_header(self):
        """Print monitor header"""
        print("\n🧠 Enhanced Smart Aggregation Monitor")
        print("=" * 60)
        print(f"⏰ Started at: {now_local().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
    def print_chunk_tracking_info(self):
        """Print information about the new chunk tracking feature"""
        print("🆕 Chunk Tracking Feature Active:")
        print("   📦 Multi-chunk submissions tracked by session ID")
        print("   ⏳ Aggregation deferred until final chunk received")
        print("   🎯 Only final chunks trigger aggregation processing")
        print("   📊 Enhanced logging shows chunk progress (1/3, 2/3, 3/3)")
        print()
        
    def print_detailed_status(self, status: Dict[str, Any], metrics: Dict[str, Any]):
        """Print comprehensive status information"""
        timestamp = datetime.fromisoformat(status['timestamp'])
        elapsed = (timestamp - self.start_time).total_seconds() if self.start_time else 0
        
        print(f"📊 Status Update [{elapsed:.0f}s elapsed]")
        print(f"   🕒 {timestamp.strftime('%H:%M:%S')}")
        print()
        
        # Vitals Aggregation Queue Status
        vitals_queue = status['vitals_aggregation_queue']
        print("🩺 Vitals Aggregation Queue:")
        print(f"   ⏳ Pending: {vitals_queue.get('pending', 0):,}")
        print(f"   🔄 Processing: {vitals_queue.get('processing', 0):,}")
        print(f"   ⏸️  Queued: {vitals_queue.get('queued', 0):,}")
        print(f"   ✅ Completed: {vitals_queue.get('completed', 0):,}")
        if vitals_queue.get('failed', 0) > 0:
            print(f"   ❌ Failed: {vitals_queue.get('failed', 0):,}")
        print()
        
        # Nutrition Aggregation Queue Status
        nutrition_queue = status['nutrition_aggregation_queue']
        print("🍎 Nutrition Aggregation Queue:")
        print(f"   ⏳ Pending: {nutrition_queue.get('pending', 0):,}")
        print(f"   🔄 Processing: {nutrition_queue.get('processing', 0):,}")
        print(f"   ⏸️  Queued: {nutrition_queue.get('queued', 0):,}")
        print(f"   ✅ Completed: {nutrition_queue.get('completed', 0):,}")
        if nutrition_queue.get('failed', 0) > 0:
            print(f"   ❌ Failed: {nutrition_queue.get('failed', 0):,}")
        print()
        
        # Performance Metrics
        print("📈 Performance Metrics:")
        print(f"   📊 Total Records: {metrics['total_records']:,}")
        print(f"   🎯 Overall Completion: {metrics['total_completion_percentage']:.1f}%")
        print(f"   ⚡ Overall Throughput: {metrics['total_throughput_per_minute']:.1f} records/min")
        print(f"   🩺 Vitals: {metrics['vitals_completion_percentage']:.1f}% ({metrics['vitals_throughput_per_minute']:.1f}/min)")
        print(f"   🍎 Nutrition: {metrics['nutrition_completion_percentage']:.1f}% ({metrics['nutrition_throughput_per_minute']:.1f}/min)")
        if metrics['estimated_completion_time']:
            print(f"   ⏰ ETA: {metrics['estimated_completion_time']}")
        print()
        
        # Sync Operations Status
        sync_ops = status['sync_operations']
        print("🔄 Sync Operations:")
        print(f"   🔧 Active Operations: {sync_ops['total_active_operations']}")
        print(f"   ⚙️  Worker Running: {'Yes' if sync_ops['worker_started'] else 'No'}")
        print(f"   🕐 Last Activity: {sync_ops['time_since_last_activity']:.1f}s ago")
        print(f"   🎯 Should Start Worker: {'Yes' if sync_ops['should_start_worker'] else 'No'}")
        
        if sync_ops['active_sync_operations']:
            print("   📝 Active Sessions:")
            for user_id, operations in sync_ops['active_sync_operations'].items():
                print(f"      👤 User {user_id}: {len(operations)} operations")
        print()
        
        # Recent Activity - Vitals
        if status['vitals_recent_activity']:
            print("📊 Vitals Recent Activity (last 30 minutes):")
            for activity in status['vitals_recent_activity'][:5]:  # Show last 5 minutes
                minute = datetime.fromisoformat(activity['minute']).strftime('%H:%M')
                print(f"   {minute}: {activity['submissions']:,} submissions, "
                      f"{activity['unique_users']} users, "
                      f"{activity['avg_processing_time']:.2f}s avg")
            print()
        
        # Recent Activity - Nutrition
        if status['nutrition_recent_activity']:
            print("📊 Nutrition Recent Activity (last 30 minutes):")
            for activity in status['nutrition_recent_activity'][:5]:  # Show last 5 minutes
                minute = datetime.fromisoformat(activity['minute']).strftime('%H:%M')
                print(f"   {minute}: {activity['submissions']:,} submissions, "
                      f"{activity['unique_users']} users, "
                      f"{activity['avg_processing_time']:.2f}s avg")
            print()
        
        # User Progress - Vitals (if there are pending items)
        if status['vitals_user_progress']:
            print("👥 Vitals User Progress:")
            user_summary = {}
            for progress in status['vitals_user_progress']:
                user_id = progress['user_id']
                if user_id not in user_summary:
                    user_summary[user_id] = {'pending': 0, 'processing': 0, 'failed': 0}
                user_summary[user_id][progress['status']] = progress['count']
            
            for user_id, summary in user_summary.items():
                total_user_pending = summary['pending'] + summary['processing'] + summary['failed']
                print(f"   👤 User {user_id}: {total_user_pending:,} pending "
                      f"(⏳{summary['pending']} 🔄{summary['processing']} ❌{summary['failed']})")
            print()
        
        # User Progress - Nutrition (if there are pending items)
        if status['nutrition_user_progress']:
            print("👥 Nutrition User Progress:")
            user_summary = {}
            for progress in status['nutrition_user_progress']:
                user_id = progress['user_id']
                if user_id not in user_summary:
                    user_summary[user_id] = {'pending': 0, 'processing': 0, 'failed': 0}
                user_summary[user_id][progress['status']] = progress['count']
            
            for user_id, summary in user_summary.items():
                total_user_pending = summary['pending'] + summary['processing'] + summary['failed']
                print(f"   👤 User {user_id}: {total_user_pending:,} pending "
                      f"(⏳{summary['pending']} 🔄{summary['processing']} ❌{summary['failed']})")
            print()

async def monitor_smart_aggregation():
    """Enhanced monitoring with detailed status updates"""
    monitor = AggregationStatusMonitor()
    monitor.start_time = now_local()
    
    monitor.print_status_header()
    monitor.print_chunk_tracking_info()
    
    # Get initial status
    initial_status = await monitor.get_detailed_status()
    initial_metrics = monitor.calculate_metrics(initial_status)
    
    # Calculate total pending from both vitals and nutrition
    total_pending = initial_status['vitals_total_pending'] + initial_status['nutrition_total_pending']
    
    if total_pending == 0:
        print("✅ No pending data - system is idle")
        print()
        print("💡 How Enhanced Smart Aggregation Works:")
        print("   1. iOS app submits data in chunks with session tracking")
        print("   2. Backend receives chunks: 1/3, 2/3, 3/3 (final)")
        print("   3. Aggregation only triggered on final chunk")
        print("   4. Smart delay timer starts (15s incremental, 60s bulk)")
        print("   5. If more chunks arrive → Timer resets")
        print("   6. When timer expires → Process all pending data")
        print("   7. System returns to idle state")
        print()
        print("🎯 Enhanced Benefits:")
        print("   ✅ No premature aggregation on partial data")
        print("   ✅ Chunk-aware processing with session tracking")
        print("   ✅ Detailed progress monitoring and metrics")
        print("   ✅ User-specific progress tracking")
        print("   ✅ Separate vitals and nutrition processing")
        return
        
    # Monitor only - do not trigger aggregation
    print(f"📊 Found {total_pending:,} pending entries - monitoring only...")
    print(f"   🩺 Vitals: {initial_status['vitals_total_pending']:,} pending")
    print(f"   🍎 Nutrition: {initial_status['nutrition_total_pending']:,} pending")
    print("ℹ️  Note: This monitor only observes - aggregation is triggered by API endpoints")
    print("⏰ Monitoring aggregation progress...")
    print()
    
    monitor.print_detailed_status(initial_status, initial_metrics)
    monitor.last_status = initial_status
    
    # Monitor until completion
    check_count = 0
    while True:
        await asyncio.sleep(15)  # Check every 15 seconds
        check_count += 1
        
        current_status = await monitor.get_detailed_status()
        current_metrics = monitor.calculate_metrics(current_status, monitor.last_status)
        
        # Show status update
        monitor.print_detailed_status(current_status, current_metrics)
        
        # Check for completion
        current_total_pending = current_status['vitals_total_pending'] + current_status['nutrition_total_pending']
        current_total_active = current_status['vitals_total_active'] + current_status['nutrition_total_active']
        
        if current_total_pending == 0 and current_total_active == 0:
            elapsed = (now_local() - monitor.start_time).total_seconds()
            total_completed = current_status['vitals_total_completed'] + current_status['nutrition_total_completed']
            print(f"🎉 Aggregation completed in {elapsed:.1f} seconds!")
            print(f"✅ Final status: {total_completed:,} entries processed")
            print(f"   🩺 Vitals: {current_status['vitals_total_completed']:,} completed")
            print(f"   🍎 Nutrition: {current_status['nutrition_total_completed']:,} completed")
            break
        
        # Check if we're stuck (no progress for 10 checks = 2.5 minutes)
        if check_count > 10:
            if (current_status == monitor.last_status and 
                current_total_pending > 0 and current_total_active == 0):
                print("⚠️  Warning: No progress detected for 2.5 minutes")
                print("💡 You may need to trigger aggregation manually or check worker status")
                break
        
        monitor.last_status = current_status
        monitor.metrics_history.append(current_metrics)

if __name__ == "__main__":
    asyncio.run(monitor_smart_aggregation()) 