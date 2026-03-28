"""
Strategy service for managing trading strategies
"""
import asyncio
from typing import List, Optional
from datetime import datetime
import uuid

from app.core.logger import logger
from app.models.strategies import Strategy, StrategyExecution, StrategyPerformance, StrategyStatus
from app.strategies.macd_strategy import MACDStrategy
from app.services.market_data_service import MarketDataService
from app.core.strategy_persistence import StrategyPersistence

class StrategyService:
    def __init__(self):
        self.strategies: List[Strategy] = []
        self.executions: List[StrategyExecution] = []
        self.running_strategies = set()
        
        # Initialize strategy implementations
        self.macd_strategy = MACDStrategy()
        self.market_data_service = MarketDataService()
        
        # Initialize persistence
        self.persistence = StrategyPersistence()
        
        # Load existing strategies and executions
        self._load_data()
    
    def _load_data(self):
        """Load strategies and executions from disk"""
        try:
            self.strategies = self.persistence.load_strategies()
            self.executions = self.persistence.load_executions()
            
            # Restore running strategies
            for strategy in self.strategies:
                if strategy.status == StrategyStatus.RUNNING:
                    self.running_strategies.add(strategy.id)
            
            logger.info(f"Loaded {len(self.strategies)} strategies and {len(self.executions)} executions")
            
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")
    
    def _save_strategies(self):
        """Save strategies to disk"""
        try:
            self.persistence.save_strategies(self.strategies)
        except Exception as e:
            logger.error(f"Error saving strategies: {str(e)}")
    
    def _save_executions(self):
        """Save executions to disk"""
        try:
            self.persistence.save_executions(self.executions)
        except Exception as e:
            logger.error(f"Error saving executions: {str(e)}")
    
    def _save_single_strategy(self, strategy: Strategy):
        """Save a single strategy to disk"""
        try:
            self.persistence.save_single_strategy(strategy)
        except Exception as e:
            logger.error(f"Error saving strategy {strategy.id}: {str(e)}")
        
    async def get_strategies(self) -> List[Strategy]:
        """Get all trading strategies"""
        return self.strategies
    
    async def create_macd_strategy(
        self,
        name: str,
        symbols: List[str],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        enabled: bool = True
    ) -> Strategy:
        """Create a MACD trading strategy"""
        try:
            strategy_id = str(uuid.uuid4())
            
            parameters = {
                "strategy_type": "MACD",
                "fast_period": fast_period,
                "slow_period": slow_period,
                "signal_period": signal_period,
                "min_bars": 50
            }
            
            strategy = Strategy(
                id=strategy_id,
                name=name,
                description=f"MACD Strategy for {', '.join(symbols)} - Fast: {fast_period}, Slow: {slow_period}, Signal: {signal_period}",
                parameters=parameters,
                symbols=symbols,
                status=StrategyStatus.STOPPED,
                enabled=enabled,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            self.strategies.append(strategy)
            self._save_single_strategy(strategy)
            logger.info(f"Created MACD strategy: {name} ({strategy_id}) for symbols: {symbols}")
            
            return strategy
            
        except Exception as e:
            logger.error(f"Error creating MACD strategy: {str(e)}")
            raise
    
    async def create_strategy(
        self,
        name: str,
        description: str,
        parameters: dict,
        symbols: List[str],
        enabled: bool = True
    ) -> Strategy:
        """Create a new trading strategy"""
        try:
            strategy_id = str(uuid.uuid4())
            
            strategy = Strategy(
                id=strategy_id,
                name=name,
                description=description,
                parameters=parameters,
                symbols=symbols,
                status=StrategyStatus.STOPPED,
                enabled=enabled,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            self.strategies.append(strategy)
            self._save_single_strategy(strategy)
            logger.info(f"Created strategy: {name} ({strategy_id})")
            
            return strategy
            
        except Exception as e:
            logger.error(f"Error creating strategy: {str(e)}")
            raise
    
    async def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """Get specific strategy by ID"""
        for strategy in self.strategies:
            if strategy.id == strategy_id:
                return strategy
        return None
    
    async def update_strategy(
        self,
        strategy_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        symbols: Optional[List[str]] = None,
        enabled: Optional[bool] = None
    ) -> Optional[Strategy]:
        """Update a trading strategy"""
        try:
            strategy = await self.get_strategy(strategy_id)
            if not strategy:
                return None
            
            # Update fields if provided
            if name is not None:
                strategy.name = name
            if description is not None:
                strategy.description = description
            if parameters is not None:
                strategy.parameters = parameters
            if symbols is not None:
                strategy.symbols = symbols
            if enabled is not None:
                strategy.enabled = enabled
            
            strategy.updated_at = datetime.now()
            
            logger.info(f"Updated strategy: {strategy_id}")
            return strategy
            
        except Exception as e:
            logger.error(f"Error updating strategy {strategy_id}: {str(e)}")
            raise
    
    async def delete_strategy(self, strategy_id: str) -> bool:
        """Delete a trading strategy"""
        try:
            # Stop strategy if running
            if strategy_id in self.running_strategies:
                await self.stop_strategy(strategy_id)
            
            # Remove from list and delete file
            for i, strategy in enumerate(self.strategies):
                if strategy.id == strategy_id:
                    del self.strategies[i]
                    self.persistence.delete_strategy_file(strategy_id)
                    self._save_strategies()  # Update the main strategies file
                    logger.info(f"Deleted strategy: {strategy_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting strategy {strategy_id}: {str(e)}")
            return False
    
    async def start_strategy(self, strategy_id: str) -> bool:
        """Start a trading strategy"""
        try:
            strategy = await self.get_strategy(strategy_id)
            if not strategy:
                return False
            
            if not strategy.enabled:
                logger.warning(f"Cannot start disabled strategy: {strategy_id}")
                return False
            
            # Start strategy
            strategy.status = StrategyStatus.RUNNING
            strategy.started_at = datetime.now()
            strategy.updated_at = datetime.now()
            
            self.running_strategies.add(strategy_id)
            self._save_single_strategy(strategy)
            
            # Start strategy-specific analysis if MACD
            if strategy.parameters.get("strategy_type") == "MACD":
                asyncio.create_task(self._run_macd_strategy(strategy))
            
            logger.info(f"Started strategy: {strategy.name} ({strategy_id})")
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting strategy {strategy_id}: {str(e)}")
            return False
    
    async def _run_macd_strategy(self, strategy: Strategy):
        """Run MACD strategy analysis loop"""
        try:
            while strategy.id in self.running_strategies:
                for symbol in strategy.symbols:
                    try:
                        # Analyze symbol with MACD
                        execution = await self.macd_strategy.analyze_symbol(
                            symbol, self.market_data_service
                        )
                        
                        if execution:
                            # Update execution with strategy ID
                            execution.strategy_id = strategy.id
                            self.executions.append(execution)
                            self._save_executions()
                            
                            logger.info(f"MACD execution for {symbol}: {execution.action} - {execution.reason}")
                    
                    except Exception as e:
                        logger.error(f"Error analyzing {symbol} in MACD strategy: {str(e)}")
                
                # Wait before next analysis (5 minutes)
                await asyncio.sleep(300)
                
        except Exception as e:
            logger.error(f"Error in MACD strategy loop: {str(e)}")
            strategy.status = StrategyStatus.ERROR
    
    async def stop_strategy(self, strategy_id: str) -> bool:
        """Stop a trading strategy"""
        try:
            strategy = await self.get_strategy(strategy_id)
            if not strategy:
                return False
            
            # Stop strategy
            strategy.status = StrategyStatus.STOPPED
            strategy.stopped_at = datetime.now()
            strategy.updated_at = datetime.now()
            
            self.running_strategies.discard(strategy_id)
            self._save_single_strategy(strategy)
            
            logger.info(f"Stopped strategy: {strategy.name} ({strategy_id})")
            
            return True
            
        except Exception as e:
            logger.error(f"Error stopping strategy {strategy_id}: {str(e)}")
            return False
    
    async def get_strategy_executions(self, strategy_id: str, limit: int = 100) -> List[StrategyExecution]:
        """Get strategy execution history"""
        executions = [
            execution for execution in self.executions
            if execution.strategy_id == strategy_id
        ]
        return executions[-limit:] if limit else executions
    
    async def get_strategy_performance(self, strategy_id: str) -> Optional[StrategyPerformance]:
        """Get strategy performance metrics"""
        try:
            strategy = await self.get_strategy(strategy_id)
            if not strategy:
                return None
            
            executions = await self.get_strategy_executions(strategy_id)
            
            if not executions:
                return StrategyPerformance(
                    strategy_id=strategy_id,
                    total_trades=0,
                    winning_trades=0,
                    losing_trades=0,
                    win_rate=0.0,
                    total_pnl=0.0,
                    max_drawdown=0.0,
                    start_date=strategy.created_at,
                    updated_at=datetime.now()
                )
            
            # Calculate performance metrics
            total_trades = len(executions)
            winning_trades = len([e for e in executions if e.action == "BUY" and e.price])
            losing_trades = total_trades - winning_trades
            win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
            
            # TODO: Calculate actual PnL and drawdown
            total_pnl = 0.0
            max_drawdown = 0.0
            
            return StrategyPerformance(
                strategy_id=strategy_id,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=win_rate,
                total_pnl=total_pnl,
                max_drawdown=max_drawdown,
                start_date=strategy.created_at,
                updated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error getting performance for strategy {strategy_id}: {str(e)}")
            return None
    
    async def get_strategy_status(self, strategy_id: str) -> Optional[dict]:
        """Get strategy status"""
        try:
            strategy = await self.get_strategy(strategy_id)
            if not strategy:
                return None
            
            executions = await self.get_strategy_executions(strategy_id, limit=1)
            last_execution = executions[0] if executions else None
            
            uptime = None
            if strategy.started_at:
                uptime = (datetime.now() - strategy.started_at).total_seconds()
            
            return {
                "strategy_id": strategy_id,
                "status": strategy.status,
                "last_execution": last_execution.timestamp if last_execution else None,
                "current_positions": [],  # TODO: Get actual positions
                "error_message": None,
                "uptime": uptime
            }
            
        except Exception as e:
            logger.error(f"Error getting status for strategy {strategy_id}: {str(e)}")
            return None
