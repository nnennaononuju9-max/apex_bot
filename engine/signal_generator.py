from future import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import uuid

import numpy as np
import pandas as pd

from config import (
CANDLE_LIMIT,
FREE_SIGNAL_SCORE,
VIP_SCAN_SCORE,
MAX_SIGNALS_PER_MARKET_PER_DAY,
TWELVE_DATA_API_KEY,
BINANCE_API_KEY,
)

from database import (
get_daily_signal_count,
increment_daily_signal_count,
)

from .market_data import (
get_data,
get_latest_price,
)

from .indicators import calculate_indicators

from .scoring import (
MAX_SCORE,
STRONGER_MIN,
get_strength,
score_signal,
)

from .risk import (
build_risk_profile,
)

============================================================

APEX SIGNAL GENERATOR

============================================================

This module is the bridge between:

MARKET DATA

↓

INDICATORS

↓

SCORING

↓

RISK MANAGEMENT

↓

FINAL SIGNAL

It does NOT send Telegram messages.

It does NOT contain Telegram handlers.

It does NOT contain database schema logic.

============================================================

LOWER_TIMEFRAME = "15min"
HIGHER_TIMEFRAME = "1h"

============================================================

MARKETS

============================================================

MARKETS = [
# Crypto
"BTC/USD",
"ETH/USD",
"SOL/USD",
"BNB/USD",
"XRP/USD",
"DOGE/USD",
"ADA/USD",

# Forex / Gold
"XAU/USD",
"EUR/USD",
"GBP/USD",
"USD/JPY",

]

CRYPTO_SYMBOL_MAP = {
"BTC/USD": "BTCUSDT",
"ETH/USD": "ETHUSDT",
"SOL/USD": "SOLUSDT",
"BNB/USD": "BNBUSDT",
"XRP/USD": "XRPUSDT",
"DOGE/USD": "DOGEUSDT",
"ADA/USD": "ADAUSDT",
}

============================================================

PRICE FORMATTING

============================================================

def price_format(price: float) -> str:
"""Format prices appropriately for different markets."""

price = float(price)

if price >= 1000:
    return f"{price:,.2f}"

if price >= 10:
    return f"{price:.3f}"

if price >= 1:
    return f"{price:.4f}"

return f"{price:.6f}"

============================================================

SIGNAL ID

============================================================

def create_signal_code() -> str:
"""Create a unique signal identifier."""

timestamp = datetime.now(timezone.utc).strftime(
    "%Y%m%d%H%M%S"
)

random_part = uuid.uuid4().hex[:6].upper()

return f"{timestamp}-{random_part}"

============================================================

TRADINGVIEW CHART

============================================================

def build_chart_url(symbol: str) -> str:
"""Build a TradingView chart URL."""

if symbol in CRYPTO_SYMBOL_MAP:
    pair = CRYPTO_SYMBOL_MAP[symbol]

    return (
        "https://www.tradingview.com/chart/"
        f"?symbol=BINANCE:{pair}"
    )

clean_symbol = symbol.replace("/", "")

return (
    "https://www.tradingview.com/chart/"
    f"?symbol=FX:{clean_symbol}"
)

============================================================

DATA VALIDATION

============================================================

def _validate_dataframe(
df: Optional[pd.DataFrame],
) -> bool:
"""Verify that a candle dataframe is usable."""

if df is None:
    return False

if len(df) < 50:
    return False

required = {
    "datetime",
    "open",
    "high",
    "low",
    "close",
}

if not required.issubset(df.columns):
    return False

return True

============================================================

INDICATOR VALIDATION

============================================================

def _required_indicator_values(
current: pd.Series,
previous: pd.Series,
higher: pd.Series,
) -> list[Any]:
"""Collect values required by the scoring engine."""

