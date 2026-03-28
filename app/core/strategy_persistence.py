"""
Strategy persistence utilities for saving and loading strategies to/from disk
"""
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from app.core.logger import logger
from app.models.strategies import Strategy, StrategyExecution, StrategyStatus

class StrategyPersistence:
    """Handle saving and loading strategies to/from disk"""
    
    def __init__(self, strategies_dir: str = "strategies"):
        self.strategies_dir = Path(strategies_dir)
        self.strategies_dir.mkdir(exist_ok=True)
        
        # File paths
        self.strategies_file = self.strategies_dir / "strategies.json"
        self.executions_file = self.strategies_dir / "executions.json"
        
    def save_strategies(self, strategies: List[Strategy]) -> bool:
        """Save strategies to disk"""
        try:
            strategies_data = []
            for strategy in strategies:
                strategy_dict = {
                    "id": strategy.id,
                    "name": strategy.name,
                    "description": strategy.description,
                    "parameters": strategy.parameters,
                    "symbols": strategy.symbols,
                    "status": strategy.status.value,
                    "enabled": strategy.enabled,
                    "created_at": strategy.created_at.isoformat(),
                    "updated_at": strategy.updated_at.isoformat(),
                    "started_at": strategy.started_at.isoformat() if strategy.started_at else None,
                    "stopped_at": strategy.stopped_at.isoformat() if strategy.stopped_at else None
                }
                strategies_data.append(strategy_dict)
            
            with open(self.strategies_file, 'w') as f:
                json.dump(strategies_data, f, indent=2)
            
            logger.info(f"Saved {len(strategies)} strategies to {self.strategies_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving strategies: {str(e)}")
            return False
    
    def load_strategies(self) -> List[Strategy]:
        """Load strategies from disk"""
        try:
            strategies = []
            
            # First try to load from individual strategy files
            strategy_files = list(self.strategies_dir.glob("strategy_*.json"))
            if strategy_files:
                logger.info(f"Found {len(strategy_files)} individual strategy files")
                for strategy_file in strategy_files:
                    try:
                        with open(strategy_file, 'r') as f:
                            strategy_dict = json.load(f)
                        
                        strategy = Strategy(
                            id=strategy_dict["id"],
                            name=strategy_dict["name"],
                            description=strategy_dict["description"],
                            parameters=strategy_dict["parameters"],
                            symbols=strategy_dict["symbols"],
                            status=StrategyStatus(strategy_dict["status"]),
                            enabled=strategy_dict["enabled"],
                            created_at=datetime.fromisoformat(strategy_dict["created_at"]),
                            updated_at=datetime.fromisoformat(strategy_dict["updated_at"]),
                            started_at=datetime.fromisoformat(strategy_dict["started_at"]) if strategy_dict["started_at"] else None,
                            stopped_at=datetime.fromisoformat(strategy_dict["stopped_at"]) if strategy_dict["stopped_at"] else None
                        )
                        strategies.append(strategy)
                    except Exception as e:
                        logger.error(f"Error loading strategy from {strategy_file}: {str(e)}")
                        continue
                
                logger.info(f"Loaded {len(strategies)} strategies from individual files")
                return strategies
            
            # Fallback to main strategies file if it exists
            if self.strategies_file.exists():
                logger.info("Loading from main strategies file")
                with open(self.strategies_file, 'r') as f:
                    strategies_data = json.load(f)
                
                for strategy_dict in strategies_data:
                    try:
                        strategy = Strategy(
                            id=strategy_dict["id"],
                            name=strategy_dict["name"],
                            description=strategy_dict["description"],
                            parameters=strategy_dict["parameters"],
                            symbols=strategy_dict["symbols"],
                            status=StrategyStatus(strategy_dict["status"]),
                            enabled=strategy_dict["enabled"],
                            created_at=datetime.fromisoformat(strategy_dict["created_at"]),
                            updated_at=datetime.fromisoformat(strategy_dict["updated_at"]),
                            started_at=datetime.fromisoformat(strategy_dict["started_at"]) if strategy_dict["started_at"] else None,
                            stopped_at=datetime.fromisoformat(strategy_dict["stopped_at"]) if strategy_dict["stopped_at"] else None
                        )
                        strategies.append(strategy)
                    except Exception as e:
                        logger.error(f"Error loading strategy {strategy_dict.get('id', 'unknown')}: {str(e)}")
                        continue
                
                logger.info(f"Loaded {len(strategies)} strategies from {self.strategies_file}")
                return strategies
            
            logger.info("No strategy files found, returning empty list")
            return []
            
        except Exception as e:
            logger.error(f"Error loading strategies: {str(e)}")
            return []
    
    def save_executions(self, executions: List[StrategyExecution]) -> bool:
        """Save strategy executions to disk"""
        try:
            executions_data = []
            for execution in executions:
                execution_dict = {
                    "id": execution.id,
                    "strategy_id": execution.strategy_id,
                    "symbol": execution.symbol,
                    "action": execution.action,
                    "quantity": execution.quantity,
                    "price": execution.price,
                    "reason": execution.reason,
                    "timestamp": execution.timestamp.isoformat(),
                    "order_id": execution.order_id
                }
                executions_data.append(execution_dict)
            
            with open(self.executions_file, 'w') as f:
                json.dump(executions_data, f, indent=2)
            
            logger.info(f"Saved {len(executions)} executions to {self.executions_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving executions: {str(e)}")
            return False
    
    def load_executions(self) -> List[StrategyExecution]:
        """Load strategy executions from disk"""
        try:
            if not self.executions_file.exists():
                logger.info("No executions file found, returning empty list")
                return []
            
            with open(self.executions_file, 'r') as f:
                executions_data = json.load(f)
            
            executions = []
            for execution_dict in executions_data:
                try:
                    execution = StrategyExecution(
                        id=execution_dict["id"],
                        strategy_id=execution_dict["strategy_id"],
                        symbol=execution_dict["symbol"],
                        action=execution_dict["action"],
                        quantity=execution_dict["quantity"],
                        price=execution_dict["price"],
                        reason=execution_dict["reason"],
                        timestamp=datetime.fromisoformat(execution_dict["timestamp"]),
                        order_id=execution_dict["order_id"]
                    )
                    executions.append(execution)
                except Exception as e:
                    logger.error(f"Error loading execution {execution_dict.get('id', 'unknown')}: {str(e)}")
                    continue
            
            logger.info(f"Loaded {len(executions)} executions from {self.executions_file}")
            return executions
            
        except Exception as e:
            logger.error(f"Error loading executions: {str(e)}")
            return []
    
    def get_strategy_file_path(self, strategy_id: str) -> Path:
        """Get file path for a specific strategy"""
        return self.strategies_dir / f"strategy_{strategy_id}.json"
    
    def save_single_strategy(self, strategy: Strategy) -> bool:
        """Save a single strategy to its own file"""
        try:
            strategy_dict = {
                "id": strategy.id,
                "name": strategy.name,
                "description": strategy.description,
                "parameters": strategy.parameters,
                "symbols": strategy.symbols,
                "status": strategy.status.value,
                "enabled": strategy.enabled,
                "created_at": strategy.created_at.isoformat(),
                "updated_at": strategy.updated_at.isoformat(),
                "started_at": strategy.started_at.isoformat() if strategy.started_at else None,
                "stopped_at": strategy.stopped_at.isoformat() if strategy.stopped_at else None
            }
            
            file_path = self.get_strategy_file_path(strategy.id)
            with open(file_path, 'w') as f:
                json.dump(strategy_dict, f, indent=2)
            
            logger.info(f"Saved strategy {strategy.name} to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving strategy {strategy.id}: {str(e)}")
            return False
    
    def load_single_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """Load a single strategy from its file"""
        try:
            file_path = self.get_strategy_file_path(strategy_id)
            if not file_path.exists():
                return None
            
            with open(file_path, 'r') as f:
                strategy_dict = json.load(f)
            
            strategy = Strategy(
                id=strategy_dict["id"],
                name=strategy_dict["name"],
                description=strategy_dict["description"],
                parameters=strategy_dict["parameters"],
                symbols=strategy_dict["symbols"],
                status=StrategyStatus(strategy_dict["status"]),
                enabled=strategy_dict["enabled"],
                created_at=datetime.fromisoformat(strategy_dict["created_at"]),
                updated_at=datetime.fromisoformat(strategy_dict["updated_at"]),
                started_at=datetime.fromisoformat(strategy_dict["started_at"]) if strategy_dict["started_at"] else None,
                stopped_at=datetime.fromisoformat(strategy_dict["stopped_at"]) if strategy_dict["stopped_at"] else None
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Error loading strategy {strategy_id}: {str(e)}")
            return None
    
    def delete_strategy_file(self, strategy_id: str) -> bool:
        """Delete a strategy file"""
        try:
            file_path = self.get_strategy_file_path(strategy_id)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted strategy file {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting strategy file {strategy_id}: {str(e)}")
            return False
