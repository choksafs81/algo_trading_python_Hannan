"""
Polygon API service
"""
import aiohttp
import asyncio
from typing import List, Optional
from datetime import datetime

from app.core.logger import logger
from app.core.config import settings
from app.models.market_data import Quote, Bar, News

class PolygonService:
    def __init__(self):
        self.api_key = settings.polygon_api_key
        self.base_url = "https://api.polygon.io"
        # Rate limiting for free plan: 5 calls per minute
        self._rate_limit_max = 5
        self._rate_limit_window = 60  # seconds
        self._call_timestamps = []  # epoch seconds of recent calls
        self._rate_lock = asyncio.Lock()

        # Short in-memory cache for recent quotes to avoid burst calls
        # cache: symbol -> (Quote, timestamp)
        self._quote_cache = {}
        
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get real-time quote from Polygon"""
        try:
            # Check short cache (20s TTL)
            cached = self._quote_cache.get(symbol)
            if cached:
                quote_obj, ts = cached
                if (datetime.now() - ts).total_seconds() < 20:
                    return quote_obj

            if not self.api_key:
                logger.warning("Polygon API key not configured")
                return None
                
            url = f"{self.base_url}/v2/last/trade/{symbol}"
            params = {"apikey": self.api_key}
            
            # Respect rate limit before making request
            await self._wait_for_rate_slot()
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("status") == "OK":
                            trade = data.get("results", {})
                            
                            q = Quote(
                                symbol=symbol,
                                last=float(trade.get("p", 0)),
                                volume=int(trade.get("s", 0)),
                                timestamp=datetime.fromtimestamp(
                                    trade.get("t", 0) / 1000
                                )
                            )
                            # save to short cache
                            try:
                                self._quote_cache[symbol] = (q, datetime.now())
                            except Exception:
                                pass
                            return q
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Polygon quote for {symbol}: {str(e)}")
            return None
    
    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str = "1min",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Bar]:
        """Get historical data from Polygon"""
        try:
            if not self.api_key:
                logger.warning("Polygon API key not configured")
                return []
                
            # Map timeframe to Polygon timespan
            timespan_map = {
                "1min": "minute",
                "5min": "minute",
                "15min": "minute",
                "1hour": "hour",
                "1day": "day"
            }
            
            timespan = timespan_map.get(timeframe, "minute")
            
            # Format dates
            from_date = start_date.strftime("%Y-%m-%d") if start_date else None
            to_date = end_date.strftime("%Y-%m-%d") if end_date else None
            
            url = f"{self.base_url}/v2/aggs/ticker/{symbol}/range/1/{timespan}/{from_date}/{to_date}"
            params = {
                "apikey": self.api_key,
                "adjusted": "true",
                "sort": "asc",
                "limit": limit
            }
            
            # Respect rate limit before making request
            await self._wait_for_rate_slot()
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("status") == "OK":
                            results = data.get("results", [])
                            bars = []
                            
                            for result in results:
                                bar = Bar(
                                    symbol=symbol,
                                    timestamp=datetime.fromtimestamp(
                                        result.get("t", 0) / 1000
                                    ),
                                    open=float(result.get("o", 0)),
                                    high=float(result.get("h", 0)),
                                    low=float(result.get("l", 0)),
                                    close=float(result.get("c", 0)),
                                    volume=int(result.get("v", 0)),
                                    timeframe=timeframe
                                )
                                bars.append(bar)
                            
                            return bars
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting Polygon historical data for {symbol}: {str(e)}")
            return []
    
    async def get_news(self, symbol: str, limit: int = 10) -> List[News]:
        """Get news from Polygon"""
        try:
            if not self.api_key:
                logger.warning("Polygon API key not configured")
                return []
                
            url = f"{self.base_url}/v2/reference/news"
            params = {
                "ticker": symbol,
                "apikey": self.api_key,
                "limit": limit
            }
            
            # Respect rate limit before making request
            await self._wait_for_rate_slot()
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("status") == "OK":
                            results = data.get("results", [])
                            news_list = []
                            
                            for item in results:
                                news = News(
                                    id=item.get("id", ""),
                                    symbol=symbol,
                                    headline=item.get("title", ""),
                                    summary=item.get("description", ""),
                                    url=item.get("article_url", ""),
                                    published_at=datetime.fromisoformat(
                                        item.get("published_utc", "").replace("Z", "+00:00")
                                    ),
                                    source=item.get("publisher", {}).get("name", ""),
                                    sentiment=item.get("sentiment", "")
                                )
                                news_list.append(news)
                            
                            return news_list
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting Polygon news for {symbol}: {str(e)}")
            return []

    async def _wait_for_rate_slot(self):
        """Ensure we don't exceed the configured number of calls per window.
        Simple sliding-window implementation: wait until there is a free slot.
        """
        if not self.api_key:
            return

        async with self._rate_lock:
            now = int(datetime.now().timestamp())
            # purge old timestamps
            self._call_timestamps = [t for t in self._call_timestamps if now - t < self._rate_limit_window]
            if len(self._call_timestamps) < self._rate_limit_max:
                # we can proceed
                self._call_timestamps.append(now)
                return

            # need to wait until oldest timestamp is outside the window
            oldest = min(self._call_timestamps)
            wait = self._rate_limit_window - (now - oldest) + 0.05

        # release lock while sleeping to allow other coroutines to check
        await asyncio.sleep(wait)
        # after sleeping, try again (recursive but bounded)
        await self._wait_for_rate_slot()
