from __future__ import annotations

import hashlib
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


# ============================================================
# DELIVERY CACHE
# ============================================================

_DELIVERED_SIGNAL_KEYS: set[str] = set()
_DELIVERED_SETUP_KEYS: set[str] = set()

_DELIVERED_LOCK = threading.Lock()


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        result = float(value)

        if result != result:
            return default

        return result

    except (TypeError, ValueError):
        return default


def _normalize_text(
    value: Any,
) -> str:
    return str(value or "").strip().upper()


# ============================================================
# SETUP IDENTITY
# ============================================================

def build_setup_key(
    signal: dict[str, Any],
) -> str:
    """
    Build a stable identity for the underlying market setup.

    Unlike signal_code, this key does not depend on a random UUID.

    This allows repeated scans of the same setup to be detected.
    """

    symbol = _normalize_text(
        signal.get("symbol")
    )

    direction = _normalize_text(
        signal.get("direction")
    )

    timeframe = _normalize_text(
        signal.get("timeframe")
        or signal.get("interval")
    )

    entry = _safe_float(
        signal.get("entry_price")
    )

    zone_low = _safe_float(
        signal.get("entry_zone_low")
    )

    zone_high = _safe_float(
        signal.get("entry_zone_high")
    )

    invalidation = _safe_float(
        signal.get("invalidation_price")
    )

    liquidity = _safe_float(
        signal.get("liquidity_level")
    )

    structure = _safe_float(
        signal.get("structure_level")
    )

    # Round prices so tiny floating-point differences
    # do not create a brand-new setup identity.
    raw = "|".join(
        [
            symbol,
            direction,
            timeframe,
            f"{entry:.8f}",
            f"{zone_low:.8f}",
            f"{zone_high:.8f}",
            f"{invalidation:.8f}",
            f"{liquidity:.8f}",
            f"{structure:.8f}",
        ]
    )

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:16].upper()

    return f"SETUP:{digest}"


# ============================================================
# SIGNAL DELIVERY IDENTITY
# ============================================================

def is_signal_delivered(
    signal_key: str,
) -> bool:
    """Return True if this exact generated signal was delivered."""

    if not signal_key:
        return False

    with _DELIVERED_LOCK:
        return signal_key in _DELIVERED_SIGNAL_KEYS


def is_setup_delivered(
    setup_key: str,
) -> bool:
    """Return True if this underlying setup was already delivered."""

    if not setup_key:
        return False

    with _DELIVERED_LOCK:
        return setup_key in _DELIVERED_SETUP_KEYS


# ============================================================
# MARK DELIVERY
# ============================================================

def mark_signal_delivered(
    signal: dict[str, Any],
) -> bool:
    """
    Mark a signal as delivered.

    Returns False if either:
      - the exact signal was already delivered
      - the underlying setup was already delivered
    """

    if not signal:
        return False

    signal_key = get_signal_key(signal)
    setup_key = build_setup_key(signal)

    if not signal_key or not setup_key:
        return False

    with _DELIVERED_LOCK:

        if signal_key in _DELIVERED_SIGNAL_KEYS:
            return False

        if setup_key in _DELIVERED_SETUP_KEYS:
            return False

        _DELIVERED_SIGNAL_KEYS.add(
            signal_key
        )

        _DELIVERED_SETUP_KEYS.add(
            setup_key
        )

        return True


# ============================================================
# CACHE REMOVAL
# ============================================================

def remove_signal_from_cache(
    signal_key: str,
) -> None:
    """
    Remove an exact signal key from the delivery cache.

    This does not automatically remove the associated
    setup key because the setup may have been delivered
    under another generated signal.
    """

    if not signal_key:
        return

    with _DELIVERED_LOCK:
        _DELIVERED_SIGNAL_KEYS.discard(
            signal_key
        )


def remove_setup_from_cache(
    setup_key: str,
) -> None:
    """Remove a setup key from the delivery cache."""

    if not setup_key:
        return

    with _DELIVERED_LOCK:
        _DELIVERED_SETUP_KEYS.discard(
            setup_key
        )


# ============================================================
# CACHE COUNTERS
# ============================================================

