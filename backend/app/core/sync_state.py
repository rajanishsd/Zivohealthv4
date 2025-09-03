"""
Sync State Manager - Controls when aggregation workers should start
"""
import asyncio
import logging
from typing import Dict, Set
from datetime import datetime, timedelta
from app.utils.timezone import now_local

logger = logging.getLogger(__name__)

class SyncStateManager:
    """Manages sync operations and aggregation worker lifecycle"""
    
    def __init__(self):
        self.active_sync_operations: Dict[int, Set[str]] = {}  # user_id -> set of operation_ids
        self.last_sync_activity: Dict[int, datetime] = {}  # user_id -> last activity timestamp
        self.worker_started = False
        self.worker_task = None
        self.sync_cooldown_seconds = 60  # Wait 60 seconds after last sync before starting worker
        
    def start_sync_operation(self, user_id: int, operation_id: str):
        """Register the start of a sync operation"""
        if user_id not in self.active_sync_operations:
            self.active_sync_operations[user_id] = set()
        
        self.active_sync_operations[user_id].add(operation_id)
        self.last_sync_activity[user_id] = now_local()
        
        logger.info(f"🔄 [SyncState] Started sync operation {operation_id} for user {user_id}")
        logger.info(f"🔄 [SyncState] Active operations for user {user_id}: {len(self.active_sync_operations[user_id])}")
    
    def end_sync_operation(self, user_id: int, operation_id: str):
        """Register the end of a sync operation"""
        if user_id in self.active_sync_operations:
            self.active_sync_operations[user_id].discard(operation_id)
            self.last_sync_activity[user_id] = now_local()
            
            # Clean up empty sets
            if not self.active_sync_operations[user_id]:
                del self.active_sync_operations[user_id]
        
        logger.info(f"✅ [SyncState] Ended sync operation {operation_id} for user {user_id}")
        remaining_ops = len(self.active_sync_operations.get(user_id, set()))
        logger.info(f"🔄 [SyncState] Remaining operations for user {user_id}: {remaining_ops}")
        
        # Check if we should start the aggregation worker
        self._check_and_start_worker()
    
    def has_active_sync_operations(self) -> bool:
        """Check if there are any active sync operations"""
        return bool(self.active_sync_operations)
    
    def get_time_since_last_activity(self) -> float:
        """Get seconds since last sync activity across all users"""
        if not self.last_sync_activity:
            return float('inf')
        
        latest_activity = max(self.last_sync_activity.values())
        return (now_local() - latest_activity).total_seconds()
    
    def should_start_worker(self) -> bool:
        """Determine if the aggregation worker should be started"""
        # Don't start if already running
        if self.worker_started:
            return False
        
        # Don't start if there are active sync operations
        if self.has_active_sync_operations():
            return False
        
        # Don't start if recent sync activity (within cooldown period)
        if self.get_time_since_last_activity() < self.sync_cooldown_seconds:
            return False
        
        return True
    
    async def start_aggregation_worker(self):
        """Start the aggregation worker if conditions are met"""
        if not self.should_start_worker():
            logger.info("🔄 [SyncState] Conditions not met for starting aggregation worker")
            return False
        
        try:
            from app.core.background_worker import get_worker
            
            worker = get_worker()
            self.worker_task = asyncio.create_task(worker.start())
            self.worker_started = True
            
            logger.info("🚀 [SyncState] Background aggregation worker started after data push completion")
            return True
            
        except Exception as e:
            logger.error(f"❌ [SyncState] Failed to start aggregation worker: {e}")
            return False
    
    async def stop_aggregation_worker(self):
        """Stop the aggregation worker"""
        if self.worker_task and self.worker_started:
            try:
                from app.core.background_worker import stop_background_worker
                
                stop_background_worker()
                self.worker_task.cancel()
                
                try:
                    await self.worker_task
                except asyncio.CancelledError:
                    pass
                
                self.worker_started = False
                self.worker_task = None
                
                logger.info("🛑 [SyncState] Background aggregation worker stopped")
                
            except Exception as e:
                logger.error(f"❌ [SyncState] Error stopping aggregation worker: {e}")
    
    def _check_and_start_worker(self):
        """Check conditions and start worker if appropriate"""
        if self.should_start_worker():
            # Schedule worker start in background
            asyncio.create_task(self.start_aggregation_worker())
    
    def get_status(self) -> dict:
        """Get current sync state status"""
        return {
            "active_sync_operations": {
                user_id: list(ops) for user_id, ops in self.active_sync_operations.items()
            },
            "total_active_operations": sum(len(ops) for ops in self.active_sync_operations.values()),
            "worker_started": self.worker_started,
            "time_since_last_activity": self.get_time_since_last_activity(),
            "should_start_worker": self.should_start_worker()
        }

# Global sync state manager instance
sync_state_manager = SyncStateManager()
