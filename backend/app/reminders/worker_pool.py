"""
Custom Celery worker pool that tracks child worker PIDs
"""
import os
import signal
from celery.concurrency.prefork import TaskPool
from celery.utils.log import get_logger

logger = get_logger(__name__)

class PidTrackingTaskPool(TaskPool):
    """Custom task pool that tracks child worker PIDs"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.child_pids = set()
        self.pid_file = os.path.join(os.getcwd(), 'tmp', 'worker-child-pids.pid')
        
    def on_start(self):
        """Called when worker starts"""
        super().on_start()
        self._ensure_pid_dir()
        self._load_existing_pids()
        
    def on_stop(self):
        """Called when worker stops"""
        self._save_pids()
        super().on_stop()
        
    def _ensure_pid_dir(self):
        """Ensure PID directory exists"""
        os.makedirs(os.path.dirname(self.pid_file), exist_ok=True)
        
    def _load_existing_pids(self):
        """Load existing PIDs from file"""
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, 'r') as f:
                    self.child_pids = set(int(line.strip()) for line in f if line.strip())
                logger.info(f"Loaded {len(self.child_pids)} existing child PIDs")
            except Exception as e:
                logger.error(f"Failed to load existing PIDs: {e}")
                
    def _save_pids(self):
        """Save current PIDs to file"""
        try:
            with open(self.pid_file, 'w') as f:
                for pid in self.child_pids:
                    f.write(f"{pid}\n")
            logger.info(f"Saved {len(self.child_pids)} child PIDs to {self.pid_file}")
        except Exception as e:
            logger.error(f"Failed to save PIDs: {e}")
            
    def _add_child_pid(self, pid):
        """Add a child PID to tracking"""
        self.child_pids.add(pid)
        logger.info(f"Added child PID {pid}, total: {len(self.child_pids)}")
        
    def _remove_child_pid(self, pid):
        """Remove a child PID from tracking"""
        self.child_pids.discard(pid)
        logger.info(f"Removed child PID {pid}, total: {len(self.child_pids)}")
        
    def _kill_child_pids(self):
        """Kill all tracked child PIDs"""
        for pid in list(self.child_pids):
            try:
                os.kill(pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to child PID {pid}")
            except ProcessLookupError:
                logger.info(f"Child PID {pid} already dead")
                self._remove_child_pid(pid)
            except Exception as e:
                logger.error(f"Failed to kill child PID {pid}: {e}")
                
    def _cleanup_dead_pids(self):
        """Remove PIDs of dead processes"""
        dead_pids = []
        for pid in self.child_pids:
            try:
                os.kill(pid, 0)  # Check if process exists
            except ProcessLookupError:
                dead_pids.append(pid)
                
        for pid in dead_pids:
            self._remove_child_pid(pid)
            
    def get_child_pids(self):
        """Get current child PIDs"""
        self._cleanup_dead_pids()
        return list(self.child_pids)
