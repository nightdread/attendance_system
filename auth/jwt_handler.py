"""
JWT token handling for authentication
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from config import JWT_SECRET_KEYS, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES

# Password hashing
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

class JWTHandler:
    """Handle JWT token operations with key rotation support"""

    SECRET_KEYS = JWT_SECRET_KEYS
    ALGORITHM = JWT_ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES = JWT_ACCESS_TOKEN_EXPIRE_MINUTES

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
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=JWTHandler.ACCESS_TOKEN_EXPIRE_MINUTES))

        to_encode.update({"exp": expire})
        signing_key = JWTHandler.SECRET_KEYS[0]
        encoded_jwt = jwt.encode(to_encode, signing_key, algorithm=JWTHandler.ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify and decode JWT token"""
        try:
            last_error = None
            for key in JWTHandler.SECRET_KEYS:
                try:
                    return jwt.decode(token, key, algorithms=[JWTHandler.ALGORITHM])
                except JWTError as e:
                    last_error = e
                    continue
            return None
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
