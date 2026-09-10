from __future__ import annotations

from typing import Any, Dict, List, Tuple

# ============================================================
# APEX SIGNAL SCORING ENGINE
# ============================================================
# Purpose:
# Convert technical conditions into a consistent 0-110 score.
#
# This file does NOT:
# - fetch market data
# - calculate indicators
# - send Telegram messages
# - access PostgreSQL
#
# Those responsibilities belong to other modules.
# ============================================================

WEAK_MIN = 70
MODERATE_MIN = 80
STRONG_MIN = 90
VERY_STRONG_MIN = 100
STRONGER_MIN = 105

MAX_SCORE = 110


def get_strength(score: int) -> str | None:
    """Return the human-readable strength level for a signal."""
    score = int(score)

    if score >= STRONGER_MIN:
        return "💎 STRONGER"

    if score >= VERY_STRONG_MIN:
        return "🔥 VERY STRONG"

    if score >= STRONG_MIN:
        return "🔥 STRONG"

    if score >= MODERATE_MIN:
        return "🟡 MODERATE"

    if score >= WEAK_MIN:
        return "⚠️ WEAK"

    return None


def clamp_score(score: int) -> int:
    """Keep a score safely inside the 0-110 range."""
    return max(0, min(int(score), MAX_SCORE))


def score_direction(
    *,
    ema9: float,
    ema21: float,
    higher_ema9: float,
    higher_ema21: float,
    rsi: float,
    macd: float,
    macd_signal: float,
    previous_macd: float,
    previous_macd_signal: float,
    candle_open: float,
    candle_close: float,
) -> Tuple[str | None, int, List[str], List[str]]:
    """
    Score BUY and SELL conditions.

    Maximum score:
        25  = lower-timeframe EMA alignment
        20  = higher-timeframe trend
        15  = RSI momentum
        20  = MACD direction
        10  = fresh MACD crossover
        20  = confirmation candle

        TOTAL = 110

    Returns:
        (
            direction,
            score,
            reasons,
            opposite_reasons,
        )

    If neither side reaches a meaningful score, direction is None.
    """
    buy_score = 0
    sell_score = 0

    buy_reasons: List[str] = []
    sell_reasons: List[str] = []

    # --------------------------------------------------------
    # 1. LOWER TIMEFRAME EMA ALIGNMENT — 25 POINTS
    # --------------------------------------------------------
    if ema9 > ema21:
        buy_score += 25
        buy_reasons.append("15M EMA bullish alignment (EMA9 > EMA21)")

    elif ema9 < ema21:
        sell_score += 25
        sell_reasons.append("15M EMA bearish alignment (EMA9 < EMA21)")

    # --------------------------------------------------------
    # 2. HIGHER TIMEFRAME TREND — 20 POINTS
    # --------------------------------------------------------
    if higher_ema9 > higher_ema21:
        buy_score += 20
        buy_reasons.append("1H higher-timeframe trend is bullish")

    elif higher_ema9 < higher_ema21:
        sell_score += 20
        sell_reasons.append("1H higher-timeframe trend is bearish")

    # --------------------------------------------------------
    # 3. RSI MOMENTUM — 15 POINTS
    # --------------------------------------------------------
    if 50 <= rsi <= 70:
        buy_score += 15
        buy_reasons.append(f"RSI confirms bullish momentum ({rsi:.1f})")

    elif 30 <= rsi < 50:
        sell_score += 15
        sell_reasons.append(f"RSI confirms bearish momentum ({rsi:.1f})")

    # --------------------------------------------------------
    # 4. MACD DIRECTION — 20 POINTS
    # --------------------------------------------------------
    if macd > macd_signal:
        buy_score += 20
        buy_reasons.append("MACD confirms bullish momentum")

    elif macd < macd_signal:
        sell_score += 20
        sell_reasons.append("MACD confirms bearish momentum")

    # --------------------------------------------------------
    # 5. FRESH MACD CROSSOVER — 10 POINTS
    # --------------------------------------------------------
    bullish_cross = (
        macd > macd_signal
        and previous_macd <= previous_macd_signal
    )

    bearish_cross = (
        macd < macd_signal
        and previous_macd >= previous_macd_signal
    )

    if bullish_cross:
        buy_score += 10
        buy_reasons.append("Fresh bullish MACD crossover")

    elif bearish_cross:
        sell_score += 10
        sell_reasons.append("Fresh bearish MACD crossover")

    # --------------------------------------------------------
    # 6. CONFIRMATION CANDLE — 20 POINTS
    # --------------------------------------------------------
    if candle_close > candle_open:
        buy_score += 20
        buy_reasons.append("15M candle confirms bullish price action")

    elif candle_close < candle_open:
        sell_score += 20
        sell_reasons.append("15M candle confirms bearish price action")

    # --------------------------------------------------------
    # FINAL DIRECTION
    # --------------------------------------------------------
    buy_score = clamp_score(buy_score)
    sell_score = clamp_score(sell_score)

    if buy_score > sell_score:
        return "BUY", buy_score, buy_reasons, sell_reasons

    if sell_score > buy_score:
        return "SELL", sell_score, sell_reasons, buy_reasons

    return None, 0, [], []


def score_signal(
    *,
    ema9: float,
    ema21: float,
    higher_ema9: float,
    higher_ema21: float,
    rsi: float,
    macd: float,
    macd_signal: float,
    previous_macd: float,
    previous_macd_signal: float,
    candle_open: float,
    candle_close: float,
    minimum_score: int = WEAK_MIN,
) -> Dict[str, Any]:
    """
    Main public scoring function.

    Returns a consistent dictionary that the signal generator
    can use without knowing how the scoring system works.
    """
    direction, score, reasons, opposite_reasons = score_direction(
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
        candle_close=candle_close,
    )

    score = clamp_score(score)
    minimum_score = max(0, int(minimum_score))

    valid = (
        direction is not None
        and score >= minimum_score
    )

    if not valid:
        return {
            "valid": False,
            "direction": None,
            "score": score,
            "max_score": MAX_SCORE,
            "strength": None,
            "reasons": [],
            "opposite_reasons": opposite_reasons,
        }

    return {
        "valid": True,
        "direction": direction,
        "score": score,
        "max_score": MAX_SCORE,
        "strength": get_strength(score),
        "reasons": reasons,
        "opposite_reasons": opposite_reasons,
    }


def is_vip_score(score: int, minimum_score: int = STRONG_MIN) -> bool:
    """Return True when a signal qualifies for VIP delivery."""
    return int(score) >= int(minimum_score)


def is_elite_score(score: int) -> bool:
    """Return True for the highest Apex signal tier."""
    return int(score) >= STRONGER_MIN


def score_label(score: int) -> str:
    """Return a safe display label for any score."""
    strength = get_strength(score)

    if strength:
        return strength

    return "⚪ NO QUALIFYING SETUP"
