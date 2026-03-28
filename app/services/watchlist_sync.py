"""Background watchlist sync manager.

Provides async start/stop/status for a single background task that refreshes
watchlist historical data periodically. Persists desired state to disk so it
can be restored on restart.
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Optional

from app.services.market_data_service import MarketDataService
from app.core.logger import logger


_state_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'watch_sync.json')
_task: Optional[asyncio.Task] = None
_svc: Optional[MarketDataService] = None
_interval_minutes: int = 0
_last_run_at: Optional[str] = None
_lock = asyncio.Lock()


def _persist_state(enabled: bool, interval_minutes: int, last_run_at: Optional[str] = None):
    try:
        os.makedirs(os.path.dirname(_state_path), exist_ok=True)
        with open(_state_path, 'w') as f:
            json.dump({
                'enabled': enabled,
                'interval_minutes': interval_minutes,
                'last_run_at': last_run_at
            }, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to persist watch_sync state: {e}")


def _read_persisted():
    if not os.path.exists(_state_path):
        return None
    try:
        with open(_state_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read persisted watch_sync state: {e}")
        return None


async def _sync_loop(interval_minutes: int):
    global _last_run_at
    while True:
        try:
            if _svc is None:
                logger.error('Watchlist sync service not initialized')
            else:
                watch = await _svc.get_watchlist()
                for w in watch:
                    try:
                        await _svc.get_historical_data(
                            symbol=w.symbol,
                            timeframe='1min',
                            start_date=datetime.now() - __import__('datetime').timedelta(days=1),
                            end_date=datetime.now(),
                            limit=500
                        )
                    except Exception as e:
                        logger.debug(f"Failed refresh for {w.symbol}: {e}")
                _last_run_at = datetime.now().isoformat()
                _persist_state(True, interval_minutes, _last_run_at)
        except asyncio.CancelledError:
            logger.info('Watchlist sync loop cancelled')
            raise
        except Exception as e:
            logger.error(f"Error in watchlist sync loop: {e}")

        await asyncio.sleep(interval_minutes * 60)


async def start(interval_minutes: int) -> bool:
    """Start the background sync if not already running. Returns True if started or already running."""
    global _task, _svc, _interval_minutes
    async with _lock:
        if _task and not _task.done():
            # already running; update interval if different by restarting
            if _interval_minutes != interval_minutes:
                await stop()
            else:
                return True

        _svc = MarketDataService()
        _interval_minutes = interval_minutes
        _task = asyncio.create_task(_sync_loop(interval_minutes))
        _persist_state(True, interval_minutes, _last_run_at)
        logger.info(f"Started watchlist sync every {interval_minutes} minutes")
        return True


async def stop() -> bool:
    """Stop the background sync if running."""
    global _task
    async with _lock:
        if not _task:
            return True
        try:
            _task.cancel()
            await _task
        except Exception:
            pass
        _task = None
        _persist_state(False, _interval_minutes, _last_run_at)
        logger.info('Stopped watchlist sync')
        return True


def status() -> dict:
    return {
        'enabled': bool(_task and not _task.done()),
        'interval_minutes': _interval_minutes,
        'last_run_at': _last_run_at
    }


async def restore_and_start(default_interval: int = 30):
    """Restore persisted state and start sync if enabled, otherwise start with default if no persisted state."""
    p = _read_persisted()
    if p:
        enabled = bool(p.get('enabled'))
        interval = int(p.get('interval_minutes', default_interval))
        if enabled:
            await start(interval)
            return

    # No persisted enabled state; if default interval > 0 start with that
    if default_interval and default_interval > 0:
        await start(default_interval)
