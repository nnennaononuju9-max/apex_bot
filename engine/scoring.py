from __future__ import annotations

from typing import Any, Dict, List, Tuple


# ============================================================
# APEX SIGNAL SCORING ENGINE
# ============================================================
# 0 - 110 scoring system
#
# 25  = 15M EMA alignment
# 20  = 1H trend alignment
# 15  = RSI confirmation
# 20  = MACD confirmation
# 10  = fresh MACD crossover
# 20  = candle confirmation
#
# Additional price-action confirmation is returned separately
# and is used by signal_generator.py as a hard quality gate.
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


def _safe_float(value: Any) -> float | None:
    try:
        value = float(value)

        if value != value:
            return None

        return value

    except (TypeError, ValueError):
        return None


# ============================================================
# RSI
# ============================================================

def _rsi_score(
    rsi: float,
) -> tuple[str | None, int, str]:

    rsi = float(rsi)

    if 55 <= rsi <= 65:
        return (
            "BUY",
            15,
            f"RSI strong bullish momentum ({rsi:.1f})",
        )

    if 50 <= rsi < 55:
        return (
            "BUY",
            8,
            f"RSI mild bullish momentum ({rsi:.1f})",
        )

    if 35 <= rsi <= 45:
        return (
            "SELL",
            15,
            f"RSI strong bearish momentum ({rsi:.1f})",
        )

    if 45 < rsi < 50:
        return (
            "SELL",
            8,
            f"RSI mild bearish momentum ({rsi:.1f})",
        )

    return None, 0, ""


# ============================================================
# CANDLE
# ============================================================

def _candle_score(
    candle_open: float,
    candle_close: float,
    atr: float | None = None,
) -> tuple[str | None, int, str]:

    candle_open = _safe_float(candle_open)
    candle_close = _safe_float(candle_close)
    atr = _safe_float(atr)

    if (
        candle_open is None
        or candle_close is None
        or candle_open <= 0
        or candle_close <= 0
    ):
        return None, 0, ""

    body = abs(candle_close - candle_open)

    if atr and atr > 0:
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
        return (
            "BUY",
            points,
            "15M candle confirms bullish price action",
        )

    if candle_close < candle_open:
        return (
            "SELL",
            points,
            "15M candle confirms bearish price action",
        )

    return None, 0, ""


# ============================================================
# PRICE ACTION
# ============================================================

def _build_price_action(
    *,
    direction: str,
    candle_open: float,
    candle_close: float,
    atr: float,
    ema9: float,
    ema21: float,
    higher_ema9: float,
    higher_ema21: float,
) -> Dict[str, Any]:
    """
    Conservative structural price-action proxy.

    This intentionally does not fabricate a sweep/reclaim/
    displacement/structure-break sequence when the scoring
    engine has no dedicated market-structure detector.

    It returns safe defaults so the signal generator can
    explicitly decide whether a setup qualifies.
    """

    entry = float(candle_close)
    atr = float(atr)

    body = abs(float(candle_close) - float(candle_open))
    displacement_body_atr = (
        body / atr if atr > 0 else 0.0
    )

    if direction == "BUY":
        trend_aligned = (
            ema9 > ema21
            and higher_ema9 > higher_ema21
        )

        invalidation_price = entry - atr

        # Conservative structural proxy.
        structure_level = ema21

    else:
        trend_aligned = (
            ema9 < ema21
            and higher_ema9 < higher_ema21
        )

        invalidation_price = entry + atr
        structure_level = ema21

    return {
        "sweep": False,
        "reclaim": False,
        "displacement": displacement_body_atr >= 0.50,
        "structure_break": bool(trend_aligned),
        "retest": False,

        "entry_zone_low": (
            entry - atr * 0.25
            if direction == "BUY"
            else entry - atr * 0.25
        ),

        "entry_zone_high": (
            entry + atr * 0.25
            if direction == "BUY"
            else entry + atr * 0.25
        ),

        "invalidation_price": invalidation_price,
        "liquidity_level": None,
        "structure_level": structure_level,

        "displacement_body_atr": displacement_body_atr,
    }


