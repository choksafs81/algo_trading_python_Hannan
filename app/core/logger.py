"""
Logging configuration for the trading system
"""
from loguru import logger
import sys
import os
from app.core.config import settings

# Remove default logger
logger.remove()

# Add console logging
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level,
    colorize=True
)

# Add file logging
os.makedirs(os.path.dirname(settings.log_file), exist_ok=True)
logger.add(
    settings.log_file,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level=settings.log_level,
    rotation="10 MB",
    retention="7 days",
    compression="zip"
)

# Export logger for use in other modules
__all__ = ["logger"]
