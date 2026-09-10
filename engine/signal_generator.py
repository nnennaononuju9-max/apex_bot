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
from .scoring import score_signal, get_strength, MAX_SCORE
from .risk import build_risk_profile


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


def _latest_row(df: pd.DataFrame) -> dict[str, Any]:
    row = df.iloc[-1]
    return {k: row[k] for k in df.columns}


def create_signal(
    symbol: str,
    *,
    minimum_score: int = FREE_SIGNAL_SCORE,
    interval: str = "15min",
) -> Optional[dict[str, Any]]:
    """
    Build a signal using:
    - 15-minute indicators for entry confirmation
    - 1-hour EMA trend confirmation
    - scoring.py's current scoring interface
    """
    symbol = str(symbol).strip().upper()

    if "/" not in symbol and len(symbol) == 6:
        symbol = symbol[:3] + "/" + symbol[3:]

    # --------------------------------------------------------
    # 1. Get lower-timeframe data
    # --------------------------------------------------------

    df = get_data(symbol, interval=interval)

    if df is None or df.empty:
        return None

    try:
        df = calculate_indicators(df)
    except Exception:
        return None

    if len(df) < 2:
        return None

    # --------------------------------------------------------
    # 2. Get latest 15M indicator values
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

        previous_macd = float(previous_row["macd"])
        previous_macd_signal = float(
            previous_row["macd_signal"]
        )

    except (TypeError, ValueError, KeyError):
        return None

    if (
        close <= 0
        or atr <= 0
        or pd.isna(ema9)
        or pd.isna(ema21)
        or pd.isna(rsi)
        or pd.isna(macd)
        or pd.isna(macd_signal)
        or pd.isna(previous_macd)
        or pd.isna(previous_macd_signal)
    ):
        return None

    # --------------------------------------------------------
    # 3. Get higher-timeframe (1H) data
    # --------------------------------------------------------

    try:
        higher_df = get_data(
            symbol,
            interval="1h",
        )

        if higher_df is None or higher_df.empty:
            return None

        higher_df = calculate_indicators(higher_df)

        higher_row = higher_df.iloc[-1]

        higher_ema9 = float(higher_row["ema9"])
        higher_ema21 = float(higher_row["ema21"])

    except (TypeError, ValueError, KeyError, IndexError):
        return None
    except Exception:
        return None

    if (
        pd.isna(higher_ema9)
        or pd.isna(higher_ema21)
    ):
        return None

    # --------------------------------------------------------
    # 4. Run the current scoring engine
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
            minimum_score=int(minimum_score),
        )
    except Exception:
        return None

    if not scoring.get("valid"):
        return None

    direction = scoring.get("direction")
    score = int(scoring.get("score") or 0)
    reasons = scoring.get("reasons") or []

    if not direction or score < int(minimum_score):
        return None

    # --------------------------------------------------------
    # 5. Build risk profile
    # --------------------------------------------------------

    try:
        risk = build_risk_profile(
            entry_price=close,
            atr=atr,
            direction=direction,
        )
    except Exception:
        return None

    # --------------------------------------------------------
    # 6. Determine whether this is crypto
    # --------------------------------------------------------

    is_crypto = symbol in CRYPTO_SYMBOL_MAP

    # --------------------------------------------------------
    # 7. Build final signal
    # --------------------------------------------------------

    signal = {
        "symbol": symbol,
        "direction": direction,
        "score": score,
        "strength": get_strength(score),
        "reasons": reasons,

        "entry_price": risk["entry_price"],
        "stop_loss": risk["stop_loss"],
        "tp1": risk["tp1"],
        "tp2": risk["tp2"],
        "tp3": risk["tp3"],

        "rr_tp1": risk.get("rr_tp1"),
        "rr_tp2": risk.get("rr_tp2"),
        "rr_tp3": risk.get("rr_tp3"),

        "atr": atr,
        "rsi": rsi,
        "ema9": ema9,
        "ema21": ema21,
        "higher_ema9": higher_ema9,
        "higher_ema21": higher_ema21,
        "macd": macd,
        "macd_signal": macd_signal,

        "is_crypto": is_crypto,
        "interval": interval,

        "signal_code": create_signal_code(),
        "chart_url": build_chart_url(symbol),
        "generated_at": datetime.now(timezone.utc).isoformat(),

        "max_score": MAX_SCORE,
        "minimum_score": int(minimum_score),
    }

    return signal

def market_can_receive_signal(symbol: str) -> bool:
    """Respect per-market daily signal limit."""
    try:
        count = get_daily_signal_count(symbol)
        return int(count) < int(MAX_SIGNALS_PER_MARKET_PER_DAY)
    except Exception:
        # If DB helpers are unavailable, allow signal
        return True


def generate_free_signal(symbol: str, interval: str = "15min") -> Optional[dict[str, Any]]:
    if not market_can_receive_signal(symbol):
        return None
    return create_signal(
        symbol,
        minimum_score=FREE_SIGNAL_SCORE,
        interval=interval,
    )


def generate_vip_signal(symbol: str, interval: str = "15min") -> Optional[dict[str, Any]]:
    return create_signal(
        symbol,
        minimum_score=VIP_SCAN_SCORE,
        interval=interval,
    )


def mark_signal_posted(symbol: str) -> None:
    """Increment daily counter after a signal is delivered."""
    try:
        increment_daily_signal_count(symbol)
    except Exception:
        pass


def get_score(signal: dict[str, Any]) -> int:
    try:
        return int(signal.get("score") or 0)
    except (TypeError, ValueError):
        return 0


def get_signal_key(signal: dict[str, Any]) -> str:
    symbol = str(signal.get("symbol") or "")
    direction = str(signal.get("direction") or "")
    code = str(signal.get("signal_code") or "")
    return f"{symbol}:{direction}:{code}"


__all__ = [
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
