"""
Alpha Vantage API service
"""
import aiohttp
import asyncio
from typing import List, Optional
from datetime import datetime

from app.core.logger import logger
from app.core.config import settings
from app.models.market_data import Quote, Bar, News

class AlphaVantageService:
    def __init__(self):
        self.api_key = settings.alpha_vantage_api_key
        self.base_url = "https://www.alphavantage.co/query"
        
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get real-time quote from Alpha Vantage"""
        try:
            if not self.api_key:
                logger.warning("Alpha Vantage API key not configured")
                return None
                
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self.api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        quote_data = data.get("Global Quote", {})
                        
                        if quote_data:
                            return Quote(
                                symbol=symbol,
                                bid=float(quote_data.get("03. low", 0)),
                                ask=float(quote_data.get("02. high", 0)),
                                last=float(quote_data.get("05. price", 0)),
                                volume=int(quote_data.get("06. volume", 0)),
                                timestamp=datetime.now()
                            )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Alpha Vantage quote for {symbol}: {str(e)}")
            return None
    
    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str = "1min",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Bar]:
        """Get historical data from Alpha Vantage"""
        try:
            if not self.api_key:
                logger.warning("Alpha Vantage API key not configured")
                return []
                
            # Map timeframe to Alpha Vantage function
            function_map = {
                "1min": "TIME_SERIES_INTRADAY",
                "5min": "TIME_SERIES_INTRADAY",
                "15min": "TIME_SERIES_INTRADAY",
                "1hour": "TIME_SERIES_INTRADAY",
                "1day": "TIME_SERIES_DAILY"
            }
            
            function = function_map.get(timeframe, "TIME_SERIES_DAILY")
            
            params = {
                "function": function,
                "symbol": symbol,
                "apikey": self.api_key,
                "outputsize": "compact"
            }
            
            if function == "TIME_SERIES_INTRADAY":
                params["interval"] = timeframe
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract time series data
                        time_series_key = None
                        for key in data.keys():
                            if "Time Series" in key:
                                time_series_key = key
                                break
                        
                        if time_series_key:
                            time_series = data[time_series_key]
                            bars = []
                            
                            for timestamp_str, values in list(time_series.items())[:limit]:
                                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                                
                                bar = Bar(
                                    symbol=symbol,
                                    timestamp=timestamp,
                                    open=float(values["1. open"]),
                                    high=float(values["2. high"]),
                                    low=float(values["3. low"]),
                                    close=float(values["4. close"]),
                                    volume=int(values["5. volume"]),
                                    timeframe=timeframe
                                )
                                bars.append(bar)
                            
                            return bars
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting Alpha Vantage historical data for {symbol}: {str(e)}")
            return []
    
    async def get_news(self, symbol: str, limit: int = 10) -> List[News]:
        """Get news from Alpha Vantage"""
        try:
            if not self.api_key:
                logger.warning("Alpha Vantage API key not configured")
                return []
                
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": symbol,
                "apikey": self.api_key,
                "limit": limit
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        news_items = data.get("feed", [])
                        
                        news_list = []
                        for item in news_items:
                            news = News(
                                id=item.get("uuid", ""),
                                symbol=symbol,
                                headline=item.get("title", ""),
                                summary=item.get("summary", ""),
                                url=item.get("url", ""),
                                published_at=datetime.fromisoformat(
                                    item.get("time_published", "").replace("Z", "+00:00")
                                ),
                                source=item.get("source", ""),
                                sentiment=item.get("overall_sentiment_score", "")
                            )
                            news_list.append(news)
                        
                        return news_list
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting Alpha Vantage news for {symbol}: {str(e)}")
            return []
