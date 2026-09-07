from future import annotations

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

logger = logging.getLogger(name)

============================================================

APEX SIGNAL MANAGER

============================================================

Responsibilities:

- Prevent duplicate signal delivery

- Generate signals safely

- Track signals already delivered during this process

- Provide clean functions for Telegram/jobs to call

This module does NOT:

- send Telegram messages

- calculate indicators

- fetch candles directly

- contain payment logic

============================================================

Signals delivered during the current bot process.

IMPORTANT:

This is intentionally an in-memory safety layer.

The database remains responsible for daily signal limits.

If Railway restarts the bot, this set is cleared.

That is okay because the database daily limit still protects

against unlimited signal generation.

_DELIVERED_SIGNAL_KEYS: set[str] = set()

Prevent simultaneous threads/tasks from modifying the set.

_DELIVERED_LOCK = threading.Lock()

============================================================

DUPLICATE PROTECTION

============================================================

def is_signal_delivered(signal_key: str) -> bool:
"""Return True if this signal has already been delivered."""

if not signal_key:
    return False

with _DELIVERED_LOCK:
    return signal_key in _DELIVERED_SIGNAL_KEYS

def mark_signal_delivered(
signal: dict[str, Any],
) -> bool:
"""
Mark a signal as delivered.

Returns:
    True  = newly marked
    False = already existed

The operation is atomic with respect to other threads.
"""

signal_key = get_signal_key(signal)

if not signal_key:
    return False

with _DELIVERED_LOCK:
    if signal_key in _DELIVERED_SIGNAL_KEYS:
        return False

    _DELIVERED_SIGNAL_KEYS.add(signal_key)
    return True

def remove_signal_from_cache(
signal_key: str,
) -> None:
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
"""
Clear the in-memory signal cache.

Primarily useful for controlled maintenance/testing.
"""

with _DELIVERED_LOCK:
    _DELIVERED_SIGNAL_KEYS.clear()

============================================================

SIGNAL GENERATION

============================================================

def scan_free_market(
symbol: str,
) -> Optional[dict[str, Any]]:
"""
Generate a free-channel eligible signal.

No Telegram action happens here.
"""

try:
    return generate_free_signal(symbol)

except Exception:
    logger.exception(
        "Free signal generation failed for %s",
        symbol,
    )
    return None

def scan_vip_market(
symbol: str,
) -> Optional[dict[str, Any]]:
"""
Generate a VIP eligible signal.

No Telegram action happens here.
"""

try:
    return generate_vip_signal(symbol)

except Exception:
    logger.exception(
        "VIP signal generation failed for %s",
        symbol,
    )
    return None

============================================================

SAFE SIGNAL PREPARATION

============================================================

def prepare_free_signal(
symbol: str,
) -> Optional[dict[str, Any]]:
"""
Generate a free signal and reject duplicates.

The signal is NOT marked delivered yet.

Why?

Because the Telegram layer should only mark it delivered
after the message has successfully been sent.
"""

signal = scan_free_market(symbol)

if not signal:
    return None

signal_key = get_signal_key(signal)

if is_signal_delivered(signal_key):
    return None

return signal

def prepare_vip_signal(
symbol: str,
) -> Optional[dict[str, Any]]:
"""
Generate a VIP signal and reject duplicates.

The signal is NOT marked delivered yet.
"""

signal = scan_vip_market(symbol)

if not signal:
    return None

signal_key = get_signal_key(signal)

if is_signal_delivered(signal_key):
    return None

return signal

============================================================

DELIVERY CONFIRMATION

============================================================

def confirm_signal_delivery(
signal: dict[str, Any],
) -> bool:
"""
Confirm that a signal was successfully delivered.

Once confirmed:
    1. It is added to the duplicate-protection cache.
    2. Its market daily counter is incremented.

This should be called ONLY after Telegram confirms that
the message was sent successfully.
"""

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
        # The in-memory duplicate lock is already active.
        # Log the database problem rather than accidentally
        # delivering the same signal repeatedly.
        logger.exception(
            "Failed to increment daily signal counter for %s",
            symbol,
        )

return True

============================================================

SIGNAL INFORMATION

============================================================

def signal_summary(
signal: dict[str, Any],
) -> dict[str, Any]:
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

============================================================

CACHE MAINTENANCE

============================================================

def prune_old_signal_keys(
max_items: int = 5000,
) -> None:
"""
Safety valve for long-running processes.

Signal keys normally remain small because the database
daily limits prevent unlimited signal creation.

If the cache grows beyond max_items, retain the newest
keys approximately by insertion order.
"""

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

    # Python sets do not expose insertion order.
    # Converting to a list gives us a deterministic way
    # to reduce the cache without relying on undocumented
    # behavior.
    keys = list(_DELIVERED_SIGNAL_KEYS)

    _DELIVERED_SIGNAL_KEYS.clear()

    _DELIVERED_SIGNAL_KEYS.update(
        keys[-max_items:]
    )

============================================================

ENGINE HEALTH

============================================================

def engine_status() -> dict[str, Any]:
"""Return basic engine status information."""

with _DELIVERED_LOCK:
    cached = len(_DELIVERED_SIGNAL_KEYS)

return {
    "status": "operational",
    "cached_delivered_signals": cached,
    "checked_at": datetime.now(timezone.utc),
}

============================================================

PUBLIC EXPORTS

============================================================

all = [
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
