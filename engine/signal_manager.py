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

logger = logging.getLogger(__name__)

_DELIVERED_SIGNAL_KEYS: set[str] = set()
_DELIVERED_LOCK = threading.Lock()


def is_signal_delivered(signal_key: str) -> bool:
    """Return True if this signal has already been delivered."""
    if not signal_key:
        return False

    with _DELIVERED_LOCK:
        return signal_key in _DELIVERED_SIGNAL_KEYS


def mark_signal_delivered(signal: dict[str, Any]) -> bool:
    """Mark a signal as delivered."""
    signal_key = get_signal_key(signal)

    if not signal_key:
        return False

    with _DELIVERED_LOCK:
        if signal_key in _DELIVERED_SIGNAL_KEYS:
            return False

        _DELIVERED_SIGNAL_KEYS.add(signal_key)
        return True


def remove_signal_from_cache(signal_key: str) -> None:
    """Remove a signal from the in-memory delivery cache."""
    if not signal_key:
        return

    with _DELIVERED_LOCK:
        _DELIVERED_SIGNAL_KEYS.discard(signal_key)


def delivered_signal_count() -> int:
    """Return the number of signals stored in the current cache."""
    with _DELIVERED_LOCK:
        return len(_DELIVERED_SIGNAL_KEYS)


def clear_delivered_signals() -> None:
    """Clear the in-memory signal cache."""
    with _DELIVERED_LOCK:
        _DELIVERED_SIGNAL_KEYS.clear()


def scan_free_market(symbol: str) -> Optional[dict[str, Any]]:
    """Generate a free-channel eligible signal."""
    try:
        return generate_free_signal(symbol)
    except Exception:
        logger.exception("Free signal generation failed for %s", symbol)
        return None


def scan_vip_market(symbol: str) -> Optional[dict[str, Any]]:
    """Generate a VIP eligible signal."""
    try:
        return generate_vip_signal(symbol)
    except Exception:
        logger.exception("VIP signal generation failed for %s", symbol)
        return None


def prepare_free_signal(symbol: str) -> Optional[dict[str, Any]]:
    """Generate a free signal and reject duplicates."""
    signal = scan_free_market(symbol)

    if not signal:
        return None

    signal_key = get_signal_key(signal)

    if is_signal_delivered(signal_key):
        return None

    return signal


def prepare_vip_signal(symbol: str) -> Optional[dict[str, Any]]:
    """Generate a VIP signal and reject duplicates."""
    signal = scan_vip_market(symbol)

    if not signal:
        return None

    signal_key = get_signal_key(signal)

    if is_signal_delivered(signal_key):
        return None

    return signal


def confirm_signal_delivery(signal: dict[str, Any]) -> bool:
    """Confirm that a signal was successfully delivered."""
    if not signal:
        return False

    signal_key = get_signal_key(signal)

    if not signal_key:
        return False

    newly_marked = mark_signal_delivered(signal)

    if not newly_marked:
        return False

    symbol = signal.get("symbol")

    if symbol:
        try:
            mark_signal_posted(str(symbol))
        except Exception:
            logger.exception("Failed to increment daily signal counter for %s", symbol)

    return True


def signal_summary(signal: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, safe summary for logging/admin tools."""
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
    """Safety valve for long-running processes."""
    try:
        max_items = int(max_items)
    except (TypeError, ValueError):
        max_items = 5000

    if max_items < 100:
        max_items = 100

    with _DELIVERED_LOCK:
        current_size = len(_DELIVERED_SIGNAL_KEYS)

        if current_size <= max_items:
            return

        keys = list(_DELIVERED_SIGNAL_KEYS)
        _DELIVERED_SIGNAL_KEYS.clear()
        _DELIVERED_SIGNAL_KEYS.update(keys[-max_items:])


def engine_status() -> dict[str, Any]:
    """Return basic engine status information."""
    with _DELIVERED_LOCK:
        cached = len(_DELIVERED_SIGNAL_KEYS)

    return {
        "status": "operational",
        "cached_delivered_signals": cached,
        "checked_at": datetime.now(timezone.utc),
    }


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
]
