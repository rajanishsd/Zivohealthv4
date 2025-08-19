"""
Database Performance Monitoring

Utilities for tracking database operation performance including
query execution times, connection pool status, and operation types.
"""

import time
import logging
import hashlib
from typing import Optional, Any, Dict, List
from contextlib import asynccontextmanager
from functools import wraps
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool
from .system_metrics import system_metrics

logger = logging.getLogger(__name__)


class DatabaseMonitor:
    """Database performance monitoring utility"""
    
    def __init__(self):
        self.active_queries = {}
        self.connection_pool_stats = {}
        
    def setup_sqlalchemy_monitoring(self, engine: Engine):
        """Setup SQLAlchemy event listeners for monitoring"""
        
        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Track query start time"""
            query_id = id(cursor)
            self.active_queries[query_id] = {
                'start_time': time.time(),
                'statement': statement,
                'parameters': parameters
            }
            
        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Track query completion and record metrics"""
            query_id = id(cursor)
            
            if query_id in self.active_queries:
                query_info = self.active_queries.pop(query_id)
                duration_ms = (time.time() - query_info['start_time']) * 1000
                
                # Determine operation type
                operation_type = self._extract_operation_type(statement)
                
                # Extract table name if possible
                table_name = self._extract_table_name(statement)
                
                # Generate query hash for grouping similar queries
                query_hash = self._generate_query_hash(statement)
                
                # Get affected rows from cursor if available
                rows_affected = getattr(cursor, 'rowcount', None)
                if rows_affected == -1:  # Some drivers return -1 for SELECT
                    rows_affected = None
                    
                # Record the database metric (safely handle async in sync context)
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Schedule the coroutine to run soon, but don't wait for it
                        asyncio.create_task(system_metrics.record_database_operation(
                            operation_type=operation_type,
                            duration_ms=duration_ms,
                            table_name=table_name,
                            rows_affected=rows_affected,
                            query_hash=query_hash,
                            success=True
                        ))
                    else:
                        # No running loop, skip the metric recording
                        pass
                except Exception as e:
                    # If we can't record the metric, don't break the database operation
                    logger.debug(f"Could not record database metric: {e}")
                    pass
                
                # Log slow queries
                if duration_ms > 1000:  # Queries slower than 1 second
                    logger.warning(
                        f"Slow query detected: {operation_type} on {table_name or 'unknown'} "
                        f"took {duration_ms:.0f}ms"
                    )
                    
        @event.listens_for(engine, "handle_error")
        def handle_error(exception_context):
            """Track database errors"""
            statement = getattr(exception_context, 'statement', None)
            
            if statement:
                operation_type = self._extract_operation_type(statement)
                table_name = self._extract_table_name(statement)
                query_hash = self._generate_query_hash(statement)
                
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(system_metrics.record_database_operation(
                            operation_type=operation_type,
                            duration_ms=0,  # Error occurred before completion
                            table_name=table_name,
                            query_hash=query_hash,
                            success=False,
                            error_message=str(exception_context.original_exception)
                        ))
                except Exception as e:
                    logger.debug(f"Could not record database error metric: {e}")
                    pass
                
        @event.listens_for(Pool, "connect")
        def pool_connect(dbapi_conn, connection_record):
            """Track new connections"""
            logger.debug("New database connection established")
            
        @event.listens_for(Pool, "checkout")
        def pool_checkout(dbapi_conn, connection_record, connection_proxy):
            """Track connection checkout from pool"""
            pass
            
        @event.listens_for(Pool, "checkin")
        def pool_checkin(dbapi_conn, connection_record):
            """Track connection return to pool"""
            pass
            
        logger.info("Database monitoring events configured")
        
    def _extract_operation_type(self, statement: str) -> str:
        """Extract SQL operation type from statement"""
        if not statement:
            return "UNKNOWN"
            
        statement = statement.strip().upper()
        
        if statement.startswith("SELECT"):
            return "SELECT"
        elif statement.startswith("INSERT"):
            return "INSERT"
        elif statement.startswith("UPDATE"):
            return "UPDATE"
        elif statement.startswith("DELETE"):
            return "DELETE"
        elif statement.startswith("CREATE"):
            return "CREATE"
        elif statement.startswith("DROP"):
            return "DROP"
        elif statement.startswith("ALTER"):
            return "ALTER"
        elif statement.startswith("WITH"):
            return "CTE"  # Common Table Expression
        else:
            return "OTHER"
            
    def _extract_table_name(self, statement: str) -> Optional[str]:
        """Extract primary table name from SQL statement"""
        if not statement:
            return None
            
        try:
            statement = statement.strip().upper()
            
            # Simple regex-like extraction for common patterns
            if statement.startswith("SELECT"):
                if " FROM " in statement:
                    from_part = statement.split(" FROM ")[1]
                    table_part = from_part.split()[0]
                    return table_part.strip("\"'`").lower()
                    
            elif statement.startswith(("INSERT", "UPDATE", "DELETE")):
                if statement.startswith("INSERT INTO"):
                    table_part = statement.replace("INSERT INTO", "").strip().split()[0]
                elif statement.startswith("UPDATE"):
                    table_part = statement.replace("UPDATE", "").strip().split()[0]
                elif statement.startswith("DELETE FROM"):
                    table_part = statement.replace("DELETE FROM", "").strip().split()[0]
                else:
                    return None
                    
                return table_part.strip("\"'`").lower()
                
        except Exception as e:
            logger.debug(f"Could not extract table name from statement: {e}")
            
        return None
        
    def _generate_query_hash(self, statement: str) -> str:
        """Generate a hash for grouping similar queries"""
        if not statement:
            return ""
            
        # Normalize the statement by removing specific values
        normalized = statement.strip().upper()
        
        # Simple normalization - replace common patterns
        import re
        
        # Replace string literals
        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        
        # Replace numeric literals
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        
        # Replace IN clauses with multiple values
        normalized = re.sub(r'IN\s*\([^)]*\)', 'IN (?)', normalized)
        
        # Generate hash
        return hashlib.md5(normalized.encode()).hexdigest()[:12]
        
    def get_connection_pool_stats(self, engine: Engine) -> Dict[str, Any]:
        """Get connection pool statistics"""
        try:
            pool = engine.pool
            
            return {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid(),
                "total_connections": pool.size() + pool.overflow()
            }
            
        except Exception as e:
            logger.error(f"Error getting connection pool stats: {e}")
            return {}


@asynccontextmanager
async def track_database_operation(operation_name: str, table_name: Optional[str] = None):
    """Context manager for tracking custom database operations"""
    start_time = time.time()
    success = True
    error_message = None
    
    try:
        yield
    except Exception as e:
        success = False
        error_message = str(e)
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        
        system_metrics.record_database_operation(
            operation_type=operation_name,
            duration_ms=duration_ms,
            table_name=table_name,
            success=success,
            error_message=error_message
        )


def monitor_database_function(operation_type: str = "FUNCTION", table_name: Optional[str] = None):
    """Decorator for monitoring database function calls"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            async with track_database_operation(operation_type, table_name):
                return await func(*args, **kwargs)
                
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_message = None
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                system_metrics.record_database_operation(
                    operation_type=operation_type,
                    duration_ms=duration_ms,
                    table_name=table_name,
                    success=success,
                    error_message=error_message
                )
                
        # Return appropriate wrapper based on whether function is async
        if hasattr(func, '__code__') and 'async' in func.__code__.co_flags:
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


# Global instance
db_monitor = DatabaseMonitor() 