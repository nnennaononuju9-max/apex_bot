from __future__ import annotations

from typing import Any, Dict, List, Tuple

# ============================================================
# APEX SIGNAL SCORING ENGINE
# ============================================================
# Purpose:
# Convert technical conditions into a consistent 0-110 score.
#
# Higher scores require stronger multi-timeframe confluence.
# ============================================================

WEAK_MIN = 70
MODERATE_MIN = 80
STRONG_MIN = 90
VERY_STRONG_MIN = 100
STRONGER_MIN = 105

MAX_SCORE = 110


def get_strength(score: int) -> str | None:
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
    return max(0, min(int(score), MAX_SCORE))


def _rsi_score(rsi: float) -> tuple[str | None, int, str]:
    """
    More selective RSI scoring.

    Neutral RSI should not receive a full momentum score.
    Extreme RSI is also not automatically treated as strong momentum.
    """
    if 55 <= rsi <= 65:
        return "BUY", 15, f"RSI strong bullish momentum ({rsi:.1f})"

    if 50 <= rsi < 55:
        return "BUY", 8, f"RSI mild bullish momentum ({rsi:.1f})"

    if 35 <= rsi <= 45:
        return "SELL", 15, f"RSI strong bearish momentum ({rsi:.1f})"

    if 45 < rsi < 50:
        return "SELL", 8, f"RSI mild bearish momentum ({rsi:.1f})"

    # Avoid awarding momentum points to extreme/overextended RSI.
    return None, 0, ""


