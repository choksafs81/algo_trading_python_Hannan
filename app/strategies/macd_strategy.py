"""
MACD (Moving Average Convergence Divergence) Trading Strategy
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import asyncio

from app.core.logger import logger
from app.models.market_data import Bar, Quote
from app.models.strategies import StrategyExecution
from app.services.market_data_service import MarketDataService

class MACDStrategy:
    """
    MACD Trading Strategy Implementation
    
    MACD Strategy Logic:
    1. Calculate MACD Line = EMA(12) - EMA(26)
    2. Calculate Signal Line = EMA(9) of MACD Line
    3. Calculate Histogram = MACD Line - Signal Line
    
    Trading Signals:
    - BUY: MACD Line crosses above Signal Line (bullish crossover)
    - SELL: MACD Line crosses below Signal Line (bearish crossover)
    - Additional filters: MACD above/below zero line, histogram momentum
    """
    
    def __init__(self, 
                 fast_period: int = 12,
                 slow_period: int = 26, 
                 signal_period: int = 9,
                 min_bars: int = 50):
        """
        Initialize MACD Strategy
        
        Args:
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal line EMA period (default: 9)
            min_bars: Minimum bars required for calculation (default: 50)
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.min_bars = min_bars
        
        # Strategy state
        self.last_signals = {}  # Track last signal for each symbol
        self.position_data = {}  # Track positions and MACD data
        
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return [None] * len(prices)
        
        ema = [None] * len(prices)
        multiplier = 2 / (period + 1)
        
        # First EMA value is SMA
        ema[period - 1] = sum(prices[:period]) / period
        
        # Calculate subsequent EMA values
        for i in range(period, len(prices)):
            ema[i] = (prices[i] * multiplier) + (ema[i - 1] * (1 - multiplier))
        
        return ema
    
    def calculate_macd(self, prices: List[float]) -> Tuple[List[float], List[float], List[float]]:
        """
        Calculate MACD indicators
        
        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        if len(prices) < self.slow_period + self.signal_period:
            return [None] * len(prices), [None] * len(prices), [None] * len(prices)
        
        # Calculate EMAs
        fast_ema = self.calculate_ema(prices, self.fast_period)
        slow_ema = self.calculate_ema(prices, self.slow_period)
        
        # Calculate MACD line
        macd_line = []
        for i in range(len(prices)):
            if fast_ema[i] is not None and slow_ema[i] is not None:
                macd_line.append(fast_ema[i] - slow_ema[i])
            else:
                macd_line.append(None)
        
        # Calculate signal line (EMA of MACD line)
        macd_values = [x for x in macd_line if x is not None]
        if len(macd_values) < self.signal_period:
            signal_line = [None] * len(macd_line)
        else:
            signal_line = self.calculate_ema(macd_values, self.signal_period)
            # Pad with None values to match original length
            signal_line = [None] * (len(macd_line) - len(signal_line)) + signal_line
        
        # Calculate histogram
        histogram = []
        for i in range(len(macd_line)):
            if macd_line[i] is not None and signal_line[i] is not None:
                histogram.append(macd_line[i] - signal_line[i])
            else:
                histogram.append(None)
        
        return macd_line, signal_line, histogram
    
    def generate_signal(self, symbol: str, bars: List[Bar]) -> Optional[StrategyExecution]:
        """
        Generate trading signal based on MACD analysis
        
        Args:
            symbol: Trading symbol
            bars: Historical price bars
            
        Returns:
            StrategyExecution object if signal generated, None otherwise
        """
        try:
            if len(bars) < self.min_bars:
                logger.warning(f"Insufficient data for {symbol}: {len(bars)} bars (need {self.min_bars})")
                return None
            
            # Extract closing prices
            prices = [bar.close for bar in bars]
            
            # Calculate MACD indicators
            macd_line, signal_line, histogram = self.calculate_macd(prices)
            
            # Need at least 2 valid MACD values to detect crossover
            valid_macd = [x for x in macd_line if x is not None]
            valid_signal = [x for x in signal_line if x is not None]
            
            if len(valid_macd) < 2 or len(valid_signal) < 2:
                logger.warning(f"Insufficient MACD data for {symbol}")
                return None
            
            # Get current and previous values
            current_macd = valid_macd[-1]
            previous_macd = valid_macd[-2]
            current_signal = valid_signal[-1]
            previous_signal = valid_signal[-2]
            current_histogram = histogram[-1] if histogram[-1] is not None else 0
            
            # Store MACD data for this symbol
            self.position_data[symbol] = {
                'macd_line': current_macd,
                'signal_line': current_signal,
                'histogram': current_histogram,
                'last_update': datetime.now()
            }
            
            # Determine signal
            signal = None
            reason = ""
            
            # Bullish crossover: MACD crosses above signal line
            if (previous_macd <= previous_signal and 
                current_macd > current_signal and 
                current_macd > 0):  # MACD above zero line
                signal = "BUY"
                reason = f"MACD bullish crossover: {current_macd:.4f} > {current_signal:.4f}, MACD above zero"
            
            # Bearish crossover: MACD crosses below signal line
            elif (previous_macd >= previous_signal and 
                  current_macd < current_signal and 
                  current_macd < 0):  # MACD below zero line
                signal = "SELL"
                reason = f"MACD bearish crossover: {current_macd:.4f} < {current_signal:.4f}, MACD below zero"
            
            # Additional momentum signals
            elif (current_macd > current_signal and 
                  current_histogram > 0 and 
                  current_macd > 0 and
                  symbol not in self.last_signals):
                signal = "BUY"
                reason = f"MACD momentum: {current_macd:.4f} > {current_signal:.4f}, histogram positive"
            
            elif (current_macd < current_signal and 
                  current_histogram < 0 and 
                  current_macd < 0 and
                  symbol not in self.last_signals):
                signal = "SELL"
                reason = f"MACD momentum: {current_macd:.4f} < {current_signal:.4f}, histogram negative"
            
            # Generate execution if signal found
            if signal:
                # Avoid duplicate signals
                last_signal = self.last_signals.get(symbol)
                if (last_signal and 
                    last_signal['action'] == signal and 
                    (datetime.now() - last_signal['timestamp']).seconds < 300):  # 5 minutes
                    return None
                
                execution = StrategyExecution(
                    id=f"macd_{symbol}_{int(datetime.now().timestamp())}",
                    strategy_id="macd_strategy",
                    symbol=symbol,
                    action=signal,
                    quantity=100,  # Default quantity
                    price=bars[-1].close,
                    reason=reason,
                    timestamp=datetime.now()
                )
                
                # Update last signal
                self.last_signals[symbol] = {
                    'action': signal,
                    'timestamp': datetime.now(),
                    'macd': current_macd,
                    'signal': current_signal,
                    'histogram': current_histogram
                }
                
                logger.info(f"MACD Signal for {symbol}: {signal} - {reason}")
                return execution
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating MACD signal for {symbol}: {str(e)}")
            return None
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information and parameters"""
        return {
            "name": "MACD Strategy",
            "description": "Moving Average Convergence Divergence trading strategy",
            "parameters": {
                "fast_period": self.fast_period,
                "slow_period": self.slow_period,
                "signal_period": self.signal_period,
                "min_bars": self.min_bars
            },
            "symbols": list(self.position_data.keys()),
            "last_signals": self.last_signals,
            "position_data": self.position_data
        }
    
    async def analyze_symbol(self, symbol: str, market_data_service: MarketDataService) -> Optional[StrategyExecution]:
        """
        Analyze a symbol and generate trading signal
        
        Args:
            symbol: Symbol to analyze
            market_data_service: Market data service instance
            
        Returns:
            StrategyExecution if signal generated, None otherwise
        """
        try:
            # Get historical data (last 100 bars, 1-minute intervals)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)  # Get enough data
            
            bars = await market_data_service.get_historical_data(
                symbol=symbol,
                timeframe="1min",
                start_date=start_date,
                end_date=end_date,
                limit=100
            )
            
            if not bars:
                logger.warning(f"No historical data available for {symbol}")
                return None
            
            # Generate signal
            return self.generate_signal(symbol, bars)
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol} with MACD strategy: {str(e)}")
            return None