return [
    current.get("ema9"),
    current.get("ema21"),
    current.get("rsi"),
    current.get("macd"),
    current.get("macd_signal"),
    current.get("atr"),
    previous.get("macd"),
    previous.get("macd_signal"),
    higher.get("ema9"),
    higher.get("ema21"),
]

def _indicators_are_valid(values: list[Any]) -> bool:
"""Return False if any required indicator is missing/NaN."""

for value in values:
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        return False

return True

============================================================

CORE SIGNAL GENERATOR

============================================================

def create_signal(
symbol: str,
minimum_score: int = FREE_SIGNAL_SCORE,
) -> Optional[dict[str, Any]]:
"""
Generate one validated algorithmic trading signal.

The signal requires:

    15M data
    +
    1H data
    +
    technical indicators
    +
    directional scoring
    +
    valid risk levels
"""

symbol = str(symbol).upper().strip()

# --------------------------------------------------------
# BASIC MARKET VALIDATION
# --------------------------------------------------------

if not symbol:
    return None

if symbol not in MARKETS:
    return None

# --------------------------------------------------------
# FETCH MULTI-TIMEFRAME DATA
# --------------------------------------------------------

df15 = get_data(
    symbol,
    LOWER_TIMEFRAME,
)

df1h = get_data(
    symbol,
    HIGHER_TIMEFRAME,
)

if not _validate_dataframe(df15):
    return None

if not _validate_dataframe(df1h):
    return None

# --------------------------------------------------------
# CALCULATE INDICATORS
# --------------------------------------------------------

df15 = calculate_indicators(df15)
df1h = calculate_indicators(df1h)

if len(df15) < 2 or len(df1h) < 1:
    return None

current = df15.iloc[-1]
previous = df15.iloc[-2]
higher = df1h.iloc[-1]

required_values = _required_indicator_values(
    current,
    previous,
    higher,
)

if not _indicators_are_valid(required_values):
    return None

# --------------------------------------------------------
# SCORE THE SETUP
# --------------------------------------------------------

scoring = score_signal(
    ema9=float(current["ema9"]),
    ema21=float(current["ema21"]),

    higher_ema9=float(higher["ema9"]),
    higher_ema21=float(higher["ema21"]),

    rsi=float(current["rsi"]),

    macd=float(current["macd"]),
    macd_signal=float(current["macd_signal"]),

    previous_macd=float(previous["macd"]),
    previous_macd_signal=float(previous["macd_signal"]),

    candle_open=float(current["open"]),
    candle_close=float(current["close"]),

    minimum_score=minimum_score,
)

if not scoring["valid"]:
    return None

direction = scoring["direction"]
score = int(scoring["score"])
reasons = list(scoring["reasons"])

if direction not in {"BUY", "SELL"}:
    return None

if score < minimum_score:
    return None

# --------------------------------------------------------
# PRICE + ATR
# --------------------------------------------------------

price = float(current["close"])
atr = float(current["atr"])

if not np.isfinite(price) or price <= 0:
    return None

if not np.isfinite(atr) or atr <= 0:
    # Conservative fallback.
    atr = price * 0.01

# --------------------------------------------------------
# RISK ENGINE
# --------------------------------------------------------

try:
    risk = build_risk_profile(
        entry_price=price,
        atr=atr,
        direction=direction,
    )

except (ValueError, TypeError):
    return None

if not risk.get("valid"):
    return None

stop_loss = float(risk["stop_loss"])
tp1 = float(risk["tp1"])
tp2 = float(risk["tp2"])
tp3 = float(risk["tp3"])

# --------------------------------------------------------
# FINAL SAFETY CHECK
# --------------------------------------------------------

if direction == "BUY":
    if not (
        stop_loss < price
        and tp1 > price
        and tp2 > tp1
        and tp3 > tp2
    ):
        return None

else:
    if not (
        stop_loss > price
        and tp1 < price
        and tp2 < tp1
        and tp3 < tp2
    ):
        return None

# --------------------------------------------------------
# MARKET TYPE
# --------------------------------------------------------