def _candle_score(
    candle_open: float,
    candle_close: float,
    atr: float | None = None,
) -> tuple[str | None, int, str]:
    """
    Score candle confirmation according to candle strength.

    A tiny green/red candle should not receive the same score
    as a meaningful confirmation candle.
    """
    if candle_open <= 0 or candle_close <= 0:
        return None, 0, ""

    body = abs(candle_close - candle_open)

    if atr is not None and atr > 0:
        body_ratio = body / atr

        if body_ratio >= 0.50:
            points = 20
        elif body_ratio >= 0.20:
            points = 12
        else:
            points = 6
    else:
        points = 12

    if candle_close > candle_open:
        return "BUY", points, "15M candle confirms bullish price action"

    if candle_close < candle_open:
        return "SELL", points, "15M candle confirms bearish price action"

    return None, 0, ""


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
    atr: float | None = None,
) -> Tuple[str | None, int, List[str], List[str]]:
    """
    Score BUY and SELL conditions.

    Maximum possible score:
        25  = 15M EMA alignment
        20  = 1H trend alignment
        15  = RSI momentum
        20  = MACD direction
        10  = fresh MACD crossover
        20  = candle confirmation

        TOTAL = 110

    Important:
    High scores now require genuine confluence.
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
        buy_reasons.append(
            "15M EMA bullish alignment (EMA9 > EMA21)"
        )

    elif ema9 < ema21:
        sell_score += 25
        sell_reasons.append(
            "15M EMA bearish alignment (EMA9 < EMA21)"
        )

    # --------------------------------------------------------
    # 2. HIGHER TIMEFRAME TREND — 20 POINTS
    # --------------------------------------------------------

    if higher_ema9 > higher_ema21:
        buy_score += 20
        buy_reasons.append(
            "1H higher-timeframe trend is bullish"
        )

    elif higher_ema9 < higher_ema21:
        sell_score += 20
        sell_reasons.append(
            "1H higher-timeframe trend is bearish"
        )

    # --------------------------------------------------------
    # 3. RSI MOMENTUM — 15 POINTS
    # --------------------------------------------------------

    rsi_direction, rsi_points, rsi_reason = _rsi_score(rsi)

    if rsi_direction == "BUY":
        buy_score += rsi_points
        buy_reasons.append(rsi_reason)

    elif rsi_direction == "SELL":
        sell_score += rsi_points
        sell_reasons.append(rsi_reason)

    # --------------------------------------------------------
    # 4. MACD DIRECTION — 20 POINTS
    # --------------------------------------------------------

    if macd > macd_signal:
        buy_score += 20
        buy_reasons.append(
            "MACD confirms bullish momentum"
        )

    elif macd < macd_signal:
        sell_score += 20
        sell_reasons.append(
            "MACD confirms bearish momentum"
        )

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
        buy_reasons.append(
            "Fresh bullish MACD crossover"
        )

    elif bearish_cross:
        sell_score += 10
        sell_reasons.append(
            "Fresh bearish MACD crossover"
        )

    # --------------------------------------------------------
    # 6. CANDLE CONFIRMATION — 20 POINTS
    # --------------------------------------------------------

    candle_direction, candle_points, candle_reason = _candle_score(
        candle_open,
        candle_close,
        atr,
    )

    if candle_direction == "BUY":
        buy_score += candle_points
        buy_reasons.append(candle_reason)

    elif candle_direction == "SELL":
        sell_score += candle_points
        sell_reasons.append(candle_reason)

    # --------------------------------------------------------
    # FINAL SCORES
    # --------------------------------------------------------

    buy_score = clamp_score(buy_score)
    sell_score = clamp_score(sell_score)

    # --------------------------------------------------------
    # HIGH-SCORE QUALITY FILTER
    # --------------------------------------------------------
    #
    # A score alone should not create a STRONG signal.
    #
    # 90+ requires:
    #   - 15M EMA alignment
    #   - 1H trend agreement
    #
    # 100+ additionally requires:
    #   - RSI confirmation
    #   - MACD confirmation
    #
    # 105+ additionally requires:
    #   - fresh MACD crossover
    #   - meaningful candle confirmation
    # --------------------------------------------------------

    def quality_filter(
        direction: str,
        score: int,
        reasons: List[str],
    ) -> tuple[int, List[str]]:
        reason_text = " ".join(reasons)

        has_15m_ema = (
            "15M EMA bullish alignment" in reason_text
            if direction == "BUY"
            else "15M EMA bearish alignment" in reason_text
        )

        has_1h_trend = (
            "1H higher-timeframe trend is bullish" in reason_text
            if direction == "BUY"
            else "1H higher-timeframe trend is bearish" in reason_text
        )

        has_rsi = "RSI " in reason_text
        has_macd = "MACD confirms" in reason_text
        has_cross = "Fresh " in reason_text and "MACD crossover" in reason_text
        has_candle = "15M candle confirms" in reason_text

        # 90+ must have both timeframe trends aligned.
        if score >= STRONG_MIN:
            if not (has_15m_ema and has_1h_trend):
                score = min(score, STRONG_MIN - 1)

        # 100+ must also have RSI and MACD confirmation.
        if score >= VERY_STRONG_MIN:
            if not (has_rsi and has_macd):
                score = min(score, STRONG_MIN)

        # 105+ must have fresh crossover and candle confirmation.
        if score >= STRONGER_MIN:
            if not (has_cross and has_candle):
                score = min(score, VERY_STRONG_MIN - 1)

        return clamp_score(score), reasons

    buy_score, buy_reasons = quality_filter(
        "BUY",
        buy_score,
        buy_reasons,
    )

    sell_score, sell_reasons = quality_filter(
        "SELL",
        sell_score,
        sell_reasons,
    )

    # --------------------------------------------------------
    # FINAL DIRECTION
    # --------------------------------------------------------

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
    atr: float | None = None,
    minimum_score: int = WEAK_MIN,
) -> Dict[str, Any]:
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
        atr=atr,
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


def is_vip_score(
    score: int,
    minimum_score: int = STRONG_MIN,
) -> bool:
    return int(score) >= int(minimum_score)


def is_elite_score(score: int) -> bool:
    return int(score) >= STRONGER_MIN


def score_label(score: int) -> str:
    strength = get_strength(score)

    if strength:
        return strength

    return "⚪ NO QUALIFYING SETUP"
