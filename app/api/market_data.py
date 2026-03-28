"""
Market data API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.core.logger import logger
from app.services.market_data_service import MarketDataService
from app.models.market_data import Quote, Bar, News
import asyncio
from datetime import datetime
from app.services import watchlist_sync

router = APIRouter()

# Global market data service instance
_market_data_service = None

def get_market_data_service():
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService()
    return _market_data_service

class SymbolRequest(BaseModel):
    symbol: str

class HistoricalDataRequest(BaseModel):
    symbol: str
    timeframe: str = "1min"  # 1min, 5min, 15min, 1hour, 1day
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100

@router.get("/quotes/{symbol}", response_model=Quote)
async def get_quote(
    symbol: str,
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Get real-time quote for a symbol"""
    try:
        quote = await market_data_service.get_quote(symbol)
        if not quote:
            raise HTTPException(status_code=404, detail=f"No quote found for {symbol}")
        return quote
    except Exception as e:
        logger.error(f"Error getting quote for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quotes", response_model=List[Quote])
async def get_quotes(
    symbols: str,  # Comma-separated list of symbols
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Get real-time quotes for multiple symbols"""
    try:
        symbol_list = [s.strip() for s in symbols.split(",")]
        quotes = await market_data_service.get_quotes(symbol_list)
        return quotes
    except Exception as e:
        logger.error(f"Error getting quotes for {symbols}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/historical", response_model=List[Bar])
async def get_historical_data(
    request: HistoricalDataRequest,
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Get historical price data"""
    try:
        bars = await market_data_service.get_historical_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            limit=request.limit
        )
        return bars
    except Exception as e:
        logger.error(f"Error getting historical data for {request.symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/news/{symbol}", response_model=List[News])
async def get_news(
    symbol: str,
    limit: int = 10,
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Get news for a symbol"""
    try:
        news = await market_data_service.get_news(symbol, limit)
        return news
    except Exception as e:
        logger.error(f"Error getting news for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/market-status")
async def get_market_status(
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Get market status (open/closed)"""
    try:
        status = await market_data_service.get_market_status()
        return status
    except Exception as e:
        logger.error(f"Error getting market status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/watchlist")
async def get_watchlist(
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Get current watchlist"""
    try:
        watchlist = await market_data_service.get_watchlist()
        return watchlist
    except Exception as e:
        logger.error(f"Error getting watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watchlist/refresh/{symbol}")
async def refresh_watchlist_symbol(
    symbol: str,
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Force-populate or refresh local history for a symbol in the watchlist."""
    try:
        # call get_historical_data to populate cache; request 1 day of 1min bars (limit 500)
        now = datetime.now()
        bars = await market_data_service.get_historical_data(
            symbol=symbol,
            timeframe='1min',
            start_date=now - timedelta(days=1),
            end_date=now,
            limit=500
        )
        return {"symbol": symbol, "bars_fetched": len(bars)}
    except Exception as e:
        logger.error(f"Error refreshing history for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watchlist/refresh_all")
async def refresh_watchlist_all(
    interval_minutes: Optional[int] = 0,
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Refresh all watchlist symbols. If interval_minutes provided and >0,
    this schedules a background loop that continues to refresh at that interval.
    Otherwise it performs a one-time sync.
    """
    try:
        watch = await market_data_service.get_watchlist()
        symbols = [w.symbol for w in watch]

        results = {}
        # perform sequentially to be polite with rate limits
        for s in symbols:
            try:
                res = await market_data_service.get_historical_data(
                    symbol=s,
                    timeframe='1min',
                    start_date=datetime.now() - timedelta(days=1),
                    end_date=datetime.now(),
                    limit=500
                )
                results[s] = len(res)
            except Exception as e:
                results[s] = str(e)

        return {"results": results}
    except Exception as e:
        logger.error(f"Error refreshing all watchlist symbols: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/watchlist/sync_status')
async def watchlist_sync_status(
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Return a basic sync status. For now, return list of watchlist symbols and
    whether a history file exists locally.
    """
    try:
        watch = await market_data_service.get_watchlist()
        status = []
        for w in watch:
            # check file existence using service helper
            path = market_data_service._history_path(w.symbol)
            status.append({
                'symbol': w.symbol,
                'history_exists': bool(path and __import__('os').path.exists(path))
            })
        return {"status": status}
    except Exception as e:
        logger.error(f"Error getting watchlist sync status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/watchlist/auto_sync')
async def set_watchlist_auto_sync(
    enable: bool = True,
    interval_minutes: int = 30
):
    """Enable or disable background watchlist auto-sync. Returns status."""
    try:
        if enable:
            await watchlist_sync.start(interval_minutes)
        else:
            await watchlist_sync.stop()

        return watchlist_sync.status()
    except Exception as e:
        logger.error(f"Error setting watchlist auto-sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/watchlist/auto_sync')
async def get_watchlist_auto_sync():
    try:
        return watchlist_sync.status()
    except Exception as e:
        logger.error(f"Error getting watchlist auto-sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/watchlist/quotes")
async def get_watchlist_with_quotes(
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Get watchlist with real-time quotes"""
    try:
        watchlist = await market_data_service.get_watchlist()
        watchlist_with_quotes = []
        
        for item in watchlist:
            quote = await market_data_service.get_quote(item.symbol)
            watchlist_with_quotes.append({
                "symbol": item.symbol,
                "added_at": item.added_at,
                "notes": item.notes,
                "quote": quote
            })
        
        return watchlist_with_quotes
    except Exception as e:
        logger.error(f"Error getting watchlist with quotes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/watchlist")
async def add_to_watchlist(
    request: SymbolRequest,
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Add symbol to watchlist"""
    try:
        success = await market_data_service.add_to_watchlist(request.symbol)
        if not success:
            # Service indicates the symbol was not added (duplicate or validation failure)
            raise HTTPException(status_code=400, detail="Failed to add symbol to watchlist")
        return {"message": f"{request.symbol} added to watchlist"}
    except HTTPException:
        # propagate intended HTTP errors
        raise
    except Exception as e:
        logger.error(f"Error adding {request.symbol} to watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(
    symbol: str,
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Remove symbol from watchlist"""
    try:
        success = await market_data_service.remove_from_watchlist(symbol)
        if not success:
            raise HTTPException(status_code=404, detail="Symbol not found in watchlist")
        return {"message": f"{symbol} removed from watchlist"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing {symbol} from watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_market_data_config(
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """Return whether Polygon and AlphaVantage providers are configured in the running service."""
    try:
        poly_key = getattr(market_data_service.polygon, 'api_key', None)
        av_key = getattr(market_data_service.alpha_vantage, 'api_key', None)
        return {
            "polygon_configured": bool(poly_key),
            "alpha_vantage_configured": bool(av_key)
        }
    except Exception as e:
        logger.exception("Error getting market data config")
        raise HTTPException(status_code=500, detail=str(e))
