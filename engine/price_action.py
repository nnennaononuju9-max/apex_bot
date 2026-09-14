from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd


# ============================================================
# APEX PRICE ACTION / MARKET STRUCTURE ENGINE
# ============================================================
#
# Detects:
#   1. Liquidity sweep
#   2. Reclaim
#   3. Displacement
#   4. Structure break
#   5. Retest
#
# Also provides:
#   - entry zone
#   - structural invalidation
#   - liquidity level
#   - structure level
#   - displacement strength
#
# This module intentionally uses completed candles only.
# ============================================================


DEFAULT_LOOKBACK = 20
DEFAULT_SWING_LOOKBACK = 3

MIN_DISPLACEMENT_ATR = 0.50
RETEST_TOLERANCE_ATR = 0.25


def _safe_float(value: Any) -> Optional[float]:
    try:
        value = float(value)

        if pd.isna(value):
            return None

        return value

    except (TypeError, ValueError):
        return None


def _validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("Price-action dataframe is empty.")

    required = {
        "open",
        "high",
        "low",
        "close",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "Missing OHLC columns: "
            + ", ".join(sorted(missing))
        )

    result = df.copy()

    for column in [
        "open",
        "high",
        "low",
        "close",
    ]:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    result = result.dropna(
        subset=[
            "open",
            "high",
            "low",
            "close",
        ]
    ).reset_index(drop=True)

    if len(result) < 10:
        raise ValueError(
            "Not enough candles for price-action analysis."
        )

    return result


# ============================================================
# SWING LEVELS
# ============================================================

def find_recent_swing_high(
    df: pd.DataFrame,
    lookback: int = DEFAULT_LOOKBACK,
) -> Optional[float]:

    if len(df) < 3:
        return None

    lookback = max(3, int(lookback))

    window = df.iloc[-lookback:]

    value = window["high"].max()

    return _safe_float(value)


def find_recent_swing_low(
    df: pd.DataFrame,
    lookback: int = DEFAULT_LOOKBACK,
) -> Optional[float]:

    if len(df) < 3:
        return None

    lookback = max(3, int(lookback))

    window = df.iloc[-lookback:]

    value = window["low"].min()

    return _safe_float(value)


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def detect_liquidity_sweep(
    df: pd.DataFrame,
    direction: str,
    lookback: int = DEFAULT_LOOKBACK,
) -> Dict[str, Any]:

    direction = str(direction).upper().strip()

    if direction not in {"BUY", "SELL"}:
        return {
            "detected": False,
            "level": None,
            "reclaimed": False,
        }

    if len(df) < lookback + 2:
        return {
            "detected": False,
            "level": None,
            "reclaimed": False,
        }

    # Previous candles define liquidity.
    previous = df.iloc[-(lookback + 1):-1]

    current = df.iloc[-1]

    previous_high = _safe_float(
        previous["high"].max()
    )

    previous_low = _safe_float(
        previous["low"].min()
    )

    current_high = _safe_float(
        current["high"]
    )

    current_low = _safe_float(
        current["low"]
    )

    current_close = _safe_float(
        current["close"]
    )

    if (
        previous_high is None
        or previous_low is None
        or current_high is None
        or current_low is None
        or current_close is None
    ):
        return {
            "detected": False,
            "level": None,
            "reclaimed": False,
        }

    # BUY:
    # Price sweeps below liquidity and closes back above it.
    if direction == "BUY":

        swept = current_low < previous_low

        reclaimed = (
            current_close > previous_low
        )

        return {
            "detected": bool(
                swept and reclaimed
            ),
            "level": previous_low,
            "reclaimed": bool(reclaimed),
        }

    # SELL:
    # Price sweeps above liquidity and closes back below it.
    swept = current_high > previous_high

    reclaimed = (
        current_close < previous_high
    )

    return {
        "detected": bool(
            swept and reclaimed
        ),
        "level": previous_high,
        "reclaimed": bool(reclaimed),
    }


# ============================================================
# DISPLACEMENT
# ============================================================

