"""
Apex Bot risk and trade-level engine.

Responsible for:
- Structural stop-loss placement
- ATR safety limits
- R-based TP1 / TP2 / TP3
- Risk/reward validation
- BUY/SELL geometry validation
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_SL_ATR_MULTIPLIER = 1.5

TP1_RR = 1.0
TP2_RR = 2.0
TP3_RR = 3.0

MIN_TP3_RR = 2.0

# Extra ATR buffer beyond structural invalidation.
SL_ATR_BUFFER = 0.15

# Maximum acceptable distance between entry and SL.
MAX_RISK_ATR = 3.0


# ============================================================
# HELPERS
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


def _normalize_direction(
    direction: str,
) -> str:
    return (
        str(direction)
        .upper()
        .strip()
    )


# ============================================================
# STRUCTURAL LEVELS
# ============================================================

def calculate_structural_levels(
    *,
    entry_price: float,
    atr: float,
    direction: str,
    invalidation_price: Optional[float] = None,
    sl_atr_buffer: float = SL_ATR_BUFFER,
    max_risk_atr: float = MAX_RISK_ATR,
) -> Dict[str, float]:
    """
    Calculate structural SL and R-based targets.

    If invalidation_price is supplied:

        BUY  -> SL below invalidation
        SELL -> SL above invalidation

    Otherwise an ATR fallback stop is used.
    """

    entry = _safe_float(entry_price)
    atr_value = _safe_float(atr)

    direction = _normalize_direction(direction)

    if entry <= 0:
        raise ValueError(
            "Entry price must be greater than zero."
        )

    if atr_value <= 0:
        raise ValueError(
            "ATR must be greater than zero."
        )

    if direction not in {"BUY", "SELL"}:
        raise ValueError(
            "Direction must be BUY or SELL."
        )

    # --------------------------------------------------------
    # Validate configuration
    # --------------------------------------------------------

    try:
        buffer_multiplier = float(
            sl_atr_buffer
        )
    except (TypeError, ValueError):
        raise ValueError(
            "Invalid SL ATR buffer."
        )

    try:
        max_risk = float(
            max_risk_atr
        )
    except (TypeError, ValueError):
        raise ValueError(
            "Invalid maximum risk ATR."
        )

    if buffer_multiplier < 0:
        raise ValueError(
            "SL ATR buffer cannot be negative."
        )

    if max_risk <= 0:
        raise ValueError(
            "Maximum risk ATR must be positive."
        )

    # --------------------------------------------------------
    # Structural stop
    # --------------------------------------------------------

    if invalidation_price is not None:

        invalidation = _safe_float(
            invalidation_price
        )

        if invalidation <= 0:
            raise ValueError(
                "Invalidation price must be greater than zero."
            )

        buffer = (
            atr_value
            * buffer_multiplier
        )

        if direction == "BUY":
            stop_loss = (
                invalidation
                - buffer
            )

        else:
            stop_loss = (
                invalidation
                + buffer
            )

    else:

        # ATR fallback.
        distance = (
            atr_value
            * DEFAULT_SL_ATR_MULTIPLIER
        )

        if direction == "BUY":
            stop_loss = (
                entry
                - distance
            )

        else:
            stop_loss = (
                entry
                + distance
            )

    # --------------------------------------------------------
    # Stop geometry
    # --------------------------------------------------------

    if stop_loss <= 0:
        raise ValueError(
            "Calculated stop loss is invalid."
        )

    if direction == "BUY":

        if stop_loss >= entry:
            raise ValueError(
                "BUY stop loss must be below entry."
            )

    else:

        if stop_loss <= entry:
            raise ValueError(
                "SELL stop loss must be above entry."
            )

    # --------------------------------------------------------
    # Risk distance
    # --------------------------------------------------------

    risk = abs(
        entry - stop_loss
    )

    if risk <= 0:
        raise ValueError(
            "Trade risk must be greater than zero."
        )

    risk_atr = (
        risk / atr_value
    )

    if risk_atr > max_risk:
        raise ValueError(
            "Structural risk too large: "
            f"{risk_atr:.2f} ATR "
            f"(maximum {max_risk:.2f} ATR)."
        )

    # --------------------------------------------------------
    # R-based targets
    # --------------------------------------------------------

    if direction == "BUY":

        tp1 = entry + (
            risk * TP1_RR
        )

        tp2 = entry + (
            risk * TP2_RR
        )

        tp3 = entry + (
            risk * TP3_RR
        )

    else:

        tp1 = entry - (
            risk * TP1_RR
        )

        tp2 = entry - (
            risk * TP2_RR
        )

        tp3 = entry - (
            risk * TP3_RR
        )

    return {
        "entry_price": entry,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "risk_distance": risk,
        "risk_atr": risk_atr,
    }


# ============================================================
# LEVEL VALIDATION
# ============================================================

def validate_trade_levels(
    entry_price: float,
    stop_loss: float,
    tp1: float,
    tp2: float,
    tp3: float,
    direction: str,
) -> bool:
    """
    Validate complete BUY/SELL trade geometry.
    """

    direction = _normalize_direction(
        direction
    )

    entry = _safe_float(entry_price)
    stop = _safe_float(stop_loss)
    target1 = _safe_float(tp1)
    target2 = _safe_float(tp2)
    target3 = _safe_float(tp3)

    if min(
        entry,
        stop,
        target1,
        target2,
        target3,
    ) <= 0:
        return False

    if direction == "BUY":

        return (
            stop
            < entry
            < target1
            < target2
            < target3
        )

    if direction == "SELL":

        return (
            stop
            > entry
            > target1
            > target2
            > target3
        )

    return False


# ============================================================
# RISK / REWARD
# ============================================================

def risk_reward_ratios(
    levels: Dict[str, float],
) -> Dict[str, float]:
    """
    Calculate R:R for all three targets.
    """

    entry = _safe_float(
        levels.get("entry_price")
    )

    stop = _safe_float(
        levels.get("stop_loss")
    )

    risk = abs(
        entry - stop
    )

    if risk <= 0:
        return {
            "rr_tp1": 0.0,
            "rr_tp2": 0.0,
            "rr_tp3": 0.0,
        }

    tp1 = _safe_float(
        levels.get("tp1")
    )

    tp2 = _safe_float(
        levels.get("tp2")
    )

    tp3 = _safe_float(
        levels.get("tp3")
    )

    return {
        "rr_tp1": round(
            abs(tp1 - entry)
            / risk,
            2,
        ),

        "rr_tp2": round(
            abs(tp2 - entry)
            / risk,
            2,
        ),

        "rr_tp3": round(
            abs(tp3 - entry)
            / risk,
            2,
        ),
    }


# ============================================================
# COMPLETE RISK PROFILE
# ============================================================

def build_risk_profile(
    *,
    entry_price: float,
    atr: float,
    direction: str,
    invalidation_price: Optional[float] = None,
    sl_atr_buffer: float = SL_ATR_BUFFER,
    max_risk_atr: float = MAX_RISK_ATR,
) -> Dict[str, Any]:
    """
    Build and validate the complete trade risk profile.
    """

    direction = _normalize_direction(
        direction
    )

    levels = calculate_structural_levels(
        entry_price=entry_price,
        atr=atr,
        direction=direction,
        invalidation_price=invalidation_price,
        sl_atr_buffer=sl_atr_buffer,
        max_risk_atr=max_risk_atr,
    )

    ratios = risk_reward_ratios(
        levels
    )

    # --------------------------------------------------------
    # TP3 R:R gate
    # --------------------------------------------------------

    if ratios["rr_tp3"] < MIN_TP3_RR:
        raise ValueError(
            "TP3 R:R below minimum: "
            f"{ratios['rr_tp3']:.2f}"
        )

    # --------------------------------------------------------
    # Final geometry validation
    # --------------------------------------------------------

    if not validate_trade_levels(
        entry_price=levels["entry_price"],
        stop_loss=levels["stop_loss"],
        tp1=levels["tp1"],
        tp2=levels["tp2"],
        tp3=levels["tp3"],
        direction=direction,
    ):
        raise ValueError(
            "Generated trade levels failed validation."
        )

    return {
        **levels,
        **ratios,

        "atr": _safe_float(
            atr
        ),

        "direction": direction,

        "invalidation_price": (
            _safe_float(
                invalidation_price
            )
            if invalidation_price is not None
            else None
        ),

        "sl_atr_buffer": float(
            sl_atr_buffer
        ),

        "max_risk_atr": float(
            max_risk_atr
        ),
    }


# ============================================================
# PUBLIC API
# ============================================================

__all__ = [
    "DEFAULT_SL_ATR_MULTIPLIER",
    "TP1_RR",
    "TP2_RR",
    "TP3_RR",
    "MIN_TP3_RR",
    "SL_ATR_BUFFER",
    "MAX_RISK_ATR",
    "calculate_structural_levels",
    "validate_trade_levels",
    "risk_reward_ratios",
    "build_risk_profile",
]
