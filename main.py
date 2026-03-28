"""
Main FastAPI application for Algorithmic Trading System
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
import uvicorn
import asyncio
from typing import List
import json
from datetime import datetime

from app.api import trading, market_data, strategies
from app.api import tools
from app.core.config import settings
from app.core.logger import logger
from datetime import datetime, timedelta
from app.services import watchlist_sync

# Initialize FastAPI app
app = FastAPI(
    title="Algorithmic Trading System",
    description="Automated trading system with IBKR TWS integration",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Remove disconnected connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Include API routers
app.include_router(trading.router, prefix="/api/trading", tags=["trading"])
app.include_router(market_data.router, prefix="/api/market-data", tags=["market-data"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(tools.router, prefix="", tags=["tools"])

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await manager.send_personal_message(
                    json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}),
                    websocket
                )
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting Algorithmic Trading System...")
    # Initialize trading services, market data connections, etc.
    # Restore persisted auto-sync state and start background sync manager if needed
    try:
        default_interval = getattr(settings, 'watchlist_sync_minutes', 30)
        # run restore in background without blocking startup
        try:
            asyncio.create_task(watchlist_sync.restore_and_start(default_interval))
            logger.info('Triggered watchlist_sync.restore_and_start')
        except Exception as e:
            logger.error(f'Failed to schedule watchlist restore: {e}')
    except Exception as e:
        logger.error(f"Failed to start watchlist sync restore: {e}")
    
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Algorithmic Trading System...")
    # Cleanup connections, save state, etc.
    # Cancel background sync task
    # Stop persisted background sync manager
    try:
        await watchlist_sync.stop()
    except Exception:
        pass

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
