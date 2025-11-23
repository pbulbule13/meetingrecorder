"""
Centralized logging configuration for all Python services
"""

import sys
from pathlib import Path
from loguru import logger

# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def setup_logger(service_name: str):
    """
    Configure logger for a specific service with file rotation

    Args:
        service_name: Name of the service (transcription, llm, rag, etc.)
    """
    # Remove default handler
    logger.remove()

    # Console handler with colored output
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )

    # File handler for all logs with rotation
    logger.add(
        LOGS_DIR / f"{service_name}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",  # Rotate when file reaches 10MB
        retention="30 days",  # Keep logs for 30 days
        compression="zip",  # Compress rotated logs
        enqueue=True,  # Thread-safe logging
    )

    # Separate file for errors only
    logger.add(
        LOGS_DIR / f"{service_name}_errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
        level="ERROR",
        rotation="5 MB",
        retention="30 days",
        compression="zip",
        backtrace=True,  # Include full stack trace
        diagnose=True,  # Include variable values in trace
        enqueue=True,
    )

    # Activity log for all services (combined)
    logger.add(
        LOGS_DIR / "activity.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | [{extra[service]}] {message}",
        level="INFO",
        rotation="50 MB",
        retention="60 days",
        compression="zip",
        enqueue=True,
    )

    # Bind service name to all log records
    logger.configure(extra={"service": service_name})

    logger.info(f"{service_name} service logger initialized")

    return logger


def log_request(endpoint: str, method: str = "POST", **kwargs):
    """
    Log API request with details

    Args:
        endpoint: API endpoint called
        method: HTTP method
        **kwargs: Additional context (user_id, session_id, etc.)
    """
    context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
    logger.info(f"API Request: {method} {endpoint} | {context}")


def log_response(endpoint: str, status: int, duration_ms: float, **kwargs):
    """
    Log API response with timing

    Args:
        endpoint: API endpoint
        status: HTTP status code
        duration_ms: Response time in milliseconds
        **kwargs: Additional context
    """
    context = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
    logger.info(f"API Response: {endpoint} | Status: {status} | Duration: {duration_ms:.2f}ms | {context}")


def log_performance(operation: str, duration_ms: float, **metrics):
    """
    Log performance metrics

    Args:
        operation: Operation name
        duration_ms: Duration in milliseconds
        **metrics: Additional metrics
    """
    metrics_str = " | ".join([f"{k}={v}" for k, v in metrics.items()])
    logger.info(f"Performance: {operation} | Duration: {duration_ms:.2f}ms | {metrics_str}")


def log_activity(activity_type: str, description: str, **context):
    """
    Log user activity for audit trail

    Args:
        activity_type: Type of activity (session_start, meeting_created, etc.)
        description: Human-readable description
        **context: Additional context
    """
    context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
    logger.info(f"Activity: {activity_type} | {description} | {context_str}")


# Export configured logger instance
__all__ = [
    "setup_logger",
    "log_request",
    "log_response",
    "log_performance",
    "log_activity",
    "logger"
]
