"""
Logging system for the attendance application
"""
import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime

class JsonFormatter(logging.Formatter):
    """Simple JSON formatter for structured logs"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "func": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_entry["stack"] = self.formatStack(record.stack_info)
        return json.dumps(log_entry, ensure_ascii=False)


class Logger:
    """Centralized logging configuration"""

    # Log levels
    LOG_LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }

    def __init__(self, name: str = "attendance_system"):
        self.name = name
        self.logger = None
        self.setup_logging()

    def setup_logging(self):
        """Setup logging configuration"""
        # Create logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Get log level from environment
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        log_level = self.LOG_LEVELS.get(log_level_str, logging.INFO)

        # Create logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(log_level)

        # Remove existing handlers
        self.logger.handlers.clear()

        # Choose formatter (default JSON for structured logs)
        use_json = os.getenv("LOG_FORMAT", "json").lower() == "json"
        detailed_formatter = JsonFormatter() if use_json else logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        simple_formatter = JsonFormatter() if use_json else logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(simple_formatter)
        self.logger.addHandler(console_handler)

        # File handler with rotation (detailed logs)
        file_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "attendance.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(file_handler)

        # Error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "errors.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(error_handler)

        # Telegram bot specific logger
        bot_logger = logging.getLogger("telegram_bot")
        bot_logger.setLevel(logging.INFO)

        bot_handler = logging.handlers.RotatingFileHandler(
            logs_dir / "telegram_bot.log",
            maxBytes=5*1024*1024,
            backupCount=3
        )
        bot_handler.setFormatter(detailed_formatter)
        bot_logger.addHandler(bot_handler)
        bot_logger.addHandler(console_handler)  # Also log to console

    def get_logger(self) -> logging.Logger:
        """Get the configured logger"""
        return self.logger

    def get_bot_logger(self) -> logging.Logger:
        """Get the Telegram bot specific logger"""
        return logging.getLogger("telegram_bot")

# Global logger instance
logger = Logger().get_logger()
bot_logger = Logger().get_bot_logger()

def log_request(request, response=None, user=None):
    """Log HTTP request"""
    user_info = f" [User: {user}]" if user else ""
    if response:
        logger.info(f"{request.method} {request.url.path} -> {response.status_code}{user_info}")
    else:
        logger.info(f"{request.method} {request.url.path}{user_info}")

def log_auth_event(event: str, username: str, success: bool = True):
    """Log authentication events"""
    level = logging.INFO if success else logging.WARNING
    status = "SUCCESS" if success else "FAILED"
    logger.log(level, f"AUTH {status}: {event} for user '{username}'")

def log_attendance_event(user_id: int, location: str, action: str, method: str = "unknown"):
    """Log attendance events"""
    logger.info(f"ATTENDANCE: User {user_id} {action} at {location} via {method}")

def log_error(error: Exception | str, context: str = ""):
    """Log errors with context
    
    Args:
        error: Exception object or error message string
        context: Optional context string describing where the error occurred
    """
    if isinstance(error, Exception):
        logger.error(f"ERROR in {context}: {str(error)}", exc_info=True)
    else:
        # If it's a string, log it as a message
        logger.error(f"ERROR in {context}: {error}", exc_info=False)

def log_performance(operation: str, duration: float, details: str = ""):
    """Log performance metrics"""
    logger.info(f"PERF: {operation} took {duration:.3f}s {details}")

def log_security_event(
    event_type: str,
    description: str,
    user: str = None,
    ip_address: str = None,
    details: dict = None,
    severity: str = "INFO"
):
    """
    Log security-related events
    
    Args:
        event_type: Type of security event (e.g., "LOGIN_FAILED", "ROLE_CHANGED", "SUSPICIOUS_ACTIVITY")
        description: Human-readable description
        user: Username or user ID
        ip_address: Client IP address
        details: Additional details as dictionary
        severity: Log level (INFO, WARNING, ERROR, CRITICAL)
    """
    level = getattr(logging, severity.upper(), logging.INFO)
    
    log_data = {
        "event_type": event_type,
        "description": description,
    }
    
    if user:
        log_data["user"] = user
    if ip_address:
        log_data["ip_address"] = ip_address
    if details:
        log_data.update(details)
    
    # Format as structured log
    details_str = ", ".join([f"{k}={v}" for k, v in log_data.items() if k != "event_type" and k != "description"])
    message = f"SECURITY [{event_type}]: {description}"
    if details_str:
        message += f" ({details_str})"
    
    logger.log(level, message)

def log_failed_login(username: str, ip_address: str, reason: str = "Invalid credentials"):
    """Log failed login attempt"""
    log_security_event(
        event_type="LOGIN_FAILED",
        description=f"Failed login attempt for user '{username}'",
        user=username,
        ip_address=ip_address,
        details={"reason": reason},
        severity="WARNING"
    )

def log_successful_login(username: str, ip_address: str, role: str = None):
    """Log successful login"""
    details = {}
    if role:
        details["role"] = role
    log_security_event(
        event_type="LOGIN_SUCCESS",
        description=f"Successful login for user '{username}'",
        user=username,
        ip_address=ip_address,
        details=details,
        severity="INFO"
    )

def log_role_change(changed_by: str, target_user: str, old_role: str, new_role: str, ip_address: str = None):
    """Log role/permission change"""
    log_security_event(
        event_type="ROLE_CHANGED",
        description=f"User '{changed_by}' changed role of '{target_user}' from '{old_role}' to '{new_role}'",
        user=changed_by,
        ip_address=ip_address,
        details={
            "target_user": target_user,
            "old_role": old_role,
            "new_role": new_role
        },
        severity="WARNING"
    )

def log_permission_change(changed_by: str, target_user: str, changes: dict, ip_address: str = None):
    """Log permission changes"""
    log_security_event(
        event_type="PERMISSION_CHANGED",
        description=f"User '{changed_by}' changed permissions for '{target_user}'",
        user=changed_by,
        ip_address=ip_address,
        details={
            "target_user": target_user,
            "changes": changes
        },
        severity="WARNING"
    )

def log_suspicious_activity(activity_type: str, description: str, ip_address: str = None, user: str = None, details: dict = None):
    """Log suspicious activity"""
    log_security_event(
        event_type="SUSPICIOUS_ACTIVITY",
        description=description,
        user=user,
        ip_address=ip_address,
        details=details or {},
        severity="WARNING"
    )

def log_data_export(user: str, export_type: str, record_count: int = None, ip_address: str = None):
    """Log data export events"""
    details = {"export_type": export_type}
    if record_count is not None:
        details["record_count"] = record_count
    log_security_event(
        event_type="DATA_EXPORT",
        description=f"User '{user}' exported {export_type} data",
        user=user,
        ip_address=ip_address,
        details=details,
        severity="INFO"
    )

def log_rate_limit_exceeded(endpoint: str, ip_address: str, attempts: int = None):
    """Log rate limit exceeded"""
    details = {"endpoint": endpoint}
    if attempts:
        details["attempts"] = attempts
    log_security_event(
        event_type="RATE_LIMIT_EXCEEDED",
        description=f"Rate limit exceeded for endpoint '{endpoint}' from IP '{ip_address}'",
        ip_address=ip_address,
        details=details,
        severity="WARNING"
    )

def log_csrf_failure(endpoint: str, ip_address: str, user: str = None):
    """Log CSRF token validation failure"""
    log_security_event(
        event_type="CSRF_FAILED",
        description=f"CSRF token validation failed for endpoint '{endpoint}'",
        user=user,
        ip_address=ip_address,
        details={"endpoint": endpoint},
        severity="WARNING"
    )

def log_unauthorized_access(attempted_resource: str, user: str = None, ip_address: str = None, reason: str = None):
    """Log unauthorized access attempt"""
    details = {"resource": attempted_resource}
    if reason:
        details["reason"] = reason
    log_security_event(
        event_type="UNAUTHORIZED_ACCESS",
        description=f"Unauthorized access attempt to '{attempted_resource}'",
        user=user,
        ip_address=ip_address,
        details=details,
        severity="WARNING"
    )
