"""
Trading strategy models
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class StrategyStatus(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"

class Strategy(BaseModel):
    id: str
    name: str
    description: str
    parameters: Dict[str, Any]
    symbols: List[str]
    status: StrategyStatus
    enabled: bool
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None

class StrategyExecution(BaseModel):
    id: str
    strategy_id: str
    symbol: str
    action: str  # BUY, SELL, HOLD
    quantity: Optional[int] = None
    price: Optional[float] = None
    reason: str
    timestamp: datetime
    order_id: Optional[str] = None

class StrategyPerformance(BaseModel):
    strategy_id: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: Optional[float] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    updated_at: datetime

class StrategyStatusInfo(BaseModel):
    strategy_id: str
    status: StrategyStatus
    last_execution: Optional[datetime] = None
    current_positions: List[str] = []  # List of symbols with positions
    error_message: Optional[str] = None
    uptime: Optional[float] = None  # Seconds since started
