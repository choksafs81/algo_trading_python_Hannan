"""
Trading strategies API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.logger import logger
from app.services.strategy_service import StrategyService
from app.models.strategies import Strategy, StrategyExecution, StrategyPerformance

router = APIRouter()

# Global strategy service instance
_strategy_service = None

def get_strategy_service():
    global _strategy_service
    if _strategy_service is None:
        _strategy_service = StrategyService()
    return _strategy_service

class StrategyRequest(BaseModel):
    name: str
    description: str
    parameters: dict
    symbols: List[str]
    enabled: bool = True

class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[dict] = None
    symbols: Optional[List[str]] = None
    enabled: Optional[bool] = None

class MACDStrategyRequest(BaseModel):
    name: str
    symbols: List[str]
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    enabled: bool = True

@router.get("/", response_model=List[Strategy])
async def get_strategies(
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Get all trading strategies"""
    try:
        strategies = await strategy_service.get_strategies()
        return strategies
    except Exception as e:
        logger.error(f"Error getting strategies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=Strategy)
async def create_strategy(
    strategy: StrategyRequest,
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Create a new trading strategy"""
    try:
        new_strategy = await strategy_service.create_strategy(
            name=strategy.name,
            description=strategy.description,
            parameters=strategy.parameters,
            symbols=strategy.symbols,
            enabled=strategy.enabled
        )
        return new_strategy
    except Exception as e:
        logger.error(f"Error creating strategy: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/macd", response_model=Strategy)
async def create_macd_strategy(
    request: MACDStrategyRequest,
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Create a MACD trading strategy"""
    try:
        strategy = await strategy_service.create_macd_strategy(
            name=request.name,
            symbols=request.symbols,
            fast_period=request.fast_period,
            slow_period=request.slow_period,
            signal_period=request.signal_period,
            enabled=request.enabled
        )
        return strategy
    except Exception as e:
        logger.error(f"Error creating MACD strategy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-macd/{symbol}")
async def test_macd_strategy(
    symbol: str,
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Test MACD strategy analysis for a specific symbol"""
    try:
        # Create a temporary MACD strategy instance for testing
        from app.strategies.macd_strategy import MACDStrategy
        from app.services.market_data_service import MarketDataService
        
        macd = MACDStrategy()
        market_data = MarketDataService()
        
        # Analyze the symbol
        execution = await macd.analyze_symbol(symbol, market_data)
        
        if execution:
            return {
                "symbol": symbol,
                "signal": execution.action,
                "reason": execution.reason,
                "price": execution.price,
                "timestamp": execution.timestamp,
                "macd_data": macd.position_data.get(symbol, {})
            }
        else:
            return {
                "symbol": symbol,
                "signal": "NO_SIGNAL",
                "reason": "No MACD signal generated",
                "macd_data": macd.position_data.get(symbol, {})
            }
            
    except Exception as e:
        logger.error(f"Error testing MACD strategy for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{strategy_id}", response_model=Strategy)
async def get_strategy(
    strategy_id: str,
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Get specific strategy by ID"""
    try:
        strategy = await strategy_service.get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return strategy
    except Exception as e:
        logger.error(f"Error getting strategy {strategy_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{strategy_id}", response_model=Strategy)
async def update_strategy(
    strategy_id: str,
    strategy_update: StrategyUpdateRequest,
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Update a trading strategy"""
    try:
        updated_strategy = await strategy_service.update_strategy(
            strategy_id=strategy_id,
            **strategy_update.dict(exclude_unset=True)
        )
        if not updated_strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return updated_strategy
    except Exception as e:
        logger.error(f"Error updating strategy {strategy_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: str,
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Delete a trading strategy"""
    try:
        success = await strategy_service.delete_strategy(strategy_id)
        if not success:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return {"message": "Strategy deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting strategy {strategy_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{strategy_id}/start")
async def start_strategy(
    strategy_id: str,
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Start a trading strategy"""
    try:
        success = await strategy_service.start_strategy(strategy_id)
        if not success:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return {"message": "Strategy started successfully"}
    except Exception as e:
        logger.error(f"Error starting strategy {strategy_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{strategy_id}/stop")
async def stop_strategy(
    strategy_id: str,
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Stop a trading strategy"""
    try:
        success = await strategy_service.stop_strategy(strategy_id)
        if not success:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return {"message": "Strategy stopped successfully"}
    except Exception as e:
        logger.error(f"Error stopping strategy {strategy_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{strategy_id}/executions", response_model=List[StrategyExecution])
async def get_strategy_executions(
    strategy_id: str,
    limit: int = 100,
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Get strategy execution history"""
    try:
        executions = await strategy_service.get_strategy_executions(strategy_id, limit)
        return executions
    except Exception as e:
        logger.error(f"Error getting executions for strategy {strategy_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{strategy_id}/performance", response_model=StrategyPerformance)
async def get_strategy_performance(
    strategy_id: str,
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Get strategy performance metrics"""
    try:
        performance = await strategy_service.get_strategy_performance(strategy_id)
        if not performance:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return performance
    except Exception as e:
        logger.error(f"Error getting performance for strategy {strategy_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{strategy_id}/status")
async def get_strategy_status(
    strategy_id: str,
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """Get strategy status"""
    try:
        status = await strategy_service.get_strategy_status(strategy_id)
        if not status:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return status
    except Exception as e:
        logger.error(f"Error getting status for strategy {strategy_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
