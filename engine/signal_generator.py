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
from .price_action import analyze_price_action
from .scoring import (
score_signal,
get_strength,
MAX_SCORE,
)
from .risk import build_risk_profile

============================================================

HELPERS

============================================================

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
clean = (
str(symbol)
.replace("/", "")
.replace("-", "")
.upper()
)

return (
    "https://www.tradingview.com/chart/"
    f"?symbol={clean}"
)

def normalize_symbol(symbol: str) -> str:
"""
Normalize common six-character forex symbols.

EURUSD -> EUR/USD
GBPUSD -> GBP/USD

Crypto symbols already containing "/" are preserved.
"""
symbol = str(symbol).strip().upper()

if "/" not in symbol and len(symbol) == 6:
    return f"{symbol[:3]}/{symbol[3:]}"

return symbol

============================================================

SIGNAL CREATION

============================================================

def create_signal(
symbol: str,
*,
minimum_score: int = FREE_SIGNAL_SCORE,
interval: str = "15min",
) -> Optional[dict[str, Any]]:
"""
Generate a complete trading signal.

Architecture:

    15M market data
          ↓
    technical indicators
          ↓
    1H trend confirmation
          ↓
    scoring engine
          ↓
    price-action confirmation
          ↓
    structural risk / TP calculation
          ↓
    final signal

Price action is used as a quality filter.

A setup must have:

    liquidity sweep
    reclaim
    displacement
    structure break
    retest

before it can be published.

Invalid or incomplete market data produces no signal.
"""

symbol = normalize_symbol(symbol)

try:
    minimum_score = int(minimum_score)
except (TypeError, ValueError):
    minimum_score = FREE_SIGNAL_SCORE

minimum_score = max(0, minimum_score)

# --------------------------------------------------------
# 1. LOWER TIMEFRAME DATA
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
# 2. CALCULATE LOWER-TIMEFRAME INDICATORS
# --------------------------------------------------------

try:
    df = calculate_indicators(df)
except Exception:
    return None

if len(df) < 2:
    return None

# --------------------------------------------------------
# 3. READ LATEST CLOSED CANDLE
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

    atr = float(row["atr"])

    previous_macd = float(
        previous_row["macd"]
    )

    previous_macd_signal = float(
        previous_row["macd_signal"]
    )

except (
    TypeError,
    ValueError,
    KeyError,
    IndexError,
):
    return None

# --------------------------------------------------------
# 4. VALIDATE LOWER-TIMEFRAME VALUES
# --------------------------------------------------------

values = (
    close,
    candle_open,
    ema9,
    ema21,
    rsi,
    macd,
    macd_signal,
    atr,
    previous_macd,
    previous_macd_signal,
)

if any(
    pd.isna(value)
    for value in values
):
    return None

if close <= 0:
    return None

if candle_open <= 0:
    return None

if atr <= 0:
    return None

# --------------------------------------------------------
# 5. HIGHER-TIMEFRAME DATA
# --------------------------------------------------------

try:
    higher_df = get_data(
        symbol,
        interval="1h",
    )
except Exception:
    return None

if higher_df is None or higher_df.empty:
    return None

try:
    higher_df = calculate_indicators(
        higher_df
    )

    if higher_df.empty:
        return None

    higher_row = higher_df.iloc[-1]

    higher_ema9 = float(
        higher_row["ema9"]
    )

    higher_ema21 = float(
        higher_row["ema21"]
    )

except (
    TypeError,
    ValueError,
    KeyError,
    IndexError,
):
    return None

if (
    pd.isna(higher_ema9)
    or pd.isna(higher_ema21)
):
    return None

# --------------------------------------------------------
# 6. RUN SCORING ENGINE
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

# --------------------------------------------------------
# 7. READ SCORE
# --------------------------------------------------------

direction = str(
    scoring.get("direction") or ""
).upper()

score = int(
    scoring.get("score") or 0
)

reasons = list(
    scoring.get("reasons") or []
)

opposite_reasons = list(
    scoring.get("opposite_reasons") or []
)

if direction not in {
    "BUY",
    "SELL",
}:
    return None

if score < minimum_score:
    return None

# --------------------------------------------------------
# 8. PRICE ACTION / MARKET STRUCTURE
# --------------------------------------------------------
#
# This is the new integration.
#
# Price action confirms whether the scored setup also
# has actual market-structure evidence.
# --------------------------------------------------------

