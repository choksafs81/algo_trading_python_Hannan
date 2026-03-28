"""
Trading service for order management and execution
"""
import asyncio
from typing import List, Optional
from datetime import datetime
import uuid

from app.core.logger import logger
from app.models.trading import Order, Position, Trade, AccountInfo, OrderType, OrderSide, OrderStatus
from app.services.ibkr_service import IBKRService, ibkr_service
from app.order_store import save_order_mapping, get_order_mapping, list_mappings

class TradingService:
    def __init__(self):
        # Reuse the shared ibkr_service singleton when available to avoid
        # multiple simultaneous connections which can cause client-id collisions
        self.ibkr_service = ibkr_service if ibkr_service is not None else IBKRService()
        self.orders: List[Order] = []
        self.positions: List[Position] = []
        self.trades: List[Trade] = []
        
    async def place_order(
        self,
        symbol: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> str:
        """Place a new trading order"""
        try:
            order_id = str(uuid.uuid4())
            
            # Create order object
            order = Order(
                id=order_id,
                symbol=symbol,
                quantity=quantity,
                order_type=OrderType(order_type),
                side=OrderSide.BUY if quantity > 0 else OrderSide.SELL,
                price=price,
                stop_price=stop_price,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Place order through IBKR
            ib_order_id = await self.ibkr_service.place_order(order)

            # If initial attempt failed due connection or client-id issues, try reconnect and retry once
            if ib_order_id is None:
                logger.warning("Initial IB order placement failed; retrying after reconnect")
                await self.ibkr_service.connect()
                ib_order_id = await self.ibkr_service.place_order(order)

            if ib_order_id:
                order.status = OrderStatus.SUBMITTED
                # attach the IB numeric id to our order model
                try:
                    order.ib_id = int(ib_order_id)
                except Exception:
                    order.ib_id = None

                # persist mapping to disk for cross-reference later
                try:
                    save_order_mapping(order_id, order.ib_id, {"symbol": order.symbol, "quantity": order.quantity})
                except Exception:
                    logger.error("Failed to persist order mapping")

                self.orders.append(order)
                logger.info(f"Order placed successfully: {order_id} (IB id: {ib_order_id})")
                return order_id
            else:
                order.status = OrderStatus.REJECTED
                logger.error(f"Order rejected: {order_id}")
                # surface last IB error when available
                ib_err = None
                try:
                    ib_err = getattr(self.ibkr_service, 'last_error', None)
                except Exception:
                    ib_err = None
                if ib_err:
                    raise Exception(f"Order placement failed: {ib_err}")
                else:
                    raise Exception("Order placement failed")
                
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            raise
    
    async def get_orders(self) -> List[Order]:
        """Get all orders"""
        return self.orders
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get specific order by ID"""
        for order in self.orders:
            if order.id == order_id:
                return order
        return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            order = await self.get_order(order_id)
            if not order:
                return False
                
            if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                return False
                
            # Cancel through IBKR
            success = await self.ibkr_service.cancel_order(order_id)
            
            if success:
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now()
                logger.info(f"Order cancelled: {order_id}")
                return True
            else:
                logger.error(f"Failed to cancel order: {order_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {str(e)}")
            return False
    
    async def get_positions(self) -> List[Position]:
        """Get current positions"""
        try:
            # Get positions from IBKR
            positions = await self.ibkr_service.get_positions()
            self.positions = positions
            return positions
        except Exception as e:
            logger.error(f"Error getting positions: {str(e)}")
            return []
    
    async def get_trades(self) -> List[Trade]:
        """Get trade history"""
        try:
            # Get trades from IBKR
            trades = await self.ibkr_service.get_trades()
            self.trades = trades
            return trades
        except Exception as e:
            logger.error(f"Error getting trades: {str(e)}")
            return []
    
    async def get_account_info(self) -> Optional[AccountInfo]:
        """Get account information"""
        try:
            account_info = await self.ibkr_service.get_account_info()
            return account_info
        except Exception as e:
            logger.error(f"Error getting account info: {str(e)}")
            return None
