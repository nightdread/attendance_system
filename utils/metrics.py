"""
Performance metrics and monitoring utilities
"""
import time
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from functools import wraps

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from utils.cache import cache
from utils.logger import log_performance


def get_system_metrics() -> Dict[str, Any]:
    """
    Get system performance metrics
    
    Returns:
        Dictionary with system metrics
    """
    if not PSUTIL_AVAILABLE:
        return {
            "error": "psutil not installed (optional dependency)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    try:
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_free_gb = disk.free / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        
        return {
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count
            },
            "memory": {
                "percent": memory_percent,
                "available_mb": round(memory_available_mb, 2),
                "total_mb": round(memory_total_mb, 2),
                "used_mb": round((memory.total - memory.available) / (1024 * 1024), 2)
            },
            "disk": {
                "percent": disk_percent,
                "free_gb": round(disk_free_gb, 2),
                "total_gb": round(disk_total_gb, 2),
                "used_gb": round((disk.total - disk.free) / (1024 * 1024 * 1024), 2)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def get_redis_metrics() -> Dict[str, Any]:
    """
    Get Redis connection metrics
    
    Returns:
        Dictionary with Redis metrics
    """
    metrics = {
        "enabled": cache.redis_enabled,
        "connected": False,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if not cache.redis_enabled:
        return metrics
    
    try:
        if cache.redis_client:
            # Test connection
            cache.redis_client.ping()
            metrics["connected"] = True
            
            # Get Redis info (if available)
            try:
                info = cache.redis_client.info()
                metrics.update({
                    "used_memory_mb": round(info.get("used_memory", 0) / (1024 * 1024), 2),
                    "connected_clients": info.get("connected_clients", 0),
                    "total_commands_processed": info.get("total_commands_processed", 0),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                })
            except:
                pass
        else:
            metrics["error"] = "Redis client not initialized"
    except Exception as e:
        metrics["error"] = str(e)
        metrics["connected"] = False
    
    return metrics


def get_database_metrics(db) -> Dict[str, Any]:
    """
    Get database metrics
    
    Args:
        db: Database instance
    
    Returns:
        Dictionary with database metrics
    """
    metrics = {
        "status": "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        # Check database file
        db_path = Path(db.db_path)
        if db_path.exists():
            db_size_mb = db_path.stat().st_size / (1024 * 1024)
            metrics.update({
                "status": "connected",
                "path": str(db_path),
                "size_mb": round(db_size_mb, 2),
                "exists": True
            })
        else:
            metrics.update({
                "status": "file_not_found",
                "path": str(db_path),
                "exists": False
            })
        
        # Test connection
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            metrics["status"] = "healthy"
            metrics["connection_test"] = "success"
        
        # Get table counts
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                metrics["table_count"] = cursor.fetchone()[0]
        except:
            pass
            
    except Exception as e:
        metrics.update({
            "status": "error",
            "error": str(e),
            "connection_test": "failed"
        })
    
    return metrics


def performance_monitor(func):
    """
    Decorator to monitor function performance
    
    Usage:
        @performance_monitor
        def my_function():
            ...
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            log_performance(func.__name__, duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            log_performance(func.__name__, duration, f"ERROR: {str(e)}")
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            log_performance(func.__name__, duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            log_performance(func.__name__, duration, f"ERROR: {str(e)}")
            raise
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

