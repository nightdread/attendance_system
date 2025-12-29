"""
Rate limiting utilities for API endpoints
"""
import time
from typing import Optional
from fastapi import Request, HTTPException
from starlette.responses import Response
from utils.cache import cache
from utils.logger import log_error


def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    if request.client:
        return request.client.host
    # Try to get from X-Forwarded-For header (for reverse proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return "unknown"


def rate_limit(
    request: Request,
    max_requests: int = 10,
    window_seconds: int = 60,
    block_seconds: int = 300,
    key_prefix: str = "rate_limit"
) -> Optional[Response]:
    """
    Rate limiting decorator/function
    
    Args:
        request: FastAPI request object
        max_requests: Maximum number of requests allowed
        window_seconds: Time window in seconds
        block_seconds: Block duration in seconds after exceeding limit
        key_prefix: Prefix for Redis keys
    
    Returns:
        HTTPException response if rate limit exceeded, None otherwise
    """
    client_ip = get_client_ip(request)
    now = time.time()
    
    # Redis-based limiter (fallback to memory)
    try:
        if cache.redis_client:
            key_block = f"{key_prefix}:block:{client_ip}"
            key_counter = f"{key_prefix}:count:{client_ip}"
            
            # Check if blocked
            if cache.redis_client.exists(key_block):
                raise HTTPException(
                    status_code=429,
                    detail=f"Слишком много запросов. Попробуйте позже (блокировка на {block_seconds} секунд)."
                )
            
            # Increment counter
            count = cache.redis_client.incr(key_counter)
            if count == 1:
                cache.redis_client.expire(key_counter, window_seconds)
            
            # Check if limit exceeded
            if count > max_requests:
                cache.redis_client.set(key_block, 1, ex=block_seconds)
                # Log rate limit exceeded
                try:
                    from utils.logger import log_rate_limit_exceeded
                    log_rate_limit_exceeded(key_prefix, client_ip, attempts=count)
                except:
                    pass  # Don't fail if logging fails
                raise HTTPException(
                    status_code=429,
                    detail=f"Превышен лимит запросов ({max_requests} за {window_seconds} секунд). Блокировка на {block_seconds} секунд."
                )
    except HTTPException:
        raise
    except Exception as e:
        # Log error but don't block request (fail-open)
        log_error(e, f"Rate limiting ({key_prefix})")
    
    return None


# Pre-configured rate limiters for common use cases
def rate_limit_api(max_requests: int = 100, window_seconds: int = 60):
    """Rate limiter for API endpoints"""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            rate_limit(request, max_requests=max_requests, window_seconds=window_seconds, key_prefix="api")
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def rate_limit_token_creation(max_requests: int = 5, window_seconds: int = 300):
    """Rate limiter for token creation endpoints"""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            rate_limit(request, max_requests=max_requests, window_seconds=window_seconds, key_prefix="token_creation")
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def rate_limit_user_management(max_requests: int = 20, window_seconds: int = 60):
    """Rate limiter for user management endpoints"""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            rate_limit(request, max_requests=max_requests, window_seconds=window_seconds, key_prefix="user_mgmt")
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

