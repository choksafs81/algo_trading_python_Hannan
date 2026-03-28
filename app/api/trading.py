"""
Trading API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.logger import logger
from app.services.trading_service import TradingService
from app.models.trading import Order, Position, Trade
from app.order_store import list_mappings
from app.services.ibkr_service import IBAPI_AVAILABLE
from app.services.ibkr_service import ibkr_service

router = APIRouter()

# Dependency to get trading service
def get_trading_service():
    return TradingService()

class OrderRequest(BaseModel):
    symbol: str
    quantity: int
    order_type: str  # "BUY" or "SELL"
    price: Optional[float] = None
    stop_price: Optional[float] = None

class OrderResponse(BaseModel):
    order_id: str
    status: str
    message: str

@router.post("/orders", response_model=OrderResponse)
async def place_order(
    order: OrderRequest,
    trading_service: TradingService = Depends(get_trading_service)
):
    """Place a new trading order"""
    try:
        logger.info(f"Placing order: {order.symbol} {order.order_type} {order.quantity}")
        
        # Place order through trading service
        order_id = await trading_service.place_order(
            symbol=order.symbol,
            quantity=order.quantity,
            order_type=order.order_type,
            price=order.price,
            stop_price=order.stop_price
        )
        
        return OrderResponse(
            order_id=order_id,
            status="submitted",
            message=f"Order placed successfully for {order.symbol}"
        )
        
    except Exception as e:
        logger.error(f"Error placing order: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/orders", response_model=List[Order])
async def get_orders(
    trading_service: TradingService = Depends(get_trading_service)
):
    """Get all orders"""
    try:
        orders = await trading_service.get_orders()
        return orders
    except Exception as e:
        logger.error(f"Error getting orders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/mappings")
async def get_order_mappings():
    """Return persisted mappings between app order ids and IB numeric ids"""
    try:
        mappings = list_mappings()
        return mappings
    except Exception as e:
        logger.error(f"Error getting order mappings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/preview")
async def preview_order(
    order: OrderRequest,
    trading_service: TradingService = Depends(get_trading_service)
):
    """Build an IB Order object for this request and return a small snapshot
    of the attributes that would be sent to IB (diagnostic only). This does
    not transmit anything to IB and is safe to call.
    """
    try:
        if not IBAPI_AVAILABLE:
            raise HTTPException(status_code=400, detail="IBAPI not available in this environment")

        # Build a minimal IB Order similarly to the service but don't send it
        from ibapi.order import Order as IBOrder

        ib_order = IBOrder()
        # side
        ib_order.action = order.order_type if False else ("BUY" if order.quantity > 0 else "SELL")
        # quantity
        ib_order.totalQuantity = abs(order.quantity)
        # order type
        if order.price is not None:
            ib_order.orderType = "LMT"
            ib_order.lmtPrice = float(order.price)
        else:
            ib_order.orderType = "MKT"

        # safe defaults
        try:
            if hasattr(ib_order, 'tif'):
                setattr(ib_order, 'tif', getattr(ib_order, 'tif', 'DAY'))
        except Exception:
            pass
        try:
            if hasattr(ib_order, 'transmit'):
                setattr(ib_order, 'transmit', True)
        except Exception:
            pass

        # Known problematic flags
        for f in ('eTradeOnly', 'firmQuoteOnly', 'notHeld'):
            try:
                if hasattr(ib_order, f):
                    setattr(ib_order, f, False)
            except Exception:
                pass

        # Serialize a small snapshot of attributes
        names = [n for n in dir(ib_order) if not n.startswith('__')]
        snapshot = {}
        for n in names:
            if n.startswith('_'):
                continue
            try:
                v = getattr(ib_order, n)
                # limit to simple serializable types
                if isinstance(v, (str, int, float, bool)) or v is None:
                    snapshot[n] = v
                else:
                    snapshot[n] = str(type(v))
            except Exception:
                snapshot[n] = '<unreadable>'

        # Return a limited sample to keep response small
        keys = list(snapshot.keys())[:60]
        limited = {k: snapshot[k] for k in keys}
        return {"ib_order_snapshot": limited}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error building IB order preview")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders/{order_id}", response_model=Order)
async def get_order(
    order_id: str,
    trading_service: TradingService = Depends(get_trading_service)
):
    """Get specific order by ID"""
    try:
        order = await trading_service.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order
    except Exception as e:
        logger.error(f"Error getting order {order_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ib/status")
async def ib_status():
    """Return a small status summary for the IBKR connection used by the app."""
    try:
        svc = ibkr_service
        if not svc:
            raise HTTPException(status_code=503, detail="IB service not initialized")

        return {
            "connected": bool(getattr(svc, 'connected', False)),
            "host": getattr(svc, 'host', None),
            "port": getattr(svc, 'port', None),
            "client_id": getattr(svc, 'client_id', None),
            "next_order_id": getattr(svc, 'next_order_id', None),
            "last_error": getattr(svc, 'last_error', None),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error retrieving IB status")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: str,
    trading_service: TradingService = Depends(get_trading_service)
):
    """Cancel an order"""
    try:
        success = await trading_service.cancel_order(order_id)
        if not success:
            raise HTTPException(status_code=404, detail="Order not found or already filled")
        return {"message": "Order cancelled successfully"}
    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions", response_model=List[Position])
async def get_positions(
    trading_service: TradingService = Depends(get_trading_service)
):
    """Get current positions"""
    try:
        positions = await trading_service.get_positions()
        return positions
    except Exception as e:
        logger.error(f"Error getting positions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trades", response_model=List[Trade])
async def get_trades(
    trading_service: TradingService = Depends(get_trading_service)
):
    """Get trade history"""
    try:
        trades = await trading_service.get_trades()
        return trades
    except Exception as e:
        logger.error(f"Error getting trades: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account")
async def get_account_info(
    trading_service: TradingService = Depends(get_trading_service)
):
    """Get account information"""
    try:
        account_info = await trading_service.get_account_info()
        return account_info
    except Exception as e:
        logger.error(f"Error getting account info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
