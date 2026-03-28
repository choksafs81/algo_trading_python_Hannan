"""
Trading data models
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class Order(BaseModel):
    id: str
    symbol: str
    quantity: int
    order_type: OrderType
    side: OrderSide
    # Optional IB numeric order id assigned when IB accepts/submits the order
    ib_id: Optional[int] = None
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus
    filled_quantity: int = 0
    average_price: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    filled_at: Optional[datetime] = None

class Position(BaseModel):
    symbol: str
    quantity: int
    average_price: float
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: float = 0.0
    market_value: Optional[float] = None
    updated_at: datetime

class Trade(BaseModel):
    id: str
    symbol: str
    quantity: int
    price: float
    side: OrderSide
    timestamp: datetime
    order_id: str
    commission: Optional[float] = None
    pnl: Optional[float] = None

class AccountInfo(BaseModel):
    account_id: str
    buying_power: float
    cash: float
    equity: float
    margin_used: float
    margin_available: float
    net_liquidation_value: float
    updated_at: datetime
