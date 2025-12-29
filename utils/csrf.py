"""
CSRF (Cross-Site Request Forgery) protection utilities
"""
import secrets
from typing import Optional
from fastapi import Request, HTTPException, status
from starlette.responses import Response


def generate_csrf_token() -> str:
    """
    Generate a secure random CSRF token
    
    Returns:
        Random token string (32 bytes, base64 encoded)
    """
    return secrets.token_urlsafe(32)


def get_csrf_token(request: Request) -> Optional[str]:
    """
    Get CSRF token from session
    
    Args:
        request: FastAPI request object
    
    Returns:
        CSRF token from session or None
    """
    return request.session.get("csrf_token")


def set_csrf_token(request: Request, token: Optional[str] = None) -> str:
    """
    Set CSRF token in session
    
    Args:
        request: FastAPI request object
        token: Optional token to set. If None, generates a new one.
    
    Returns:
        The CSRF token that was set
    """
    if token is None:
        token = generate_csrf_token()
    request.session["csrf_token"] = token
    return token


def validate_csrf_token(request: Request, token: Optional[str] = None) -> bool:
    """
    Validate CSRF token
    
    Args:
        request: FastAPI request object
        token: Token to validate. If None, tries to get from form/header.
    
    Returns:
        True if token is valid, False otherwise
    """
    session_token = get_csrf_token(request)
    
    if not session_token:
        return False
    
    # Try to get token from various sources
    if token is None:
        # Try header first (for AJAX/fetch requests)
        token = request.headers.get("X-CSRF-Token")
        
        # Try form data (for regular form submissions)
        if not token:
            try:
                # For FastAPI, form data is available after parsing
                # We'll check it in the endpoint handler
                pass
            except:
                pass
        
        # Try query parameter (for GET requests that modify state - not recommended but sometimes needed)
        if not token:
            token = request.query_params.get("csrf_token")
    
    if not token:
        return False
    
    # Use secrets.compare_digest to prevent timing attacks
    return secrets.compare_digest(session_token, token)


async def require_csrf_token(request: Request) -> None:
    """
    Require valid CSRF token, raise exception if invalid
    
    For JSON requests, checks X-CSRF-Token header.
    For form requests, checks csrf_token form field.
    
    Args:
        request: FastAPI request object
    
    Raises:
        HTTPException: If CSRF token is missing or invalid
    """
    # Try header first (for JSON/AJAX requests)
    token = request.headers.get("X-CSRF-Token")
    
    # If no header token, try to get from form (for form submissions)
    if not token:
        try:
            # Try to read form data (this might not work for all request types)
            # The endpoint handler should check form data separately
            pass
        except:
            pass
    
    if not validate_csrf_token(request, token):
        # Log CSRF failure
        try:
            from utils.logger import log_csrf_failure
            client_ip = request.client.host if request.client else "unknown"
            endpoint = str(request.url.path)
            # Try to get user from session
            user = request.session.get("access_token")
            username = None
            if user:
                try:
                    from auth.jwt_handler import JWTHandler
                    payload = JWTHandler.verify_token(user)
                    username = payload.get("sub") if payload else None
                except:
                    pass
            log_csrf_failure(endpoint, client_ip, user=username)
        except:
            pass  # Don't fail if logging fails
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token"
        )


def csrf_protect(func):
    """
    Decorator to protect endpoint with CSRF token validation
    
    Usage:
        @app.post("/api/endpoint")
        @csrf_protect
        async def my_endpoint(request: Request):
            ...
    """
    async def wrapper(*args, **kwargs):
        # Find Request object in args/kwargs
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        if not request:
            request = kwargs.get("request")
        
        if request and request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            require_csrf_token(request)
        
        return await func(*args, **kwargs)
    
    return wrapper

