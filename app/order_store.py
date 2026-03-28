"""Simple JSON-backed order store for persisting order <-> IB id mappings."""
import json
import os
from threading import Lock
from typing import Optional, Dict, Any

from app.core.logger import logger

STORE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "orders.json")
_lock = Lock()

def _ensure_store_dir():
    d = os.path.dirname(STORE_PATH)
    os.makedirs(d, exist_ok=True)

def save_order_mapping(app_order_id: str, ib_order_id: Optional[int], meta: Optional[Dict[str, Any]] = None):
    """Save or update an order mapping in the JSON store."""
    _ensure_store_dir()
    with _lock:
        try:
            if os.path.exists(STORE_PATH):
                with open(STORE_PATH, 'r') as f:
                    data = json.load(f)
            else:
                data = {}
        except Exception:
            data = {}

        data[app_order_id] = {
            "ib_order_id": ib_order_id,
            "meta": meta or {},
        }

        try:
            with open(STORE_PATH, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to write order store: {e}")

def get_order_mapping(app_order_id: str) -> Optional[Dict[str, Any]]:
    _ensure_store_dir()
    with _lock:
        try:
            if not os.path.exists(STORE_PATH):
                return None
            with open(STORE_PATH, 'r') as f:
                data = json.load(f)
            return data.get(app_order_id)
        except Exception as e:
            logger.error(f"Failed to read order store: {e}")
            return None

def list_mappings() -> Dict[str, Any]:
    _ensure_store_dir()
    with _lock:
        try:
            if not os.path.exists(STORE_PATH):
                return {}
            with open(STORE_PATH, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Failed to list order store: {e}")
            return {}
