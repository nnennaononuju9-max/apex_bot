from __future__ import annotations

from typing import Any, Dict


# ATR multipliers
DEFAULT_SL_ATR_MULTIPLIER = 1.5
TP1_ATR_MULTIPLIER = 1.5
TP2_ATR_MULTIPLIER = 2.5
TP3_ATR_MULTIPLIER = 4.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        result = float(value)
        if result != result:  # NaN check
            return default
        return result
    except (TypeError, ValueError):
        return default


def validate_trade_levels(
    entry_price: float,
    stop_loss: float,
    tp1: float,
    tp2: float,
    tp3: float,
    direction: str,
) -> bool:
    """Validate that SL/TP levels make sense for the direction."""
    direction = str(direction).upper().strip()
    if direction == "BUY":
        return stop_loss < entry_price < tp1 < tp2 < tp3
    if direction == "SELL":
        return stop_loss > entry_price > tp1 > tp2 > tp3
    return False


def calculate_trade_levels(
    *,
    entry_price: float,
    atr: float,
    direction: str,
    sl_atr_multiplier: float = DEFAULT_SL_ATR_MULTIPLIER,
) -> Dict[str, float]:
    """Calculate Stop Loss and three Take Profit levels from ATR."""
    entry = _safe_float(entry_price)
    atr_value = _safe_float(atr)
    direction = str(direction).upper().strip()

    if entry <= 0:
        raise ValueError("Entry price must be greater than zero.")
    if atr_value <= 0:
        raise ValueError("ATR must be greater than zero.")
    if direction not in {"BUY", "SELL"}:
        raise ValueError("Direction must be BUY or SELL.")

    sl_distance = atr_value * float(sl_atr_multiplier)
    tp1_distance = atr_value * TP1_ATR_MULTIPLIER
    tp2_distance = atr_value * TP2_ATR_MULTIPLIER
    tp3_distance = atr_value * TP3_ATR_MULTIPLIER

    if direction == "BUY":
        stop_loss = entry - sl_distance
        tp1 = entry + tp1_distance
        tp2 = entry + tp2_distance
        tp3 = entry + tp3_distance
    else:
        stop_loss = entry + sl_distance
        tp1 = entry - tp1_distance
        tp2 = entry - tp2_distance
        tp3 = entry - tp3_distance

    levels = {
        "entry_price": entry,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
    }

    if not validate_trade_levels(
        entry_price=entry,
        stop_loss=stop_loss,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        direction=direction,
    ):
        raise ValueError("Generated trade levels failed validation.")

    return levels


def risk_reward_ratios(levels: Dict[str, float], direction: str) -> Dict[str, float]:
    """Return RR ratios for TP1/TP2/TP3 versus SL distance."""
    entry = _safe_float(levels.get("entry_price"))
    stop_loss = _safe_float(levels.get("stop_loss"))

    risk = abs(entry - stop_loss)
    if risk <= 0:
        return {"rr_tp1": 0.0, "rr_tp2": 0.0, "rr_tp3": 0.0}

    out: Dict[str, float] = {}
    for key, label in (("tp1", "rr_tp1"), ("tp2", "rr_tp2"), ("tp3", "rr_tp3")):
        tp = _safe_float(levels.get(key))
        reward = abs(tp - entry)
        out[label] = round(reward / risk, 2)
    return out


def build_risk_profile(
    *,
    entry_price: float,
    atr: float,
    direction: str,
    sl_atr_multiplier: float = DEFAULT_SL_ATR_MULTIPLIER,
) -> Dict[str, Any]:
    """Full risk package used by signal generation."""
    levels = calculate_trade_levels(
        entry_price=entry_price,
        atr=atr,
        direction=direction,
        sl_atr_multiplier=sl_atr_multiplier,
    )
    ratios = risk_reward_ratios(levels, direction)
    return {
        **levels,
        **ratios,
        "atr": _safe_float(atr),
        "direction": str(direction).upper().strip(),
        "sl_atr_multiplier": float(sl_atr_multiplier),
    }


__all__ = [
    "DEFAULT_SL_ATR_MULTIPLIER",
    "TP1_ATR_MULTIPLIER",
    "TP2_ATR_MULTIPLIER",
    "TP3_ATR_MULTIPLIER",
    "calculate_trade_levels",
    "validate_trade_levels",
    "risk_reward_ratios",
    "build_risk_profile",
]
