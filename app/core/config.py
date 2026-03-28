"""
Configuration settings for the trading system
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Application settings
    app_name: str = "Algorithmic Trading System"
    debug: bool = False
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database settings
    database_url: str = "sqlite:///./trading.db"
    
    # Redis settings
    redis_url: str = "redis://localhost:6379"
    
    # IBKR TWS settings
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 1
    
    # Market data API keys
    alpha_vantage_api_key: Optional[str] = None
    polygon_api_key: Optional[str] = None
    
    # Trading settings
    max_position_size: float = 10000.0
    risk_per_trade: float = 0.02  # 2% risk per trade
    max_daily_loss: float = 0.05  # 5% max daily loss
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/trading.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()