def delivered_signal_count() -> int:
    """Return the number of exact signal keys cached."""

    with _DELIVERED_LOCK:
        return len(
            _DELIVERED_SIGNAL_KEYS
        )


def delivered_setup_count() -> int:
    """Return the number of setup keys cached."""

    with _DELIVERED_LOCK:
        return len(
            _DELIVERED_SETUP_KEYS
        )


def clear_delivered_signals() -> None:
    """Clear all in-memory delivery state."""

    with _DELIVERED_LOCK:
        _DELIVERED_SIGNAL_KEYS.clear()
        _DELIVERED_SETUP_KEYS.clear()


# ============================================================
# FREE MARKET SCAN
# ============================================================

def scan_free_market(
    symbol: str,
) -> Optional[dict[str, Any]]:
    """
    Generate a free-channel eligible signal.

    No delivery state is changed here.
    """

    try:
        signal = generate_free_signal(
            symbol
        )

        return signal

    except Exception:
        logger.exception(
            "Free signal generation failed for %s",
            symbol,
        )

        return None


# ============================================================
# VIP MARKET SCAN
# ============================================================

def scan_vip_market(
    symbol: str,
) -> Optional[dict[str, Any]]:
    """
    Generate a VIP-channel eligible signal.

    No delivery state is changed here.
    """

    try:
        signal = generate_vip_signal(
            symbol
        )

        return signal

    except Exception:
        logger.exception(
            "VIP signal generation failed for %s",
            symbol,
        )

        return None


# ============================================================
# PREPARE FREE SIGNAL
# ============================================================

def prepare_free_signal(
    symbol: str,
) -> Optional[dict[str, Any]]:
    """
    Generate a free signal and reject:
      - invalid signals
      - duplicate generated signals
      - duplicate underlying setups
    """

    signal = scan_free_market(
        symbol
    )

    if not signal:
        return None

    signal_key = get_signal_key(
        signal
    )

    setup_key = build_setup_key(
        signal
    )

    if not signal_key:
        return None

    if not setup_key:
        return None

    if is_signal_delivered(
        signal_key
    ):
        return None

    if is_setup_delivered(
        setup_key
    ):
        return None

    return signal


# ============================================================
# PREPARE VIP SIGNAL
# ============================================================

def prepare_vip_signal(
    symbol: str,
) -> Optional[dict[str, Any]]:
    """
    Generate a VIP signal and reject duplicates.
    """

    signal = scan_vip_market(
        symbol
    )

    if not signal:
        return None

    signal_key = get_signal_key(
        signal
    )

    setup_key = build_setup_key(
        signal
    )

    if not signal_key:
        return None

    if not setup_key:
        return None

    if is_signal_delivered(
        signal_key
    ):
        return None

    if is_setup_delivered(
        setup_key
    ):
        return None

    return signal


# ============================================================
# CONFIRM DELIVERY
# ============================================================

def confirm_signal_delivery(
    signal: dict[str, Any],
) -> bool:
    """
    Confirm that a signal was actually delivered.

    IMPORTANT:
    Call this only AFTER the Telegram/Discord/etc.
    delivery operation succeeds.

    This is where the daily market counter is incremented.
    """

    if not signal:
        return False

    signal_key = get_signal_key(
        signal
    )

    setup_key = build_setup_key(
        signal
    )

    if not signal_key:
        return False

    if not setup_key:
        return False

    newly_marked = mark_signal_delivered(
        signal
    )

    if not newly_marked:
        return False

    symbol = signal.get(
        "symbol"
    )

    if symbol:

        try:
            mark_signal_posted(
                str(symbol)
            )

        except Exception:
            logger.exception(
                "Failed to increment daily signal counter for %s",
                symbol,
            )

    return True


# ============================================================
# SIGNAL SUMMARY
# ============================================================

