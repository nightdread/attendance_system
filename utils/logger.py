"""
Logging system for the attendance application
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime

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

        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )

        simple_formatter = logging.Formatter(
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

def log_error(error: Exception, context: str = ""):
    """Log errors with context"""
    logger.error(f"ERROR in {context}: {str(error)}", exc_info=True)

def log_performance(operation: str, duration: float, details: str = ""):
    """Log performance metrics"""
    logger.info(f"PERF: {operation} took {duration:.3f}s {details}")
