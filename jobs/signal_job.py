"""
Apex Bot signal generation engine.

Builds qualified trading signals from:
- 15M market data
- 1H trend confirmation
- Technical indicators
- Scoring engine
- Structural price-action data
- Risk/reward validation
- Daily market signal limits
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import uuid

import pandas as pd

from config import (
    FREE_SIGNAL_SCORE,
    VIP_SCAN_SCORE,
    MAX_SIGNALS_PER_MARKET_PER_DAY,
)

from database import (
    get_daily_signal_count,
    increment_daily_signal_count,
)

from .market_data import get_data, CRYPTO_SYMBOL_MAP
from .indicators import calculate_indicators
from .scoring import score_signal, MAX_SCORE
from .risk import build_risk_profile


# ============================================================
# HELPERS
# ============================================================

def price_format(price: float) -> str:
    try:
        p = float(price)
    except (TypeError, ValueError):
        return str(price)

    if p >= 1000:
        return f"{p:,.2f}"

    if p >= 1:
        return f"{p:.4f}"

    return f"{p:.6f}"


def create_signal_code() -> str:
    return uuid.uuid4().hex[:8].upper()


def build_chart_url(symbol: str) -> str:
    clean = symbol.replace("/", "").upper()
    return f"https://www.tradingview.com/chart/?symbol={clean}"


def normalize_symbol(symbol: str) -> str:
    """
    Normalize common symbols into BASE/QUOTE format.
    """

    symbol = str(symbol).strip().upper()

    if "/" not in symbol and len(symbol) == 6:
        symbol = f"{symbol[:3]}/{symbol[3:]}"

    return symbol


# ============================================================
# SIGNAL CREATION
# ============================================================

def create_signal(
    symbol: str,
    *,
    minimum_score: int = FREE_SIGNAL_SCORE,
    interval: str = "15min",
) -> Optional[dict[str, Any]]:
    """
    Build a qualified trading signal.

    Pipeline:

        15M data
            ↓
        indicators
            ↓
        1H trend
            ↓
        scoring engine
            ↓
        structural price action
            ↓
        risk profile
            ↓
        RR validation
            ↓
        final signal
    """

    symbol = normalize_symbol(symbol)

    # --------------------------------------------------------
    # 1. Validate minimum score
    # --------------------------------------------------------

    try:
        minimum_score = int(minimum_score)
    except (TypeError, ValueError):
        minimum_score = int(FREE_SIGNAL_SCORE)

    minimum_score = max(0, minimum_score)

    # --------------------------------------------------------
    # 2. Load 15M market data
    # --------------------------------------------------------

    try:
        df = get_data(
            symbol,
            interval=interval,
        )
    except Exception:
        return None

    if df is None or df.empty:
        return None

    # --------------------------------------------------------
    # 3. Calculate 15M indicators
    # --------------------------------------------------------

    try:
        df = calculate_indicators(df)
    except Exception:
        return None

    if len(df) < 2:
        return None

    # --------------------------------------------------------
    # 4. Extract latest 15M values
    # --------------------------------------------------------

    try:
        row = df.iloc[-1]
        previous_row = df.iloc[-2]

        close = float(row["close"])
        candle_open = float(row["open"])

        ema9 = float(row["ema9"])
        ema21 = float(row["ema21"])
        rsi = float(row["rsi"])

        macd = float(row["macd"])
        macd_signal = float(row["macd_signal"])

        previous_macd = float(previous_row["macd"])
        previous_macd_signal = float(
            previous_row["macd_signal"]
        )

        atr = float(row["atr"])

    except (KeyError, TypeError, ValueError):
        return None

    # --------------------------------------------------------
    # 5. Validate indicator values
    # --------------------------------------------------------

    numeric_values = (
        close,
        candle_open,
        ema9,
        ema21,
        rsi,
        macd,
        macd_signal,
        previous_macd,
        previous_macd_signal,
        atr,
    )

    if any(pd.isna(value) for value in numeric_values):
        return None

    if close <= 0 or atr <= 0:
        return None

    # --------------------------------------------------------
    # 6. Load 1H data
    # --------------------------------------------------------

    try:
        higher_df = get_data(
            symbol,
            interval="1h",
        )

        if higher_df is None or higher_df.empty:
            return None

        higher_df = calculate_indicators(higher_df)

        if higher_df.empty:
            return None

        higher_row = higher_df.iloc[-1]

        higher_ema9 = float(
            higher_row["ema9"]
        )

        higher_ema21 = float(
            higher_row["ema21"]
        )

    except Exception:
        return None

    if (
        pd.isna(higher_ema9)
        or pd.isna(higher_ema21)
    ):
        return None

    # --------------------------------------------------------
    # 7. Run scoring engine
    # --------------------------------------------------------

    try:
        scoring = score_signal(
            ema9=ema9,
            ema21=ema21,
            higher_ema9=higher_ema9,
            higher_ema21=higher_ema21,
            rsi=rsi,
            macd=macd,
            macd_signal=macd_signal,
            previous_macd=previous_macd,
            previous_macd_signal=previous_macd_signal,
            candle_open=candle_open,
            candle_close=close,
            atr=atr,
            minimum_score=minimum_score,
        )

    except Exception:
        return None

    if not scoring:
        return None

    if not scoring.get("valid"):
        return None

    direction = scoring.get("direction")

    if direction not in {"BUY", "SELL"}:
        return None

    try:
        score = int(
            scoring.get("score") or 0
        )
    except (TypeError, ValueError):
        return None

    if score < minimum_score:
        return None

    # --------------------------------------------------------
    # 8. Extract scoring information
    # --------------------------------------------------------

    reasons = list(
        scoring.get("reasons") or []
    )

    opposite_reasons = list(
        scoring.get("opposite_reasons") or []
    )

    # The current scoring.py returns no structural PA object.
    # Keep this optional so the generator remains compatible
    # with an upgraded scoring engine that adds it later.
    price_action = (
        scoring.get("price_action")
        or {}
    )

    indicator_confirmation = (
        scoring.get("indicator_confirmation")
        or {}
    )

    # --------------------------------------------------------
    # 9. Determine crypto market
    # --------------------------------------------------------

    is_crypto = (
        symbol in CRYPTO_SYMBOL_MAP
    )

    # --------------------------------------------------------
    # 10. Strong signal quality gate
    # --------------------------------------------------------
    #
    # 90+ requires genuine timeframe alignment.
    # The scoring engine itself enforces this.
    #
    # We do NOT duplicate scoring conditions here.
    # This prevents signal_generator.py from fighting
    # scoring.py.

    if score < 90:
        return None

    # --------------------------------------------------------
    # 11. Optional confirmation checks
    # --------------------------------------------------------

    rsi_ok = indicator_confirmation.get(
        "rsi_ok"
    )

    macd_ok = indicator_confirmation.get(
        "macd_ok"
    )

    # Only enforce these if the scoring engine supplies
    # explicit confirmation flags.
    #
    # This keeps compatibility with the scoring.py you
    # currently sent, which does not return these fields.
    if indicator_confirmation:
        if rsi_ok is False:
            return None

        if macd_ok is False:
            return None

    # --------------------------------------------------------
    # 12. Build risk profile
    # --------------------------------------------------------

    try:
        risk = build_risk_profile(
            entry_price=close,
            atr=atr,
            direction=direction,
        )

    except Exception:
        return None

    if not risk:
        return None

    # --------------------------------------------------------
    # 13. Extract trade levels
    # --------------------------------------------------------

    try:
        entry_price = float(
            risk["entry_price"]
        )

        stop_loss = float(
            risk["stop_loss"]
        )

        tp1 = float(
            risk["tp1"]
        )

        tp2 = float(
            risk["tp2"]
        )

        tp3 = float(
            risk["tp3"]
        )

    except (KeyError, TypeError, ValueError):
        return None

    # --------------------------------------------------------
    # 14. Validate trade geometry
    # --------------------------------------------------------

    if (
        entry_price <= 0
        or stop_loss <= 0
        or tp1 <= 0
        or tp2 <= 0
        or tp3 <= 0
    ):
        return None

    if direction == "BUY":

        if not (
            stop_loss
            < entry_price
            < tp1
            <= tp2
            <= tp3
        ):
            return None

    elif direction == "SELL":

        if not (
            tp3
            <= tp2
            <= tp1
            < entry_price
            < stop_loss
        ):
            return None

    else:
        return None

    # --------------------------------------------------------
    # 15. Risk/reward validation
    # --------------------------------------------------------

    risk_distance = abs(
        entry_price - stop_loss
    )

    if risk_distance <= 0:
        return None

    rr_tp1 = abs(
        tp1 - entry_price
    ) / risk_distance

    rr_tp2 = abs(
        tp2 - entry_price
    ) / risk_distance

    rr_tp3 = abs(
        tp3 - entry_price
    ) / risk_distance

    # Hard TP3 R:R gate.
    if rr_tp3 < 2.0:
        return None

    # --------------------------------------------------------
    # 16. Optional structural invalidation
    # --------------------------------------------------------

    invalidation_price = price_action.get(
        "invalidation_price"
    )

    if invalidation_price is not None:

        try:
            invalidation_price = float(
                invalidation_price
            )
        except (TypeError, ValueError):
            invalidation_price = None

    if invalidation_price is not None:

        if direction == "BUY":
            if invalidation_price >= entry_price:
                return None

        elif direction == "SELL":
            if invalidation_price <= entry_price:
                return None

    # --------------------------------------------------------
    # 17. Signal strength
    # --------------------------------------------------------

    if score >= 105:
        signal_tier = "💎 STRONGER"

    elif score >= 100:
        signal_tier = "🔥 VERY STRONG"

    elif score >= 90:
        signal_tier = "🔥 STRONG"

    else:
        signal_tier = None

    if not signal_tier:
        return None

    # --------------------------------------------------------
    # 18. Quality flags
    # --------------------------------------------------------

    quality_flags = {
        "htf_aligned": (
            (
                direction == "BUY"
                and higher_ema9 > higher_ema21
            )
            or
            (
                direction == "SELL"
                and higher_ema9 < higher_ema21
            )
        ),

        "rsi_confirmation": (
            bool(rsi_ok)
            if rsi_ok is not None
            else None
        ),

        "macd_confirmation": (
            bool(macd_ok)
            if macd_ok is not None
            else None
        ),

        "price_action_available": bool(
            price_action
        ),
    }

    # --------------------------------------------------------
    # 19. Final signal
    # --------------------------------------------------------

    signal = {
        # Identity
        "symbol": symbol,
        "direction": direction,
        "signal_code": create_signal_code(),
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        # Scoring
        "score": score,
        "max_score": MAX_SCORE,
        "strength": signal_tier,
        "minimum_score": minimum_score,

        # Explanation
        "reasons": reasons,
        "opposite_reasons": opposite_reasons,
        "quality_flags": quality_flags,

        # Price action
        "price_action": price_action,
        "liquidity_level": price_action.get(
            "liquidity_level"
        ),
        "structure_level": price_action.get(
            "structure_level"
        ),
        "invalidation_price": invalidation_price,

        "entry_zone_low": price_action.get(
            "entry_zone_low"
        ),
        "entry_zone_high": price_action.get(
            "entry_zone_high"
        ),

        "displacement_body_atr": (
            price_action.get(
                "displacement_body_atr"
            )
        ),

        # Trade levels
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,

        # Compatibility
        "take_profit": tp3,

        # Risk/reward
        "rr_tp1": round(rr_tp1, 2),
        "rr_tp2": round(rr_tp2, 2),
        "rr_tp3": round(rr_tp3, 2),

        # Indicators
        "atr": atr,
        "rsi": rsi,
        "ema9": ema9,
        "ema21": ema21,
        "higher_ema9": higher_ema9,
        "higher_ema21": higher_ema21,
        "macd": macd,
        "macd_signal": macd_signal,

        # Market
        "is_crypto": is_crypto,
        "interval": interval,

        # Chart
        "chart_url": build_chart_url(
            symbol
        ),
    }

    return signal


# ============================================================
# DAILY MARKET LIMIT
# ============================================================

def market_can_receive_signal(
    symbol: str,
) -> bool:
    """
    Respect the configured per-market daily signal limit.
    """

    try:
        count = get_daily_signal_count(
            symbol
        )

        return (
            int(count)
            < int(
                MAX_SIGNALS_PER_MARKET_PER_DAY
            )
        )

    except Exception:
        # Do not block the signal engine if the
        # database temporarily fails.
        return True


# ============================================================
# FREE SIGNAL
# ============================================================

def generate_free_signal(
    symbol: str,
    interval: str = "15min",
) -> Optional[dict[str, Any]]:

    if not market_can_receive_signal(
        symbol
    ):
        return None

    return create_signal(
        symbol,
        minimum_score=FREE_SIGNAL_SCORE,
        interval=interval,
    )


# ============================================================
# VIP SIGNAL
# ============================================================

def generate_vip_signal(
    symbol: str,
    interval: str = "15min",
) -> Optional[dict[str, Any]]:

    return create_signal(
        symbol,
        minimum_score=VIP_SCAN_SCORE,
        interval=interval,
    )


# ============================================================
# DAILY COUNTER
# ============================================================

def mark_signal_posted(
    symbol: str,
) -> None:
    """
    Increment the daily market signal counter
    after successful delivery.
    """

    try:
        increment_daily_signal_count(
            symbol
        )

    except Exception:
        pass


# ============================================================
# SIGNAL HELPERS
# ============================================================

def get_score(
    signal: dict[str, Any],
) -> int:

    try:
        return int(
            signal.get("score") or 0
        )

    except (TypeError, ValueError):
        return 0


def get_signal_key(
    signal: dict[str, Any],
) -> str:

    symbol = str(
        signal.get("symbol") or ""
    )

    direction = str(
        signal.get("direction") or ""
    )

    code = str(
        signal.get("signal_code") or ""
    )

    return (
        f"{symbol}:"
        f"{direction}:"
        f"{code}"
    )


# ============================================================
# PUBLIC API
# ============================================================

__all__ = [
    "price_format",
    "create_signal_code",
    "build_chart_url",
    "normalize_symbol",
    "create_signal",
    "generate_free_signal",
    "generate_vip_signal",
    "market_can_receive_signal",
    "mark_signal_posted",
    "get_score",
    "get_signal_key",
]
