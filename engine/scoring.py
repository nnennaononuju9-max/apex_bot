from __future__ import annotations

from typing import Any, Dict, List, Tuple

MAX_SCORE = 110


def get_strength(score: float | int) -> str:
    """Map numeric score to strength label."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "WEAK"
    if s >= 90:
        return "VERY STRONG"
    if s >= 75:
        return "STRONG"
    if s >= 60:
        return "MODERATE"
    return "WEAK"


def _safe(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        if result != result:
            return default
        return result
    except (TypeError, ValueError):
        return default


def score_signal(
    *,
    direction: str,
    ema9: float,
    ema21: float,
    rsi: float,
    macd: float,
    macd_signal: float,
    atr: float = 0.0,
    close: float = 0.0,
) -> Tuple[int, List[str]]:
    """
    Convert technical conditions into a 0-110 score.

    Returns (score, list_of_reasons).
    """
    direction = str(direction).upper().strip()
    reasons: List[str] = []
    score = 0

    ema9_v = _safe(ema9)
    ema21_v = _safe(ema21)
    rsi_v = _safe(rsi)
    macd_v = _safe(macd)
    macd_sig = _safe(macd_signal)

    # Trend / EMA alignment (max 35)
    if direction == "BUY":
        if ema9_v > ema21_v:
            score += 25
            reasons.append("EMA9 above EMA21 (bullish trend)")
            if close and close > ema9_v:
                score += 10
                reasons.append("Price above EMA9")
        else:
            reasons.append("EMA not aligned for BUY")
    elif direction == "SELL":
        if ema9_v < ema21_v:
            score += 25
            reasons.append("EMA9 below EMA21 (bearish trend)")
            if close and close < ema9_v:
                score += 10
                reasons.append("Price below EMA9")
        else:
            reasons.append("EMA not aligned for SELL")

    # RSI (max 30)
    if direction == "BUY":
        if 45 <= rsi_v <= 68:
            score += 30
            reasons.append(f"RSI supportive for BUY ({rsi_v:.1f})")
        elif 40 <= rsi_v < 45 or 68 < rsi_v <= 72:
            score += 15
            reasons.append(f"RSI mildly supportive ({rsi_v:.1f})")
        else:
            reasons.append(f"RSI not ideal for BUY ({rsi_v:.1f})")
    elif direction == "SELL":
        if 32 <= rsi_v <= 55:
            score += 30
            reasons.append(f"RSI supportive for SELL ({rsi_v:.1f})")
        elif 28 <= rsi_v < 32 or 55 < rsi_v <= 60:
            score += 15
            reasons.append(f"RSI mildly supportive ({rsi_v:.1f})")
        else:
            reasons.append(f"RSI not ideal for SELL ({rsi_v:.1f})")

    # MACD (max 30)
    if direction == "BUY":
        if macd_v > macd_sig:
            score += 25
            reasons.append("MACD above signal (bullish)")
            if macd_v > 0:
                score += 5
                reasons.append("MACD histogram positive zone")
        else:
            reasons.append("MACD not aligned for BUY")
    elif direction == "SELL":
        if macd_v < macd_sig:
            score += 25
            reasons.append("MACD below signal (bearish)")
            if macd_v < 0:
                score += 5
                reasons.append("MACD histogram negative zone")
        else:
            reasons.append("MACD not aligned for SELL")

    # ATR presence (max 15) — volatility available for risk sizing
    if _safe(atr) > 0:
        score += 15
        reasons.append("ATR available for risk sizing")

    score = max(0, min(int(round(score)), MAX_SCORE))
    return score, reasons


def score_from_row(row: Dict[str, Any], direction: str) -> Tuple[int, List[str]]:
    """Convenience wrapper using a candle/indicator row dict."""
    return score_signal(
        direction=direction,
        ema9=_safe(row.get("ema9")),
        ema21=_safe(row.get("ema21")),
        rsi=_safe(row.get("rsi")),
        macd=_safe(row.get("macd")),
        macd_signal=_safe(row.get("macd_signal", row.get("macd_sig"))),
        atr=_safe(row.get("atr")),
        close=_safe(row.get("close")),
    )


__all__ = [
    "MAX_SCORE",
    "get_strength",
    "score_signal",
    "score_from_row",
]
