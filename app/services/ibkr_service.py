"""
IBKR TWS service for trading operations
"""
import asyncio
from typing import List, Optional
from datetime import datetime
import threading
import time

from app.core.logger import logger
from app.core.config import settings
from app.models.trading import Order, Position, Trade, AccountInfo

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.order import Order as IBOrder
    IBAPI_AVAILABLE = True
except ImportError:
    IBAPI_AVAILABLE = False
    logger.warning("IBAPI not available. Install with: pip install ibapi")

class IBKRService(EWrapper):
    def __init__(self):
        self.host = settings.ibkr_host
        self.port = settings.ibkr_port
        self.client_id = settings.ibkr_client_id
        self.connected = False
        self.api_thread = None
        self.next_order_id = None
        self._order_id_lock = threading.Lock()
        self._connect_lock = threading.Lock()
        # map IB order id -> threading.Event for acknowledgement
        self._order_events = {}
        # store last IB error message to surface to callers
        self.last_error = None
        # flag to indicate an IB error was received since last order attempt
        self._last_error_occurred = False
        
        if IBAPI_AVAILABLE:
            EWrapper.__init__(self)
            self.client = EClient(self)
        else:
            self.client = None
    
    async def connect(self) -> bool:
        """Connect to IBKR TWS"""
        try:
            if not IBAPI_AVAILABLE:
                logger.error("IBAPI not available. Please install ibapi package.")
                return False
            # Avoid concurrent connect attempts
            with self._connect_lock:
                # If already connected, no-op
                try:
                    if self.client and self.client.isConnected():
                        logger.info("IB client already connected")
                        self.connected = True
                        return True
                except Exception:
                    pass

                # Try connecting and, if we receive an IB error indicating the
                # configured client id is already in use (error 326), attempt a
                # small number of fallback client ids.
                max_attempts = 3
                base_client_id = int(self.client_id or 0)
                for attempt in range(max_attempts):
                    # reset last error flag before each attempt
                    self._last_error_occurred = False
                    self.last_error = None

                    candidate_id = base_client_id + attempt
                    logger.info(f"Connecting to IBKR TWS at {self.host}:{self.port} with client id {candidate_id}")

                    # (re)create client for this attempt
                    try:
                        self.client = EClient(self)
                    except Exception:
                        self.client = None
                        logger.error("Failed to create IB client instance")
                        return False

                    # Connect to TWS
                    try:
                        self.client.connect(self.host, self.port, candidate_id)
                    except Exception as e:
                        logger.error(f"Exception calling client.connect: {e}")
                        # try next id
                        continue

                    # Start API thread
                    self.api_thread = threading.Thread(target=self.client.run, daemon=True)
                    self.api_thread.start()

                    # Wait briefly for either nextValidId or an error to arrive
                    # Wait up to 6 seconds (short window to detect immediate errors)
                    timeout = 6
                    waited = 0
                    while self.next_order_id is None and not self._last_error_occurred and waited < timeout:
                        await asyncio.sleep(0.5)
                        waited += 0.5

                    # If we got the next order id, we're connected
                    if self.client.isConnected() and self.next_order_id is not None:
                        # record the effective client id in case it was changed
                        try:
                            self.client_id = candidate_id
                        except Exception:
                            pass
                        self.connected = True
                        logger.info("Successfully connected to IBKR TWS")
                        return True

                    # If an immediate error happened and it looks like client-id-in-use,
                    # try the next candidate id; otherwise break and fail
                    if self._last_error_occurred and self.last_error and '326' in self.last_error:
                        logger.warning(f"Client id {candidate_id} appears in use (IB: {self.last_error}), trying next id")
                        try:
                            # attempt to disconnect/cleanup before next try
                            if self.client:
                                self.client.disconnect()
                        except Exception:
                            pass
                        # clear next_order_id so next attempt waits fresh
                        self.next_order_id = None
                        continue
                    else:
                        # no immediate client-id error; give up
                        break

                logger.error("Failed to connect to IBKR TWS")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to IBKR TWS: {str(e)}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from IBKR TWS"""
        try:
            logger.info("Disconnecting from IBKR TWS")
            if self.client and self.connected:
                self.client.disconnect()
            self.connected = False
        except Exception as e:
            logger.error(f"Error disconnecting from IBKR TWS: {str(e)}")
    
    # IBKR API Callbacks
    def connectAck(self):
        """Called when connection is acknowledged"""
        logger.info("IBKR TWS connection acknowledged")

    def nextValidId(self, orderId: int):
        """Callback from IB indicating the next valid order ID."""
        try:
            self.next_order_id = orderId
            logger.info(f"Received nextValidId from IB: {orderId}")
        except Exception as e:
            logger.error(f"Error in nextValidId: {e}")
    
    def connectionClosed(self):
        """Called when connection is closed"""
        logger.info("IBKR TWS connection closed")
        self.connected = False
    
    def error(self, reqId, errorCode, errorString):
        """Called when an error occurs"""
        # Normalize error code to int when possible
        try:
            code_int = int(errorCode)
        except Exception:
            code_int = None

        msg = f"{errorCode}: {errorString}"

        # Some IB error codes are informational (market data / sec-def farm msgs)
        # and should not be treated as order/connection failures. Ignore those
        # for the purposes of waking order events or marking last_error.
        informational_codes = {2103, 2104, 2106, 2158}

        try:
            if code_int in informational_codes:
                # Log as info to avoid confusing clients with spurious failures
                logger.info(f"IBKR Info {msg}")
                return

            # For non-informational errors, store last_error and mark a failure
            self.last_error = msg
            self._last_error_occurred = True

            # Only wake order events for errors that likely relate to orders or
            # connection/client-id issues. Waking all events on every unrelated
            # error leads to false-positive acknowledgements.
            order_related_codes = {201, 202, 326, 10268}
            if code_int is None or code_int in order_related_codes or 'Order' in errorString or 'order' in errorString.lower():
                for ev in list(self._order_events.values()):
                    try:
                        ev.set()
                    except Exception:
                        pass

        except Exception:
            pass

        logger.error(f"IBKR Error {msg}")

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId,
                    parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        """Order status callback"""
        logger.info(f"OrderStatus. ID: {orderId}, Status: {status}, Filled: {filled}, Remaining: {remaining}, AvgFillPrice: {avgFillPrice}")
        # If we have an event waiting for this order id, set it on a non-error status
        try:
            ev = self._order_events.get(orderId)
            if ev and status and status.upper() not in ("API_PENDING", "PENDING_SUBMIT"):
                ev.set()
        except Exception:
            pass

    def openOrder(self, orderId, contract, order, orderState):
        """Open order callback"""
        logger.info(f"OpenOrder. ID: {orderId}, {contract.symbol} {order.action} {order.totalQuantity} @ {getattr(order,'lmtPrice',None)}")
        try:
            ev = self._order_events.get(orderId)
            if ev:
                ev.set()
        except Exception:
            pass
    
    async def place_order(self, order: Order) -> bool:
        """Place order through IBKR"""
        try:
            if not self.connected:
                await self.connect()
                
            if not IBAPI_AVAILABLE or not self.client:
                logger.error("IBAPI not available. Cannot place real orders.")
                return False

            logger.info(f"Placing order {order.id} for {order.symbol}")

            # clear last IB error markers for this attempt so we don't surface
            # stale informational messages from earlier connections
            try:
                self.last_error = None
                self._last_error_occurred = False
            except Exception:
                pass

            # Build contract (simple equity contract)
            contract = Contract()
            contract.symbol = order.symbol
            contract.secType = "STK"
            contract.currency = "USD"
            contract.exchange = "SMART"

            # Build IB order using a conservative whitelist to avoid setting
            # attributes that may be unsupported by the connected IB system.
            def _build_ib_order(app_order: Order):
                ib_order = IBOrder()
                # Basic fields
                try:
                    ib_order.action = app_order.side.value if hasattr(app_order.side, 'value') else ("BUY" if app_order.quantity > 0 else "SELL")
                except Exception:
                    ib_order.action = "BUY" if app_order.quantity > 0 else "SELL"
                try:
                    ib_order.totalQuantity = abs(app_order.quantity)
                except Exception:
                    ib_order.totalQuantity = abs(app_order.quantity)

                # Order type and price
                if app_order.price is not None:
                    try:
                        ib_order.orderType = "LMT"
                        ib_order.lmtPrice = float(app_order.price)
                    except Exception:
                        ib_order.orderType = "LMT"
                else:
                    try:
                        ib_order.orderType = "MKT"
                    except Exception:
                        ib_order.orderType = "MKT"

                # Safe defaults (whitelist)
                try:
                    if hasattr(ib_order, 'tif'):
                        setattr(ib_order, 'tif', 'DAY')
                except Exception:
                    pass
                try:
                    if hasattr(ib_order, 'transmit'):
                        setattr(ib_order, 'transmit', True)
                except Exception:
                    pass
                try:
                    if hasattr(ib_order, 'account'):
                        setattr(ib_order, 'account', '')
                except Exception:
                    pass
                try:
                    if hasattr(ib_order, 'outsideRth'):
                        setattr(ib_order, 'outsideRth', False)
                except Exception:
                    pass

                # Deliberately do NOT set attributes like eTradeOnly/firmQuoteOnly
                # unless we must; if they exist and are True by default we will
                # explicitly set them False to avoid server-side rejections.
                try:
                    if hasattr(ib_order, 'eTradeOnly'):
                        setattr(ib_order, 'eTradeOnly', False)
                except Exception:
                    pass

                return ib_order

            ib_order = _build_ib_order(order)

            logger.debug("IBOrder constructed using whitelist")

            # Obtain an order id
            with self._order_id_lock:
                if self.next_order_id is None:
                    logger.error("No next order id available; cannot place order")
                    return False
                order_id = self.next_order_id
                # increment for next time
                self.next_order_id += 1

            logger.debug(f"Assigned order_id {order_id}")

            # Set only the minimal, common IBOrder attributes. Avoid any
            # aggressive introspection/deletion of attributes because attribute
            # access on IBOrder can trigger unexpected behavior in some ibapi
            # versions. Some ibapi implementations access boolean flags that
            # may not exist on the Order instance; proactively set a few safe
            # defaults to prevent AttributeError during serialization. We
            # intentionally avoid setting attributes known to cause IB to
            # reject (for example `eTradeOnly`).
            try:
                # time-in-force and transmit are common safe defaults
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

                # Proactively ensure a few boolean/string flags exist so that
                # ibapi's internal serialization doesn't raise AttributeError.
                # Keep these conservative and safe.
                try:
                    if not hasattr(ib_order, 'outsideRth'):
                        setattr(ib_order, 'outsideRth', False)
                except Exception:
                    pass
                try:
                    if not hasattr(ib_order, 'ocaGroup'):
                        setattr(ib_order, 'ocaGroup', '')
                except Exception:
                    pass
                try:
                    if not hasattr(ib_order, 'account'):
                        setattr(ib_order, 'account', '')
                except Exception:
                    pass
                # Known IB order attributes that have historically caused
                # rejections in some environments — ensure conservative defaults.
                problematic_flags = ['eTradeOnly', 'firmQuoteOnly', 'notHeld']
                for f in problematic_flags:
                    try:
                        if hasattr(ib_order, f):
                            setattr(ib_order, f, False)
                    except Exception:
                        pass
            except Exception:
                # keep this non-fatal; we'll still try to place the order
                logger.debug('Non-fatal error when setting minimal IBOrder attributes')

            # Place the order and wait for acknowledgement
            try:
                logger.debug(f"About to placeOrder: ib_order type={type(ib_order)} module={type(ib_order).__module__}")
                logger.debug(f"About to placeOrder: app order type={type(order)} module={type(order).__module__}")
                try:
                    has_outside = hasattr(ib_order, 'outsideRth')
                    logger.debug(f"IBOrder has outsideRth: {has_outside}")
                    # small dir snapshot (first 40 names) for troubleshooting
                    try:
                        names = [n for n in dir(ib_order) if not n.startswith('__')]
                        logger.debug(f"IBOrder dir sample: {names[:40]}")
                    except Exception:
                        logger.debug("Failed to get IBOrder dir() sample")
                except Exception:
                    logger.debug("Failed to inspect IBOrder attributes")

                # Attempt to call placeOrder; if ibapi attempts to access an
                # IBOrder attribute that doesn't exist we may get an
                # AttributeError during serialization. In that case, set a safe
                # default for the missing attribute on the ib_order and retry
                # once. This makes the behavior robust across ibapi versions.
                place_attempts = 2
                placed = False
                for attempt in range(place_attempts):
                    try:
                        self.client.placeOrder(order_id, contract, ib_order)
                        placed = True
                        break
                    except AttributeError as ae:
                        # Parse attribute name from message like "'outsideRth'"
                        msg = str(ae)
                        import re
                        m = re.search(r"'([^']+)'", msg)
                        attr_name = m.group(1) if m else None
                        if attr_name:
                            logger.warning(f"IB Order serialization missing attribute '{attr_name}', setting default and retrying")
                            try:
                                # conservative defaults: booleans -> False, strings -> ''
                                default_val = False
                                # Heuristic: if name contains 'price' or 'group' or 'account', use empty string
                                if any(k in attr_name.lower() for k in ('price', 'group', 'account', 'id')):
                                    default_val = ''
                                setattr(ib_order, attr_name, default_val)
                                continue
                            except Exception:
                                # If we can't set it, break and surface original error
                                logger.exception(f"Failed to set dynamic IBOrder attribute {attr_name}")
                                break
                        else:
                            # unknown attribute name; re-raise to be handled below
                            raise
                    except Exception:
                        # re-raise for other exceptions to be handled below
                        raise

                if not placed:
                    logger.error(f"Failed to place order after retries for order id {order_id}")
                    return None

                logger.info(f"Sent placeOrder to IB (order id {order_id})")

                # Create an event and wait for openOrder/orderStatus acknowledgement
                ev = threading.Event()
                self._order_events[order_id] = ev
                # allow a bit more time for IB to respond on busy connections
                acknowledged = ev.wait(timeout=15)
                # cleanup
                try:
                    del self._order_events[order_id]
                except KeyError:
                    pass

                # If IB reported an error while we were waiting, treat as failure
                if acknowledged:
                    if self.last_error:
                        logger.error(f"IB reported an error during order submission: {self.last_error}")
                        return None
                    return order_id
                else:
                    logger.error(f"No acknowledgement for order {order_id} from IB within timeout")
                    return None
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                logger.error(f"Exception during IB order build/cleanup: {e}\n{tb}")
                return None
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Error placing order {order.id}: {e}\n{tb}")
            return False
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order through IBKR"""
        try:
            if not self.connected:
                await self.connect()
                
            # TODO: Implement actual order cancellation
            logger.info(f"Cancelling order {order_id}")
            
            # Simulate order cancellation
            await asyncio.sleep(0.1)
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {str(e)}")
            return False
    
    async def get_positions(self) -> List[Position]:
        """Get positions from IBKR"""
        try:
            if not self.connected:
                await self.connect()
                
            # TODO: Implement actual position retrieval
            logger.info("Getting positions from IBKR")
            
            # Return mock data for now
            return []
            
        except Exception as e:
            logger.error(f"Error getting positions: {str(e)}")
            return []
    
    async def get_trades(self) -> List[Trade]:
        """Get trades from IBKR"""
        try:
            if not self.connected:
                await self.connect()
                
            # TODO: Implement actual trade retrieval
            logger.info("Getting trades from IBKR")
            
            # Return mock data for now
            return []
            
        except Exception as e:
            logger.error(f"Error getting trades: {str(e)}")
            return []
    
    async def get_account_info(self) -> Optional[AccountInfo]:
        """Get account information from IBKR"""
        try:
            if not self.connected:
                await self.connect()
                
            # TODO: Implement actual account info retrieval
            logger.info("Getting account info from IBKR")
            
            # Return mock data for now
            return AccountInfo(
                account_id="DU123456",
                buying_power=100000.0,
                cash=50000.0,
                equity=75000.0,
                margin_used=25000.0,
                margin_available=75000.0,
                net_liquidation_value=75000.0,
                updated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error getting account info: {str(e)}")
            return None

# Module-level singleton to avoid multiple connections/client-id collisions
try:
    ibkr_service = IBKRService()
except Exception:
    # In case IBAPI is not available or initialization fails, create a placeholder
    ibkr_service = None

__all__ = ["IBKRService", "ibkr_service", "IBAPI_AVAILABLE"]
