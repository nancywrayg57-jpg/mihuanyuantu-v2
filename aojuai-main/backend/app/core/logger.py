"""
AOJU Backend - Logging Configuration

使用 structlog 提供结构化日志支持
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to log entries"""
    event_dict["app"] = settings.APP_NAME
    event_dict["env"] = settings.ENV
    return event_dict


def setup_logging() -> None:
    """
    Configure structured logging with structlog
    
    Features:
    - JSON output in production
    - Pretty console output in development
    - Automatic log rotation
    - Separate error log file
    """
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO if not settings.DEBUG else logging.DEBUG,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    
    # Add file handlers
    if not settings.DEBUG:
        # Info log file
        info_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_dir / "info.log",
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
        )
        info_handler.setLevel(logging.INFO)
        logging.root.addHandler(info_handler)
        
        # Error log file
        error_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_dir / "error.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        logging.root.addHandler(error_handler)
    
    # Configure structlog processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_app_context,
    ]
    
    if settings.DEBUG:
        # Development: pretty console output
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # Production: JSON output
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Configured structlog logger
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user_created", user_id=123, username="john")
        >>> logger.error("database_error", error=str(e), query=sql)
    """
    return structlog.get_logger(name)


# Convenience logger for quick use
logger = get_logger("aoju")
