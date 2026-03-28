"""
Market data models
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class Quote(BaseModel):
    symbol: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    volume: Optional[int] = None
    timestamp: datetime

class Bar(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    timeframe: str

class News(BaseModel):
    id: str
    symbol: str
    headline: str
    summary: str
    url: Optional[str] = None
    published_at: datetime
    source: str
    sentiment: Optional[str] = None  # POSITIVE, NEGATIVE, NEUTRAL

class MarketStatus(BaseModel):
    market_open: bool
    next_open: Optional[datetime] = None
    next_close: Optional[datetime] = None
    timezone: str = "US/Eastern"

class WatchlistItem(BaseModel):
    symbol: str
    added_at: datetime
    notes: Optional[str] = None
