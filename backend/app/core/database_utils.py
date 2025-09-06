"""
Database utility functions for consistent connection management across the application.

This module provides centralized database connection management to prevent connection leaks
and ensure proper resource cleanup.
"""

import logging
from contextlib import contextmanager
from typing import Generator, Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.core.config import settings

logger = logging.getLogger(__name__)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Get a database session with proper cleanup using context manager.
    
    This is the preferred way to get database sessions throughout the application.
    Automatically handles connection cleanup and rollback on exceptions.
    
    Usage:
        with get_db_session() as db:
            # Your database operations here
            result = db.query(Model).all()
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Commit successful operations
    except Exception as e:
        db.rollback()  # Rollback on any exception
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()  # Always close the session


@contextmanager
def get_raw_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Get a raw psycopg2 connection with proper cleanup using context manager.
    
    This should be used sparingly - prefer get_db_session() for most operations.
    Only use this when you need raw SQL access or specific psycopg2 features.
    
    Usage:
        with get_raw_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM table")
                results = cursor.fetchall()
    
    Yields:
        psycopg2.connection: Raw database connection
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD or ""
        )
        yield conn
        conn.commit()  # Commit successful operations
    except Exception as e:
        if conn:
            conn.rollback()  # Rollback on any exception
        logger.error(f"Raw database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()  # Always close the connection


def execute_query_safely(query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """
    Execute a SQL query safely with proper connection management.
    
    This is a convenience function for simple queries that returns results as dictionaries.
    Handles all connection management automatically.
    
    Args:
        query: SQL query string
        params: Optional query parameters tuple
        
    Returns:
        List of dictionaries representing query results
        
    Raises:
        Exception: If query execution fails
    """
    try:
        with get_raw_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                results = cursor.fetchall()
                return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"Query execution failed: {query[:100]}... Error: {e}")
        raise


def execute_query_safely_json(query: str, params: Optional[tuple] = None) -> str:
    """
    Execute a SQL query safely and return results as JSON string.
    
    This is specifically for agent tools that need JSON responses.
    Handles all connection management automatically.
    
    Args:
        query: SQL query string
        params: Optional query parameters tuple
        
    Returns:
        JSON string representation of query results
        
    Raises:
        Exception: If query execution fails
    """
    try:
        results = execute_query_safely(query, params)
        return json.dumps(results, default=str)
    except Exception as e:
        logger.error(f"Query JSON execution failed: {query[:100]}... Error: {e}")
        return f"Query Error: {e}"


def get_table_schema_safely(table_name: str) -> str:
    """
    Get table schema information safely with proper connection management.
    
    Args:
        table_name: Name of the table to inspect
        
    Returns:
        String description of table schema or error message
    """
    try:
        query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position;
        """
        
        results = execute_query_safely(query, (table_name,))
        
        if not results:
            return f"Table '{table_name}' not found or has no accessible columns"
            
        schema_info = f"Schema for table '{table_name}':\n"
        for row in results:
            nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
            default = f" DEFAULT {row['column_default']}" if row['column_default'] else ""
            schema_info += f"- {row['column_name']}: {row['data_type']} {nullable}{default}\n"
            
        return schema_info.strip()
        
    except Exception as e:
        logger.error(f"Schema lookup failed for table {table_name}: {e}")
        return f"Schema Error: {e}"


def check_connection_pool_stats() -> Dict[str, Any]:
    """
    Get current connection pool statistics for monitoring.
    
    Returns:
        Dictionary with connection pool statistics
    """
    try:
        pool = engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
            "total_connections": pool.size() + pool.overflow(),
            "status": "healthy" if pool.checkedout() < pool.size() + pool.overflow() else "exhausted"
        }
    except Exception as e:
        logger.error(f"Error getting connection pool stats: {e}")
        return {"error": str(e), "status": "unknown"}


def log_connection_pool_status():
    """
    Log current connection pool status for debugging.
    """
    stats = check_connection_pool_stats()
    if stats.get("status") == "exhausted":
        logger.warning(f"Connection pool exhausted: {stats}")
    else:
        logger.info(f"Connection pool status: {stats}")


# Deprecated functions - use the context managers above instead
def get_postgres_connection():
    """
    DEPRECATED: Use get_raw_db_connection() context manager instead.
    
    This function is kept for backward compatibility but should not be used
    in new code as it doesn't provide automatic cleanup.
    """
    logger.warning("get_postgres_connection() is deprecated. Use get_raw_db_connection() context manager instead.")
    return psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD or ""
    )
