"""
Pydantic schemas for API request/response models
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class TokenResponse(BaseModel):
    """Response model for token endpoints"""
    token: str = Field(..., description="Current attendance token", example="abc12345")
    url: str = Field(..., description="Telegram bot URL with token", example="https://t.me/mybot?start=abc12345")
    bot_url: str = Field(..., description="Alias for url field", example="https://t.me/mybot?start=abc12345")
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "abc12345",
                "url": "https://t.me/mybot?start=abc12345",
                "bot_url": "https://t.me/mybot?start=abc12345"
            }
        }


class UserUpdateRequest(BaseModel):
    """Request model for updating user"""
    full_name: Optional[str] = Field(None, description="User's full name", example="Иванов Иван Иванович", max_length=200)
    role: Optional[str] = Field(None, description="User role", example="user", enum=["user", "admin", "manager", "hr", "terminal"])
    department: Optional[str] = Field(None, description="Department name", example="IT", max_length=100)
    position: Optional[str] = Field(None, description="Job position", example="Developer", max_length=100)
    is_active: Optional[bool] = Field(None, description="Whether user is active", example=True)
    password: Optional[str] = Field(None, description="New password (min 8 chars, must contain letters and digits)", example="NewPass123", min_length=8)
    
    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Иванов Иван Иванович",
                "role": "user",
                "department": "IT",
                "position": "Developer",
                "is_active": True
            }
        }


class UserResponse(BaseModel):
    """Response model for user data"""
    id: int = Field(..., description="User ID", example=1)
    username: str = Field(..., description="Username", example="user123")
    full_name: Optional[str] = Field(None, description="Full name", example="Иванов Иван Иванович")
    role: str = Field(..., description="User role", example="user")
    department: Optional[str] = Field(None, description="Department", example="IT")
    position: Optional[str] = Field(None, description="Position", example="Developer")
    is_active: bool = Field(..., description="Active status", example=True)
    created_at: Optional[str] = Field(None, description="Creation timestamp", example="2024-01-01T12:00:00Z")
    last_login: Optional[str] = Field(None, description="Last login timestamp", example="2024-01-01T12:00:00Z")


class HealthCheckResponse(BaseModel):
    """Response model for health check"""
    status: str = Field(..., description="Health status", example="healthy", enum=["healthy", "degraded"])
    version: str = Field(..., description="API version", example="1.0.0")
    timestamp: str = Field(..., description="Check timestamp", example="2024-01-01T12:00:00Z")
    checks: Dict[str, Any] = Field(..., description="Individual service checks")
    system: Optional[Dict[str, Any]] = Field(None, description="System metrics (if available)")


class MetricsResponse(BaseModel):
    """Response model for metrics endpoint"""
    timestamp: str = Field(..., description="Metrics timestamp", example="2024-01-01T12:00:00Z")
    database: Dict[str, Any] = Field(..., description="Database metrics")
    redis: Dict[str, Any] = Field(..., description="Redis metrics")
    system: Dict[str, Any] = Field(..., description="System metrics")
    application: Optional[Dict[str, Any]] = Field(None, description="Application statistics")


class ErrorResponse(BaseModel):
    """Standard error response model"""
    detail: str = Field(..., description="Error message", example="User not found")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {"detail": "User not found"},
                {"detail": "Invalid or missing CSRF token"},
                {"detail": "Unauthorized"},
                {"detail": "Превышен лимит запросов (10 за 60 секунд). Блокировка на 300 секунд."}
            ]
        }


class AnalyticsSummaryResponse(BaseModel):
    """Response model for analytics summary"""
    total_users: int = Field(..., description="Total number of users", example=100)
    present_users: int = Field(..., description="Currently present users", example=25)
    today_visits: int = Field(..., description="Today's visits", example=50)
    avg_work_time: Optional[float] = Field(None, description="Average work time in hours", example=8.5)


class DailyStatsResponse(BaseModel):
    """Response model for daily statistics"""
    checkins: int = Field(..., description="Number of check-ins", example=50)
    checkouts: int = Field(..., description="Number of check-outs", example=45)
    unique_users: int = Field(..., description="Number of unique users", example=30)


class EmployeeStatsResponse(BaseModel):
    """Response model for employee statistics"""
    user_id: int = Field(..., description="User ID", example=1)
    full_name: str = Field(..., description="Full name", example="Иванов Иван Иванович")
    username: Optional[str] = Field(None, description="Username", example="ivanov")
    total_events: int = Field(..., description="Total events", example=100)
    checkins: int = Field(..., description="Check-ins count", example=50)
    checkouts: int = Field(..., description="Check-outs count", example=50)
    last_activity: Optional[str] = Field(None, description="Last activity timestamp", example="2024-01-01T12:00:00Z")

