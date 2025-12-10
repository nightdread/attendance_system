"""
Redis caching system for the attendance application
"""
import json
import pickle
from typing import Any, Optional, Union
import redis
from config.config import (
    REDIS_ENABLED, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD,
    CACHE_TTL_TOKEN, CACHE_TTL_ANALYTICS, CACHE_TTL_USER
)
from utils.logger import logger

class Cache:
    """Redis cache wrapper with fallback to in-memory cache"""

    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}  # Fallback in-memory cache

        if REDIS_ENABLED:
            try:
                self.redis_client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=False,  # Keep as bytes for pickle
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
                # Test connection
                self.redis_client.ping()
                logger.info(f"Redis cache connected to {REDIS_HOST}:{REDIS_PORT}")
            except Exception as e:
                logger.warning(f"Redis connection failed, using memory cache: {e}")
                self.redis_client = None
        else:
            logger.info("Redis cache disabled, using memory cache")

    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage"""
        return pickle.dumps(value)

    def _deserialize(self, value: bytes) -> Any:
        """Deserialize value from storage"""
        if value is None:
            return None
        return pickle.loads(value)

    def get(self, key: str) -> Any:
        """Get value from cache"""
        try:
            if self.redis_client:
                value = self.redis_client.get(key)
                if value is not None:
                    return self._deserialize(value)
            else:
                # Memory cache fallback
                return self.memory_cache.get(key)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")

        return None

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with optional TTL"""
        try:
            serialized_value = self._serialize(value)

            if self.redis_client:
                return bool(self.redis_client.set(key, serialized_value, ex=ttl))
            else:
                # Memory cache fallback (no TTL support)
                self.memory_cache[key] = value
                return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            if self.redis_client:
                return bool(self.redis_client.delete(key))
            else:
                # Memory cache fallback
                if key in self.memory_cache:
                    del self.memory_cache[key]
                    return True
                return False
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            if self.redis_client:
                return bool(self.redis_client.exists(key))
            else:
                return key in self.memory_cache
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    def clear(self) -> bool:
        """Clear all cache"""
        try:
            if self.redis_client:
                return bool(self.redis_client.flushdb())
            else:
                self.memory_cache.clear()
                return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False

    def get_stats(self) -> dict:
        """Get cache statistics"""
        try:
            if self.redis_client:
                info = self.redis_client.info()
                return {
                    "type": "redis",
                    "connected": True,
                    "keys": self.redis_client.dbsize(),
                    "memory_used": info.get("used_memory_human", "unknown"),
                    "hit_rate": "unknown"  # Would need additional tracking
                }
            else:
                return {
                    "type": "memory",
                    "connected": True,
                    "keys": len(self.memory_cache),
                    "memory_used": "unknown",
                    "hit_rate": "unknown"
                }
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {
                "type": "error",
                "connected": False,
                "error": str(e)
            }

# Cache key prefixes
class CacheKeys:
    """Cache key constants"""
    TOKEN = "token:{}"  # token:{token_value}
    USER = "user:{}"    # user:{username}
    ANALYTICS_DAILY = "analytics:daily:{}"  # analytics:daily:{date}
    ANALYTICS_WEEKLY = "analytics:weekly"   # analytics:weekly
    ANALYTICS_LOCATION = "analytics:location:{}"  # analytics:location:{date}
    ANALYTICS_USER = "analytics:user:{}"    # analytics:user:{limit}
    ANALYTICS_HOURLY = "analytics:hourly:{}"  # analytics:hourly:{date}
    ANALYTICS_HEALTH = "analytics:health"    # analytics:health

# Global cache instance
cache = Cache()

# Convenience functions
def get_cached_token(token: str) -> Optional[dict]:
    """Get cached token data"""
    return cache.get(CacheKeys.TOKEN.format(token))

def set_cached_token(token: str, data: dict) -> bool:
    """Cache token data"""
    return cache.set(CacheKeys.TOKEN.format(token), data, CACHE_TTL_TOKEN)

def invalidate_token(token: str) -> bool:
    """Remove token from cache"""
    return cache.delete(CacheKeys.TOKEN.format(token))

def get_cached_user(username: str) -> Optional[dict]:
    """Get cached user data"""
    return cache.get(CacheKeys.USER.format(username))

def set_cached_user(username: str, user_data: dict) -> bool:
    """Cache user data"""
    return cache.set(CacheKeys.USER.format(username), user_data, CACHE_TTL_USER)

def invalidate_user(username: str) -> bool:
    """Remove user from cache"""
    return cache.delete(CacheKeys.USER.format(username))

def get_cached_analytics_daily(date: str) -> Optional[dict]:
    """Get cached daily analytics"""
    return cache.get(CacheKeys.ANALYTICS_DAILY.format(date))

def set_cached_analytics_daily(date: str, data: dict) -> bool:
    """Cache daily analytics"""
    return cache.set(CacheKeys.ANALYTICS_DAILY.format(date), data, CACHE_TTL_ANALYTICS)

def get_cached_analytics_weekly() -> Optional[dict]:
    """Get cached weekly analytics"""
    return cache.get(CacheKeys.ANALYTICS_WEEKLY)

def set_cached_analytics_weekly(data: dict) -> bool:
    """Cache weekly analytics"""
    return cache.set(CacheKeys.ANALYTICS_WEEKLY, data, CACHE_TTL_ANALYTICS)

def get_cached_analytics_location(date: str = None) -> Optional[list]:
    """Get cached location analytics"""
    key = CacheKeys.ANALYTICS_LOCATION.format(date or "all")
    return cache.get(key)

def set_cached_analytics_location(data: list, date: str = None) -> bool:
    """Cache location analytics"""
    key = CacheKeys.ANALYTICS_LOCATION.format(date or "all")
    return cache.set(key, data, CACHE_TTL_ANALYTICS)

def get_cached_analytics_users(limit: int = 10) -> Optional[list]:
    """Get cached user analytics"""
    return cache.get(CacheKeys.ANALYTICS_USER.format(limit))

def set_cached_analytics_users(data: list, limit: int = 10) -> bool:
    """Cache user analytics"""
    return cache.set(CacheKeys.ANALYTICS_USER.format(limit), data, CACHE_TTL_ANALYTICS)

def get_cached_analytics_hourly(date: str) -> Optional[list]:
    """Get cached hourly analytics"""
    return cache.get(CacheKeys.ANALYTICS_HOURLY.format(date))

def set_cached_analytics_hourly(date: str, data: list) -> bool:
    """Cache hourly analytics"""
    return cache.set(CacheKeys.ANALYTICS_HOURLY.format(date), data, CACHE_TTL_ANALYTICS)

def get_cached_system_health() -> Optional[dict]:
    """Get cached system health"""
    return cache.get(CacheKeys.ANALYTICS_HEALTH)

def set_cached_system_health(data: dict) -> bool:
    """Cache system health"""
    return cache.set(CacheKeys.ANALYTICS_HEALTH, data, CACHE_TTL_ANALYTICS)