def detect_displacement(
    df: pd.DataFrame,
    atr: float,
    direction: str,
    minimum_body_atr: float = MIN_DISPLACEMENT_ATR,
) -> Dict[str, Any]:

    direction = str(direction).upper().strip()

    if direction not in {"BUY", "SELL"}:
        return {
            "detected": False,
            "body_atr": 0.0,
        }

    atr = _safe_float(atr)

    if atr is None or atr <= 0:
        return {
            "detected": False,
            "body_atr": 0.0,
        }

    candle = df.iloc[-1]

    candle_open = _safe_float(
        candle["open"]
    )

    candle_close = _safe_float(
        candle["close"]
    )

    if (
        candle_open is None
        or candle_close is None
    ):
        return {
            "detected": False,
            "body_atr": 0.0,
        }

    body = abs(
        candle_close - candle_open
    )

    body_atr = body / atr

    bullish = (
        candle_close > candle_open
    )

    bearish = (
        candle_close < candle_open
    )

    if direction == "BUY":
        directional = bullish
    else:
        directional = bearish

    return {
        "detected": bool(
            directional
            and body_atr >= float(
                minimum_body_atr
            )
        ),
        "body_atr": round(
            body_atr,
            3,
        ),
    }


# ============================================================
# STRUCTURE BREAK
# ============================================================

def detect_structure_break(
    df: pd.DataFrame,
    direction: str,
    lookback: int = DEFAULT_LOOKBACK,
) -> Dict[str, Any]:

    direction = str(direction).upper().strip()

    if direction not in {"BUY", "SELL"}:
        return {
            "detected": False,
            "level": None,
        }

    if len(df) < lookback + 2:
        return {
            "detected": False,
            "level": None,
        }

    previous = df.iloc[-(lookback + 1):-1]

    current_close = _safe_float(
        df.iloc[-1]["close"]
    )

    if current_close is None:
        return {
            "detected": False,
            "level": None,
        }

    swing_high = _safe_float(
        previous["high"].max()
    )

    swing_low = _safe_float(
        previous["low"].min()
    )

    if direction == "BUY":

        if swing_high is None:
            return {
                "detected": False,
                "level": None,
            }

        broken = current_close > swing_high

        return {
            "detected": bool(broken),
            "level": swing_high,
        }

    if swing_low is None:
        return {
            "detected": False,
            "level": None,
        }

    broken = current_close < swing_low

    return {
        "detected": bool(broken),
        "level": swing_low,
    }


# ============================================================
# RETEST
# ============================================================

def detect_retest(
    df: pd.DataFrame,
    direction: str,
    structure_level: Optional[float],
    atr: float,
    tolerance_atr: float = RETEST_TOLERANCE_ATR,
) -> bool:

    direction = str(direction).upper().strip()

    if structure_level is None:
        return False

    atr = _safe_float(atr)

    if atr is None or atr <= 0:
        return False

    if len(df) < 3:
        return False

    # Use the candle immediately before the current candle
    # as the retest candle.
    previous = df.iloc[-2]

    previous_high = _safe_float(
        previous["high"]
    )

    previous_low = _safe_float(
        previous["low"]
    )

    previous_close = _safe_float(
        previous["close"]
    )

    current_close = _safe_float(
        df.iloc[-1]["close"]
    )

    if (
        previous_high is None
        or previous_low is None
        or previous_close is None
        or current_close is None
    ):
        return False

    tolerance = (
        atr * float(tolerance_atr)
    )

    level = float(structure_level)

    if direction == "BUY":

        touched = (
            previous_low
            <= level + tolerance
            and previous_high
            >= level - tolerance
        )

        recovered = (
            current_close > level
        )

        return bool(
            touched and recovered
        )

    touched = (
        previous_low
        <= level + tolerance
        and previous_high
        >= level - tolerance
    )

    recovered = (
        current_close < level
    )

    return bool(
        touched and recovered
    )


# ============================================================
# INVALIDATION
# ============================================================

def calculate_invalidation(
    *,
    direction: str,
    liquidity_level: Optional[float],
    structure_level: Optional[float],
    atr: float,
) -> Optional[float]:

    direction = str(direction).upper().strip()

    atr = _safe_float(atr)

    if atr is None or atr <= 0:
        return None

    candidates = []

    if liquidity_level is not None:
        value = _safe_float(
            liquidity_level
        )

        if value is not None:
            candidates.append(value)

    if structure_level is not None:
        value = _safe_float(
            structure_level
        )

        if value is not None:
            candidates.append(value)

    if not candidates:
        return None

    if direction == "BUY":
        return min(candidates)

    if direction == "SELL":
        return max(candidates)

    return None


