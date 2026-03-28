"""
Market data service for real-time and historical data
This service now persists the watchlist to disk and caches historical data locally
so the UI can display stored prices without always calling external APIs.
"""
import asyncio
import os
import json
from typing import List, Optional
from datetime import datetime, timedelta

from app.core.logger import logger
from app.core.config import settings
from app.models.market_data import Quote, Bar, News, MarketStatus, WatchlistItem
from app.services.alpha_vantage_service import AlphaVantageService
from app.services.polygon_service import PolygonService


class MarketDataService:
    def __init__(self):
        self.alpha_vantage = AlphaVantageService()
        self.polygon = PolygonService()
        self.watchlist: List[WatchlistItem] = []

        # data paths (same pattern as order_store)
        base_data = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        self._watchlist_path = os.path.join(base_data, "watchlist.json")
        self._history_dir = os.path.join(base_data, "market_history")

        os.makedirs(self._history_dir, exist_ok=True)

        # load persisted watchlist if present
        try:
            self._load_watchlist_from_disk()
        except Exception:
            logger.debug("No persisted watchlist found; starting with empty watchlist")

        # Internal lock for file operations
        self._file_lock = asyncio.Lock()

    # --- persistence helpers ---
    def _load_watchlist_from_disk(self):
        if os.path.exists(self._watchlist_path):
            try:
                with open(self._watchlist_path, 'r') as f:
                    raw = json.load(f)
                items = []
                for entry in raw:
                    items.append(WatchlistItem(
                        symbol=entry.get('symbol'),
                        added_at=datetime.fromisoformat(entry.get('added_at')),
                        notes=entry.get('notes')
                    ))
                self.watchlist = items
                logger.info(f"Loaded {len(items)} watchlist items from disk")
            except Exception as e:
                logger.error(f"Failed to load watchlist from disk: {e}")

    def _save_watchlist_to_disk(self):
        try:
            arr = []
            for item in self.watchlist:
                arr.append({
                    'symbol': item.symbol,
                    'added_at': item.added_at.isoformat(),
                    'notes': item.notes
                })
            os.makedirs(os.path.dirname(self._watchlist_path), exist_ok=True)
            with open(self._watchlist_path, 'w') as f:
                json.dump(arr, f, indent=2)
            logger.info(f"Persisted watchlist ({len(arr)} items)")
        except Exception as e:
            logger.error(f"Failed to save watchlist to disk: {e}")

    def _history_path(self, symbol: str) -> str:
        safe = symbol.replace('/', '_').upper()
        return os.path.join(self._history_dir, f"{safe}.json")

    def _load_history(self, symbol: str) -> List[Bar]:
        path = self._history_path(symbol)
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r') as f:
                raw = json.load(f)
            bars: List[Bar] = []
            for b in raw:
                bars.append(Bar(
                    symbol=b.get('symbol', symbol),
                    timestamp=datetime.fromisoformat(b['timestamp']),
                    open=float(b['open']),
                    high=float(b['high']),
                    low=float(b['low']),
                    close=float(b['close']),
                    volume=int(b.get('volume', 0)),
                    timeframe=b.get('timeframe', '1min')
                ))
            return bars
        except Exception as e:
            logger.error(f"Failed to load history for {symbol}: {e}")
            return []

    def _save_history(self, symbol: str, bars: List[Bar]):
        path = self._history_path(symbol)
        try:
            arr = []
            for b in bars:
                arr.append({
                    'symbol': b.symbol,
                    'timestamp': b.timestamp.isoformat(),
                    'open': b.open,
                    'high': b.high,
                    'low': b.low,
                    'close': b.close,
                    'volume': b.volume,
                    'timeframe': b.timeframe
                })
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(arr, f, indent=2)
            logger.info(f"Saved {len(arr)} history bars for {symbol}")
        except Exception as e:
            logger.error(f"Failed to save history for {symbol}: {e}")

    # --- public API ---
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get real-time quote for a symbol.
        Prefer using local cached history (most recent bar) when available to avoid
        hitting external APIs for data we already recorded.
        """
        try:
            # Check local cache
            bars = await asyncio.get_event_loop().run_in_executor(None, self._load_history, symbol)
            if bars:
                last_bar = bars[-1]
                return Quote(
                    symbol=symbol,
                    last=last_bar.close,
                    volume=last_bar.volume,
                    timestamp=last_bar.timestamp
                )

            # Fall back to external providers
            quote = await self.polygon.get_quote(symbol)
            if not quote:
                quote = await self.alpha_vantage.get_quote(symbol)

            return quote
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {str(e)}")
            return None

    async def get_quotes(self, symbols: List[str]) -> List[Quote]:
        """Get real-time quotes for multiple symbols"""
        quotes = []
        for symbol in symbols:
            quote = await self.get_quote(symbol)
            if quote:
                quotes.append(quote)
        return quotes

    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str = "1min",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Bar]:
        """Get historical price data. Uses local cache first and only calls external
        providers for missing data. New bars are appended to local cache.
        """
        try:
            # Default to last 24 hours if no dates provided
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=1)

            # Load local cached bars
            cached_bars = await asyncio.get_event_loop().run_in_executor(None, self._load_history, symbol)

            # Filter cached bars within requested range
            filtered = [b for b in cached_bars if start_date <= b.timestamp <= end_date]
            if filtered:
                # If cached records satisfy the limit and cover the requested range, return them
                if len(filtered) >= limit or (filtered[0].timestamp <= start_date and filtered[-1].timestamp >= end_date):
                    return filtered[:limit]

            # Otherwise call external providers (Polygon preferred)
            bars = await self.polygon.get_historical_data(symbol, timeframe, start_date, end_date, limit)
            if not bars:
                bars = await self.alpha_vantage.get_historical_data(symbol, timeframe, start_date, end_date, limit)

            # Persist returned bars by merging with existing cached bars
            if bars:
                # Ensure bars sorted by timestamp
                bars_sorted = sorted(bars, key=lambda x: x.timestamp)

                # Merge unique timestamps into cached_bars
                existing = {b.timestamp.isoformat(): b for b in cached_bars}
                for b in bars_sorted:
                    existing[b.timestamp.isoformat()] = b

                merged = sorted(existing.values(), key=lambda x: x.timestamp)

                # Save merged history
                await asyncio.get_event_loop().run_in_executor(None, self._save_history, symbol, merged)

                # Return only the requested slice
                result = [b for b in merged if start_date <= b.timestamp <= end_date]
                return result[:limit]

            return []
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {str(e)}")
            return []

    async def get_news(self, symbol: str, limit: int = 10) -> List[News]:
        """Get news for a symbol"""
        try:
            # Try Polygon first, then Alpha Vantage
            news = await self.polygon.get_news(symbol, limit)
            if not news:
                news = await self.alpha_vantage.get_news(symbol, limit)

            return news
        except Exception as e:
            logger.error(f"Error getting news for {symbol}: {str(e)}")
            return []

    async def get_market_status(self) -> MarketStatus:
        """Get market status (open/closed)"""
        try:
            # Check if market is open (simplified logic)
            now = datetime.now()
            # Assume market is open 9:30 AM - 4:00 PM ET, Monday-Friday
            market_open = (
                now.weekday() < 5 and  # Monday-Friday
                9.5 <= now.hour + now.minute/60 <= 16  # 9:30 AM - 4:00 PM
            )

            return MarketStatus(
                market_open=market_open,
                timezone="US/Eastern"
            )

        except Exception as e:
            logger.error(f"Error getting market status: {str(e)}")
            return MarketStatus(market_open=False)

    async def get_watchlist(self) -> List[WatchlistItem]:
        """Get current watchlist"""
        return self.watchlist

    async def add_to_watchlist(self, symbol: str) -> bool:
        """Add symbol to watchlist and persist it to disk. Also ensure a local
        history file exists for the symbol so future quote/historical requests
        can be served from cache.
        """
        try:
            # Normalize symbol
            symbol = symbol.strip().upper()

            # Check if already in watchlist
            for item in self.watchlist:
                if item.symbol == symbol:
                    return False

            # Add to watchlist
            item = WatchlistItem(
                symbol=symbol,
                added_at=datetime.now()
            )
            self.watchlist.append(item)

            # Persist watchlist
            await asyncio.get_event_loop().run_in_executor(None, self._save_watchlist_to_disk)


            # Ensure history file exists (empty) and attempt to populate it with recent bars
            path = self._history_path(symbol)
            if not os.path.exists(path):
                await asyncio.get_event_loop().run_in_executor(None, self._save_history, symbol, [])

            # Try to fetch recent historical data once and persist it so UI can use local cache
            try:
                # request last 1 day of 1min bars (limit 1440)
                bars = []
                if getattr(self.polygon, 'api_key', None):
                    bars = await self.polygon.get_historical_data(symbol, '1min', datetime.now() - timedelta(days=1), datetime.now(), 500)
                if not bars and getattr(self.alpha_vantage, 'api_key', None):
                    bars = await self.alpha_vantage.get_historical_data(symbol, '1min', datetime.now() - timedelta(days=1), datetime.now(), 500)

                if bars:
                    # merge with any cached (should be empty) and save
                    await asyncio.get_event_loop().run_in_executor(None, self._save_history, symbol, bars)
                    logger.info(f"Populated initial history for {symbol} with {len(bars)} bars")
            except Exception as e:
                logger.debug(f"Could not populate initial history for {symbol}: {e}")

            logger.info(f"Added {symbol} to watchlist")
            return True

        except Exception as e:
            logger.error(f"Error adding {symbol} to watchlist: {str(e)}")
            return False

    async def remove_from_watchlist(self, symbol: str) -> bool:
        """Remove symbol from watchlist and persist change"""
        try:
            for i, item in enumerate(self.watchlist):
                if item.symbol == symbol:
                    del self.watchlist[i]
                    await asyncio.get_event_loop().run_in_executor(None, self._save_watchlist_to_disk)
                    logger.info(f"Removed {symbol} from watchlist")
                    return True
            return False

        except Exception as e:
            logger.error(f"Error removing {symbol} from watchlist: {str(e)}")
            return False