try:
    price_action = analyze_price_action(
        df,
        direction=direction,
        atr=atr,
    )
except Exception:
    return None

if not price_action:
    return None

# --------------------------------------------------------
# 9. REQUIRE COMPLETE PRICE-ACTION SEQUENCE
# --------------------------------------------------------
#
# Required:
#
#   sweep
#       ↓
#   reclaim
#       ↓
#   displacement
#       ↓
#   structure break
#       ↓
#   retest
#
# If the sequence is incomplete, do not publish.
# --------------------------------------------------------

if not price_action.get(
    "sequence_complete",
    False,
):
    return None

# --------------------------------------------------------
# 10. DETERMINE CRYPTO
# --------------------------------------------------------

is_crypto = (
    symbol in CRYPTO_SYMBOL_MAP
)

# --------------------------------------------------------
# 11. STRUCTURAL INVALIDATION
# --------------------------------------------------------

invalidation_price = price_action.get(
    "invalidation_price"
)

# --------------------------------------------------------
# 12. BUILD RISK PROFILE
# --------------------------------------------------------
#
# The price-action engine provides structural
# invalidation when available.
#
# Risk.py then places the ATR buffer around it.
# --------------------------------------------------------

try:
    risk = build_risk_profile(
        entry_price=close,
        atr=atr,
        direction=direction,
        invalidation_price=invalidation_price,
    )
except Exception:
    return None

if not risk:
    return None

# --------------------------------------------------------
# 13. EXTRACT TRADE LEVELS
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

    rr_tp1 = float(
        risk.get("rr_tp1") or 0
    )

    rr_tp2 = float(
        risk.get("rr_tp2") or 0
    )

    rr_tp3 = float(
        risk.get("rr_tp3") or 0
    )

    risk_distance = float(
        risk.get("risk_distance") or 0
    )

    risk_atr = float(
        risk.get("risk_atr") or 0
    )

except (
    TypeError,
    ValueError,
    KeyError,
):
    return None

# --------------------------------------------------------
# 14. TRADE GEOMETRY VALIDATION
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
        stop_loss
        > entry_price
        > tp1
        >= tp2
        >= tp3
    ):
        return None

# --------------------------------------------------------
# 15. HARD TP3 R:R FILTER
# --------------------------------------------------------

if rr_tp3 < 2.0:
    return None

# --------------------------------------------------------
# 16. SIGNAL STRENGTH
# --------------------------------------------------------

strength = get_strength(score)

if not strength:
    return None

# --------------------------------------------------------
# 17. QUALITY FLAGS
# --------------------------------------------------------

reason_text = " ".join(
    str(reason)
    for reason in reasons
)

quality_flags = {
    "lower_timeframe_ema": (
        "15M EMA" in reason_text
    ),

    "higher_timeframe_trend": (
        "1H higher-timeframe trend"
        in reason_text
    ),

    "rsi_confirmation": (
        "RSI" in reason_text
    ),

    "macd_confirmation": (
        "MACD confirms" in reason_text
    ),

    "macd_crossover": (
        "Fresh bullish MACD crossover"
        in reason_text
        or
        "Fresh bearish MACD crossover"
        in reason_text
    ),

    "candle_confirmation": (
        "15M candle confirms"
        in reason_text
    ),

    # New market-structure flags.
    "liquidity_sweep": bool(
        price_action.get("sweep")
    ),

    "liquidity_reclaim": bool(
        price_action.get("reclaim")
    ),

    "displacement": bool(
        price_action.get("displacement")
    ),

    "structure_break": bool(
        price_action.get("structure_break")
    ),

    "retest": bool(
        price_action.get("retest")
    ),

    "price_action_sequence": bool(
        price_action.get(
            "sequence_complete"
        )
    ),
}

# --------------------------------------------------------
# 18. ADD PRICE-ACTION REASONS
# --------------------------------------------------------

reasons = list(reasons)

if price_action.get("sweep"):
    reasons.append(
        "Liquidity sweep confirmed"
    )

if price_action.get("reclaim"):
    reasons.append(
        "Liquidity level reclaimed"
    )

if price_action.get("displacement"):
    reasons.append(
        "Displacement confirmed"
    )