# ============================================================
# ENTRY ZONE
# ============================================================

def build_entry_zone(
    *,
    entry_price: float,
    atr: float,
    direction: str,
) -> tuple[float, float]:

    entry = float(entry_price)
    atr = float(atr)

    width = atr * 0.25

    low = entry - width
    high = entry + width

    return low, high


# ============================================================
# COMPLETE PRICE ACTION ANALYSIS
# ============================================================

def analyze_price_action(
    df: pd.DataFrame,
    *,
    direction: str,
    atr: float,
    lookback: int = DEFAULT_LOOKBACK,
) -> Dict[str, Any]:

    df = _validate_dataframe(df)

    direction = str(direction).upper().strip()

    if direction not in {"BUY", "SELL"}:
        raise ValueError(
            "Direction must be BUY or SELL."
        )

    atr_value = _safe_float(atr)

    if atr_value is None or atr_value <= 0:
        raise ValueError(
            "ATR must be greater than zero."
        )

    # --------------------------------------------------------
    # Liquidity
    # --------------------------------------------------------

    sweep = detect_liquidity_sweep(
        df,
        direction,
        lookback=lookback,
    )

    # --------------------------------------------------------
    # Displacement
    # --------------------------------------------------------

    displacement = detect_displacement(
        df,
        atr_value,
        direction,
    )

    # --------------------------------------------------------
    # Structure
    # --------------------------------------------------------

    structure = detect_structure_break(
        df,
        direction,
        lookback=lookback,
    )

    structure_level = structure.get(
        "level"
    )

    # --------------------------------------------------------
    # Retest
    # --------------------------------------------------------

    retest = detect_retest(
        df,
        direction,
        structure_level,
        atr_value,
    )

    # --------------------------------------------------------
    # Entry
    # --------------------------------------------------------

    entry_price = _safe_float(
        df.iloc[-1]["close"]
    )

    if entry_price is None:
        raise ValueError(
            "Unable to determine entry price."
        )

    entry_zone_low, entry_zone_high = (
        build_entry_zone(
            entry_price=entry_price,
            atr=atr_value,
            direction=direction,
        )
    )

    # --------------------------------------------------------
    # Invalidation
    # --------------------------------------------------------

    invalidation_price = (
        calculate_invalidation(
            direction=direction,
            liquidity_level=sweep.get(
                "level"
            ),
            structure_level=structure_level,
            atr=atr_value,
        )
    )

    # --------------------------------------------------------
    # Final sequence
    # --------------------------------------------------------

    complete_sequence = all(
        [
            bool(sweep.get("detected")),
            bool(sweep.get("reclaimed")),
            bool(displacement.get("detected")),
            bool(structure.get("detected")),
            bool(retest),
        ]
    )

    return {
        "sweep": bool(
            sweep.get("detected")
        ),

        "reclaim": bool(
            sweep.get("reclaimed")
        ),

        "displacement": bool(
            displacement.get("detected")
        ),

        "structure_break": bool(
            structure.get("detected")
        ),

        "retest": bool(retest),

        "sequence_complete": complete_sequence,

        "liquidity_level": sweep.get(
            "level"
        ),

        "structure_level": structure_level,

        "invalidation_price": invalidation_price,

        "entry_zone_low": entry_zone_low,

        "entry_zone_high": entry_zone_high,

        "displacement_body_atr": displacement.get(
            "body_atr",
            0.0,
        ),
    }


__all__ = [
    "DEFAULT_LOOKBACK",
    "DEFAULT_SWING_LOOKBACK",
    "MIN_DISPLACEMENT_ATR",
    "RETEST_TOLERANCE_ATR",
    "find_recent_swing_high",
    "find_recent_swing_low",
    "detect_liquidity_sweep",
    "detect_displacement",
    "detect_structure_break",
    "detect_retest",
    "calculate_invalidation",
    "build_entry_zone",
    "analyze_price_action",
]