def signal_summary(
    signal: dict[str, Any],
) -> dict[str, Any]:
    """
    Return a compact summary suitable for logs,
    admin dashboards, or monitoring.
    """

    setup_key = build_setup_key(
        signal
    )

    return {

        "signal_key": (
            get_signal_key(signal)
        ),

        "setup_key": setup_key,

        "symbol": signal.get(
            "symbol"
        ),

        "direction": signal.get(
            "direction"
        ),

        "score": get_score(
            signal
        ),

        "strength": signal.get(
            "strength"
        ),

        "signal_tier": signal.get(
            "signal_tier"
        ),

        "is_crypto": bool(
            signal.get(
                "is_crypto"
            )
        ),

        "signal_code": signal.get(
            "signal_code"
        ),

        "entry_price": signal.get(
            "entry_price"
        ),

        "stop_loss": signal.get(
            "stop_loss"
        ),

        "tp1": signal.get(
            "tp1"
        ),

        "tp2": signal.get(
            "tp2"
        ),

        "tp3": signal.get(
            "tp3"
        ),

        "rr_tp3": signal.get(
            "rr_tp3"
        ),

        "generated_at": signal.get(
            "generated_at"
        ),
    }


# ============================================================
# SIGNAL QUALITY CHECK
# ============================================================

def signal_is_publishable(
    signal: Optional[dict[str, Any]],
) -> bool:
    """
    Final manager-level sanity check.

    The generator performs the detailed technical checks.
    The manager verifies that the returned object is complete
    enough to send.
    """

    if not signal:
        return False

    required = (
        "symbol",
        "direction",
        "score",
        "entry_price",
        "stop_loss",
        "tp1",
        "tp2",
        "tp3",
        "signal_code",
    )

    for field in required:

        if signal.get(field) is None:
            return False

    direction = str(
        signal.get(
            "direction"
        )
    ).upper()

    if direction not in {
        "BUY",
        "SELL",
    }:
        return False

    try:
        score = int(
            signal.get(
                "score"
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return False

    if score <= 0:
        return False

    return True


# ============================================================
# PRUNE CACHE
# ============================================================

def prune_old_signal_keys(
    max_items: int = 5000,
) -> None:
    """
    Safety valve for long-running processes.

    Keeps memory usage bounded.

    Note:
    This is an in-memory cache only. A restart clears it.
    """

    try:
        max_items = int(
            max_items
        )

    except (
        TypeError,
        ValueError,
    ):
        max_items = 5000

    if max_items < 100:
        max_items = 100

    with _DELIVERED_LOCK:

        # ----------------------------------------------------
        # Exact signal keys
        # ----------------------------------------------------

        if len(
            _DELIVERED_SIGNAL_KEYS
        ) > max_items:

            keys = list(
                _DELIVERED_SIGNAL_KEYS
            )

            _DELIVERED_SIGNAL_KEYS.clear()

            _DELIVERED_SIGNAL_KEYS.update(
                keys[-max_items:]
            )

        # ----------------------------------------------------
        # Setup keys
        # ----------------------------------------------------

        if len(
            _DELIVERED_SETUP_KEYS
        ) > max_items:

            keys = list(
                _DELIVERED_SETUP_KEYS
            )

            _DELIVERED_SETUP_KEYS.clear()

            _DELIVERED_SETUP_KEYS.update(
                keys[-max_items:]
            )


# ============================================================
# ENGINE STATUS
# ============================================================

def engine_status() -> dict[str, Any]:
    """Return basic signal-manager status."""

    with _DELIVERED_LOCK:

        cached_signals = len(
            _DELIVERED_SIGNAL_KEYS
        )

        cached_setups = len(
            _DELIVERED_SETUP_KEYS
        )

    return {

        "status": "operational",

        "cached_delivered_signals": (
            cached_signals
        ),

        "cached_delivered_setups": (
            cached_setups
        ),

        "checked_at": (
            datetime.now(
                timezone.utc
            )
        ),
    }


# ============================================================
# PUBLIC API
# ============================================================

__all__ = [

    "build_setup_key",

    "is_signal_delivered",

    "is_setup_delivered",

    "mark_signal_delivered",

    "remove_signal_from_cache",

    "remove_setup_from_cache",

    "delivered_signal_count",

    "delivered_setup_count",

    "clear_delivered_signals",

    "scan_free_market",

    "scan_vip_market",

    "prepare_free_signal",

    "prepare_vip_signal",

    "confirm_signal_delivery",

    "signal_summary",

    "signal_is_publishable",

    "prune_old_signal_keys",

    "engine_status",
]
