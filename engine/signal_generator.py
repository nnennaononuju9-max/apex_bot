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
    Build a signal for a market if score meets minimum_score.
    Returns None when data/score is insufficient.
    """
    symbol = str(symbol).strip().upper()
    if "/" not in symbol and len(symbol) == 6:
        # e.g. EURUSD -> EUR/USD heuristic
        symbol = symbol[:3] + "/" + symbol[3:]

    df = get_data(symbol, interval=interval)
    if df is None or df.empty:
        return None

    try:
        df = calculate_indicators(df)
    except Exception:
        return None

    row = _latest_row(df)
    close = float(row.get("close") or 0)
    ema9 = float(row.get("ema9") or 0)
    ema21 = float(row.get("ema21") or 0)
    rsi = float(row.get("rsi") or 0)
    macd = float(row.get("macd") or 0)
    macd_signal = float(row.get("macd_signal") or row.get("macd_sig") or 0)
    atr = float(row.get("atr") or 0)

    if close <= 0 or atr <= 0:
        return None

    # Direction from EMA trend
    if ema9 > ema21:
        direction = "BUY"
    elif ema9 < ema21:
        direction = "SELL"
    else:
        return None

    score, reasons = score_signal(
        direction=direction,
        ema9=ema9,
        ema21=ema21,
        rsi=rsi,
        macd=macd,
        macd_signal=macd_signal,
        atr=atr,
        close=close,
    )

    if score < int(minimum_score):
        return None

    try:
        risk = build_risk_profile(
            entry_price=close,
            atr=atr,
            direction=direction,
        )
    except Exception:
        return None

    is_crypto = symbol in CRYPTO_SYMBOL_MAP or symbol.replace("/", "") in {
        v.replace("USDT", "/USD") for v in CRYPTO_SYMBOL_MAP.values()
    }
    is_crypto = symbol in CRYPTO_SYMBOL_MAP

    signal = {
        "symbol": symbol,
        "direction": direction,
        "score": int(score),
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
