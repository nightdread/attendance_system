"""
Authentication middleware for FastAPI
"""
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from .jwt_handler import JWTHandler

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """Dependency to get current authenticated user"""
    if not credentials:
        return None

    token = credentials.credentials
    user = JWTHandler.get_current_user(token)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

def require_admin(current_user: dict = Depends(get_current_user)):
    """Dependency to require admin role"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return current_user

def require_permission(permission: str):
    """Create dependency to require specific permission"""
    def permission_checker(current_user: dict = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")

        # Admin has all permissions
        if current_user.get("role") == "admin":
            return current_user

        # Check if user has required permission
        user_permissions = current_user.get("permissions", [])
        if permission not in user_permissions and "all" not in user_permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission}' required"
            )

        return current_user

    return permission_checker

def require_role(role: str):
    """Create dependency to require specific role"""
    def role_checker(current_user: dict = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")

        if current_user.get("role") != role:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role}' required"
            )

        return current_user

    return role_checker

def require_authenticated(current_user: dict = Depends(get_current_user)):
    """Dependency to require any authenticated user"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    return current_user