# ============================================================
# DIRECTION SCORING
# ============================================================

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
) -> Tuple[
    str | None,
    int,
    List[str],
    List[str],
]:

    buy_score = 0
    sell_score = 0

    buy_reasons: List[str] = []
    sell_reasons: List[str] = []

    # --------------------------------------------------------
    # 1. 15M EMA
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
    # 2. 1H TREND
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
    # 3. RSI
    # --------------------------------------------------------

    rsi_direction, rsi_points, rsi_reason = _rsi_score(rsi)

    if rsi_direction == "BUY":
        buy_score += rsi_points
        buy_reasons.append(rsi_reason)

    elif rsi_direction == "SELL":
        sell_score += rsi_points
        sell_reasons.append(rsi_reason)

    # --------------------------------------------------------
    # 4. MACD
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
    # 5. MACD CROSSOVER
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
    # 6. CANDLE
    # --------------------------------------------------------

    (
        candle_direction,
        candle_points,
        candle_reason,
    ) = _candle_score(
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

    buy_score = clamp_score(buy_score)
    sell_score = clamp_score(sell_score)

    # --------------------------------------------------------
    # QUALITY FILTER
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
        has_cross = (
            "Fresh " in reason_text
            and "MACD crossover" in reason_text
        )
        has_candle = "15M candle confirms" in reason_text

        if score >= STRONG_MIN:
            if not (has_15m_ema and has_1h_trend):
                score = STRONG_MIN - 1

        if score >= VERY_STRONG_MIN:
            if not (has_rsi and has_macd):
                score = STRONG_MIN

        if score >= STRONGER_MIN:
            if not (has_cross and has_candle):
                score = VERY_STRONG_MIN - 1

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

    if buy_score > sell_score:
        return (
            "BUY",
            buy_score,
            buy_reasons,
            sell_reasons,
        )

    if sell_score > buy_score:
        return (
            "SELL",
            sell_score,
            sell_reasons,
            buy_reasons,
        )

    return None, 0, [], []


# ============================================================
# PUBLIC SCORING FUNCTION
# ============================================================

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
    df_15m: Any = None,
    df_1h: Any = None,
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

    # --------------------------------------------------------
    # Indicator confirmation
    # --------------------------------------------------------

    indicator_confirmation = {
        "rsi_ok": False,
        "macd_ok": False,
        "ema_ok": False,
        "htf_ok": False,
    }

    if direction == "BUY":
        indicator_confirmation["rsi_ok"] = (
            50 <= float(rsi) <= 65
        )

        indicator_confirmation["macd_ok"] = (
            float(macd) > float(macd_signal)
        )

        indicator_confirmation["ema_ok"] = (
            float(ema9) > float(ema21)
        )

        indicator_confirmation["htf_ok"] = (
            float(higher_ema9)
            > float(higher_ema21)
        )

    elif direction == "SELL":
        indicator_confirmation["rsi_ok"] = (
            35 <= float(rsi) < 50
        )

        indicator_confirmation["macd_ok"] = (
            float(macd) < float(macd_signal)
        )

        indicator_confirmation["ema_ok"] = (
            float(ema9) < float(ema21)
        )

        indicator_confirmation["htf_ok"] = (
            float(higher_ema9)
            < float(higher_ema21)
        )

    # --------------------------------------------------------
    # Price-action data
    # --------------------------------------------------------

    price_action: Dict[str, Any] = {}

    if direction is not None and atr is not None:
        try:
            price_action = _build_price_action(
                direction=direction,
                candle_open=candle_open,
                candle_close=candle_close,
                atr=atr,
                ema9=ema9,
                ema21=ema21,
                higher_ema9=higher_ema9,
                higher_ema21=higher_ema21,
            )
        except Exception:
            price_action = {}

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
            "indicator_confirmation": indicator_confirmation,
            "price_action": price_action,
        }

    return {
        "valid": True,
        "direction": direction,
        "score": score,
        "max_score": MAX_SCORE,
        "strength": get_strength(score),
        "reasons": reasons,
        "opposite_reasons": opposite_reasons,
        "indicator_confirmation": indicator_confirmation,
        "price_action": price_action,
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


__all__ = [
    "WEAK_MIN",
    "MODERATE_MIN",
    "STRONG_MIN",
    "VERY_STRONG_MIN",
    "STRONGER_MIN",
    "MAX_SCORE",
    "get_strength",
    "clamp_score",
    "score_direction",
    "score_signal",
    "is_vip_score",
    "is_elite_score",
    "score_label",
]
