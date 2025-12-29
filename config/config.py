import os
from pathlib import Path
from typing import List


def _require_env(name: str, default: str = None) -> str:
    """Fetch required env var or fail fast."""
    value = os.getenv(name, default)
    if not value or value.strip() == "" or "your-secret-key" in value:
        raise ValueError(f"Environment variable {name} is required")
    return value

# Security settings (must be provided via env)
SECRET_KEY = _require_env("SECRET_KEY")
# Session secret (can be rotated independently; defaults to SECRET_KEY)
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", SECRET_KEY)

# Paths
BASE_DIR = Path(__file__).parent.parent

# Database settings
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "attendance.db"))

# Telegram Bot settings (must be provided via env)
BOT_TOKEN = _require_env("BOT_TOKEN")
BOT_USERNAME = _require_env("BOT_USERNAME")

# Web terminal settings (пароль обязателен, логин по умолчанию admin)
WEB_USERNAME = os.getenv("WEB_USERNAME", "admin")
WEB_PASSWORD = _require_env("WEB_PASSWORD")

# System is now unified - no location separation
# All tokens and attendance are global

# API settings
API_HOST = "0.0.0.0"
API_PORT = 8000

# QR update interval (seconds)
QR_UPDATE_INTERVAL = 5

# Token settings
TOKEN_LENGTH = 8

# JWT settings (support rotation: current + optional previous)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
JWT_SECRET_KEY_PREV = os.getenv("JWT_SECRET_KEY_PREV")
JWT_SECRET_KEYS = [k for k in [JWT_SECRET_KEY, JWT_SECRET_KEY_PREV] if k]
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# User roles and permissions
USER_ROLES = {
    "admin": {
        "name": "Администратор",
        "permissions": ["all"],
        "description": "Полный доступ ко всем функциям"
    },
    "manager": {
        "name": "Менеджер",
        "permissions": ["view_analytics", "manage_users", "view_reports"],
        "description": "Управление пользователями и просмотр аналитики"
    },
    "hr": {
        "name": "HR специалист",
        "permissions": ["view_analytics", "manage_employees", "view_reports"],
        "description": "Управление сотрудниками и отчетами"
    },
    "user": {
        "name": "Сотрудник",
        "permissions": ["check_attendance", "view_own_stats"],
        "description": "Базовый доступ для отметки посещаемости"
    },
    "terminal": {
        "name": "Терминал",
        "permissions": ["view_terminal", "view_qr_code"],
        "description": "Доступ только к странице терминала с QR-кодом"
    }
}

DEFAULT_ROLE = "user"

# Permission definitions
PERMISSIONS = {
    "all": "Полный доступ ко всем функциям",
    "view_analytics": "Просмотр аналитики и отчетов",
    "manage_users": "Управление пользователями",
    "manage_employees": "Управление сотрудниками",
    "view_reports": "Просмотр отчетов",
    "check_attendance": "Отметка посещаемости",
    "view_own_stats": "Просмотр собственной статистики",
    "manage_tokens": "Управление QR токенами",
    "system_admin": "Администрирование системы",
    "view_terminal": "Просмотр страницы терминала",
    "view_qr_code": "Просмотр QR-кода"
}

# API settings
API_KEY = os.getenv("API_KEY")  # Optional API key for external access

# Logging settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
LOG_MAX_SIZE = int(os.getenv("LOG_MAX_SIZE", "10485760"))  # 10MB default
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# Redis settings
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").lower() == "true"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Cache TTL settings (in seconds)
CACHE_TTL_TOKEN = int(os.getenv("CACHE_TTL_TOKEN", "300"))  # 5 minutes for tokens
CACHE_TTL_ANALYTICS = int(os.getenv("CACHE_TTL_ANALYTICS", "600"))  # 10 minutes for analytics
CACHE_TTL_USER = int(os.getenv("CACHE_TTL_USER", "1800"))  # 30 minutes for user data