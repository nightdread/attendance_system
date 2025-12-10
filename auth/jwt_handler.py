"""
JWT token handling for authentication
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from config import SECRET_KEY

# Password hashing
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

class JWTHandler:
    """Handle JWT token operations"""

    SECRET_KEY = SECRET_KEY
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=JWTHandler.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, JWTHandler.SECRET_KEY, algorithm=JWTHandler.ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, JWTHandler.SECRET_KEY, algorithms=[JWTHandler.ALGORITHM])
            return payload
        except JWTError:
            return None

    @staticmethod
    def get_current_user(token: str) -> Optional[dict]:
        """Get current user from token"""
        payload = JWTHandler.verify_token(token)
        if payload:
            return {
                "username": payload.get("sub"),
                "role": payload.get("role", "user")
            }
        return None
