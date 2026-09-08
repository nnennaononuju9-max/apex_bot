from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from .signal_generator import (
    get_signal_key,
    get_score,
    generate_free_signal,
    generate_vip_signal,
    mark_signal_posted,
)

logger = logging.getLogger("apex.engine")

_DELIVERED_SIGNAL_KEYS: set[str] = set()
_DELIVERED_LOCK = threading.Lock()


def is_signal_delivered(signal_key: str) -> bool:
    with _DELIVERED_LOCK:
        return signal_key in _DELIVERED_SIGNAL_KEYS


def mark_signal_delivered(signal_key: str) -> None:
    if not signal_key:
        return
    with _DELIVERED_LOCK:
        _DELIVERED_SIGNAL_KEYS.add(signal_key)


def remove_signal_from_cache(signal_key: str) -> None:
    with _DELIVERED_LOCK:
        _DELIVERED_SIGNAL_KEYS.discard(signal_key)


def delivered_signal_count() -> int:
    with _DELIVERED_LOCK:
        return len(_DELIVERED_SIGNAL_KEYS)


def clear_delivered_signals() -> None:
    with _DELIVERED_LOCK:
        _DELIVERED_SIGNAL_KEYS.clear()


def scan_free_market(symbol: str, interval: str = "15min") -> Optional[dict[str, Any]]:
    signal = generate_free_signal(symbol, interval=interval)
    if not signal:
        return None
    key = get_signal_key(signal)
    if is_signal_delivered(key):
        return None
    return signal


def scan_vip_market(symbol: str, interval: str = "15min") -> Optional[dict[str, Any]]:
    signal = generate_vip_signal(symbol, interval=interval)
    if not signal:
        return None
    key = get_signal_key(signal)
    if is_signal_delivered(key):
        return None
    return signal


def prepare_free_signal(symbol: str, interval: str = "15min") -> Optional[dict[str, Any]]:
    return scan_free_market(symbol, interval=interval)


def prepare_vip_signal(symbol: str, interval: str = "15min") -> Optional[dict[str, Any]]:
    return scan_vip_market(symbol, interval=interval)


def confirm_signal_delivery(signal: dict[str, Any]) -> None:
    key = get_signal_key(signal)
    mark_signal_delivered(key)
    symbol = str(signal.get("symbol") or "")
    if symbol:
        mark_signal_posted(symbol)


def signal_summary(signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_key": get_signal_key(signal),
        "symbol": signal.get("symbol"),
        "direction": signal.get("direction"),
        "score": get_score(signal),
        "strength": signal.get("strength"),
        "is_crypto": bool(signal.get("is_crypto")),
        "signal_code": signal.get("signal_code"),
        "generated_at": signal.get("generated_at"),
    }


def prune_old_signal_keys(max_items: int = 5000) -> None:
    try:
        max_items = int(max_items)
    except (TypeError, ValueError):
        max_items = 5000
    if max_items < 100:
        max_items = 100

    with _DELIVERED_LOCK:
        if len(_DELIVERED_SIGNAL_KEYS) <= max_items:
            return
        keys = list(_DELIVERED_SIGNAL_KEYS)
        _DELIVERED_SIGNAL_KEYS.clear()
        _DELIVERED_SIGNAL_KEYS.update(keys[-max_items:])


def engine_status() -> dict[str, Any]:
    with _DELIVERED_LOCK:
        cached = len(_DELIVERED_SIGNAL_KEYS)
    return {
        "status": "operational",
        "cached_delivered_signals": cached,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


class SignalManager:
    """Thin OOP wrapper around module-level scan helpers."""

    def scan_free(self, symbol: str, interval: str = "15min") -> Optional[dict[str, Any]]:
        return scan_free_market(symbol, interval=interval)

    def scan_vip(self, symbol: str, interval: str = "15min") -> Optional[dict[str, Any]]:
        return scan_vip_market(symbol, interval=interval)

    def confirm(self, signal: dict[str, Any]) -> None:
        confirm_signal_delivery(signal)

    def status(self) -> dict[str, Any]:
        return engine_status()


__all__ = [
    "is_signal_delivered",
    "mark_signal_delivered",
    "remove_signal_from_cache",
    "delivered_signal_count",
    "clear_delivered_signals",
    "scan_free_market",
    "scan_vip_market",
    "prepare_free_signal",
    "prepare_vip_signal",
    "confirm_signal_delivery",
    "signal_summary",
    "prune_old_signal_keys",
    "engine_status",
    "SignalManager",
]