is_crypto = symbol in CRYPTO_SYMBOL_MAP

# --------------------------------------------------------
# SIGNAL OBJECT
# --------------------------------------------------------

signal_code = create_signal_code()

strength = get_strength(score)

if strength is None:
    return None

return {
    "signal_code": signal_code,

    "symbol": symbol,

    "is_crypto": is_crypto,

    "direction": direction,

    "score": score,

    "max_score": MAX_SCORE,

    "strength": strength,

    "stronger": score >= STRONGER_MIN,

    "price": price,

    "entry_price": price,

    "current_price": price,

    "atr": atr,

    "stop_loss": stop_loss,

    "take_profit": tp2,

    "tp1": tp1,

    "tp2": tp2,

    "tp3": tp3,

    "tp1_rr": float(risk["tp1_rr"]),

    "tp2_rr": float(risk["tp2_rr"]),

    "tp3_rr": float(risk["tp3_rr"]),

    "chart_url": build_chart_url(symbol),

    "reasons": reasons,

    "timeframe": "15M + 1H",

    "candle_time": current["datetime"],

    "generated_at": datetime.now(timezone.utc),

    "admin_only": score >= STRONGER_MIN,
}

============================================================

SIGNAL LIMITING

============================================================

def market_can_receive_signal(
symbol: str,
) -> bool:
"""
Check the daily signal limit for a market.

Database counting remains centralized in database.py.
"""

try:
    count = get_daily_signal_count(symbol)

    return int(count) < int(
        MAX_SIGNALS_PER_MARKET_PER_DAY
    )

except Exception:
    # Fail closed.
    #
    # If the database cannot confirm the daily count,
    # do not generate another paid/free signal.
    return False

============================================================

FREE SIGNAL

============================================================

def generate_free_signal(
symbol: str,
) -> Optional[dict[str, Any]]:
"""
Generate a signal eligible for the free channel.

Free threshold comes from config.py.
"""

if not market_can_receive_signal(symbol):
    return None

signal = create_signal(
    symbol,
    minimum_score=FREE_SIGNAL_SCORE,
)

if signal is None:
    return None

signal["admin_only"] = (
    signal["score"] >= STRONGER_MIN
)

return signal

============================================================

VIP SIGNAL

============================================================

def generate_vip_signal(
symbol: str,
) -> Optional[dict[str, Any]]:
"""
Generate a higher-threshold VIP signal.
"""

signal = create_signal(
    symbol,
    minimum_score=VIP_SCAN_SCORE,
)

if signal is None:
    return None

signal["admin_only"] = (
    signal["score"] >= STRONGER_MIN
)

return signal

============================================================

DAILY SIGNAL COUNTER

============================================================

def mark_signal_posted(
symbol: str,
) -> None:
"""Increment the database counter after a signal is posted."""

increment_daily_signal_count(symbol)

============================================================

SIGNAL QUALITY HELPERS

============================================================

def get_score(
signal: dict[str, Any],
) -> int:
"""Safely extract a signal score."""

try:
    return int(signal.get("score", 0))
except (TypeError, ValueError):
    return 0

def get_signal_key(
signal: dict[str, Any],
) -> str:
"""Return the unique key used by the signal manager."""

signal_code = signal.get("signal_code")

if signal_code:
    return str(signal_code)

symbol = signal.get("symbol", "UNKNOWN")
direction = signal.get("direction", "UNKNOWN")
candle_time = signal.get("candle_time", "")

return f"{symbol}:{direction}:{candle_time}"

============================================================

PUBLIC EXPORTS

============================================================

all = [
"MARKETS",
"CRYPTO_SYMBOL_MAP",
"LOWER_TIMEFRAME",
"HIGHER_TIMEFRAME",
"create_signal",
"generate_free_signal",
"generate_vip_signal",
"market_can_receive_signal",
"mark_signal_posted",
"get_score",
"get_signal_key",
"price_format",
]