if price_action.get("structure_break"):
    reasons.append(
        "Market structure break confirmed"
    )

if price_action.get("retest"):
    reasons.append(
        "Structure retest confirmed"
    )

# --------------------------------------------------------
# 19. FINAL SIGNAL
# --------------------------------------------------------

signal = {
    # ----------------------------------------------
    # Identity
    # ----------------------------------------------

    "symbol": symbol,

    "direction": direction,

    "signal_code": create_signal_code(),

    "generated_at": (
        datetime.now(
            timezone.utc
        ).isoformat()
    ),

    # ----------------------------------------------
    # Scoring
    # ----------------------------------------------

    "score": score,

    "max_score": MAX_SCORE,

    "minimum_score": (
        minimum_score
    ),

    "strength": strength,

    "reasons": reasons,

    "opposite_reasons": (
        opposite_reasons
    ),

    "quality_flags": quality_flags,

    # ----------------------------------------------
    # Market
    # ----------------------------------------------

    "is_crypto": is_crypto,

    "interval": interval,

    "timeframe": (
        f"{interval} + 1H"
    ),

    # ----------------------------------------------
    # Price
    # ----------------------------------------------

    "entry_price": entry_price,

    "stop_loss": stop_loss,

    "tp1": tp1,

    "tp2": tp2,

    "tp3": tp3,

    # ----------------------------------------------
    # Risk / Reward
    # ----------------------------------------------

    "rr_tp1": rr_tp1,

    "rr_tp2": rr_tp2,

    "rr_tp3": rr_tp3,

    "risk_distance": risk_distance,

    "risk_atr": risk_atr,

    # ----------------------------------------------
    # Structural levels
    # ----------------------------------------------

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
            "displacement_body_atr",
            0.0,
        )
    ),

    # ----------------------------------------------
    # Indicators
    # ----------------------------------------------

    "atr": atr,

    "rsi": rsi,

    "ema9": ema9,

    "ema21": ema21,

    "higher_ema9": higher_ema9,

    "higher_ema21": higher_ema21,

    "macd": macd,

    "macd_signal": macd_signal,

    # ----------------------------------------------
    # Chart
    # ----------------------------------------------

    "chart_url": (
        build_chart_url(symbol)
    ),
}

return signal

============================================================

DAILY MARKET LIMIT

============================================================

def market_can_receive_signal(
symbol: str,
) -> bool:
"""
Check whether the market has reached its
daily automatic signal limit.
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
    # Fail open so a temporary database problem
    # does not destroy signal generation.
    return True

============================================================

FREE SIGNAL

============================================================

def generate_free_signal(
symbol: str,
interval: str = "15min",
) -> Optional[dict[str, Any]]:
"""
Generate a signal meeting the free-channel
minimum score.
"""

if not market_can_receive_signal(
    symbol
):
    return None

return create_signal(
    symbol,
    minimum_score=FREE_SIGNAL_SCORE,
    interval=interval,
)

============================================================

VIP SIGNAL

============================================================

def generate_vip_signal(
symbol: str,
interval: str = "15min",
) -> Optional[dict[str, Any]]:
"""
Generate a VIP-quality signal.

VIP generation does not increment the daily
counter by itself. The counter is incremented
only after actual delivery.
"""

if not market_can_receive_signal(
    symbol
):
    return None

return create_signal(
    symbol,
    minimum_score=VIP_SCAN_SCORE,
    interval=interval,
)

============================================================

MARK SIGNAL POSTED

============================================================

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

============================================================

SCORE HELPER

============================================================

def get_score(
signal: dict[str, Any],
) -> int:
try:
return int(
signal.get("score") or 0
)
except (
TypeError,
ValueError,
):
return 0

============================================================

SIGNAL KEY

============================================================

def get_signal_key(
signal: dict[str, Any],
) -> str:
"""
Build a unique key for the generated setup.

signal_code makes every generated setup unique
while symbol/direction make logs easier to understand.
"""

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

============================================================

PUBLIC API

============================================================

all = [
"price_format",
"create_signal_code",
"build_chart_url",
"create_signal",
"generate_free_signal",
"generate_vip_signal",
"market_can_receive_signal",
"mark_signal_posted",
"get_score",
"get_signal_key",
]
