from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# APEX TECHNICAL INDICATOR ENGINE
# ============================================================
#
# Core indicators:
#   - EMA 9 / EMA 21
#   - RSI 14 (Wilder/RMA style)
#   - MACD 12/26/9
#   - ATR 14 (Wilder/RMA style)
#
# Additional market-data features:
#   - MACD histogram
#   - EMA spread
#   - EMA slopes
#   - candle body / range
#   - body-to-range ratio
#   - upper/lower wick
#   - bullish/bearish candle flags
#   - rolling highs/lows
#
# No future candles are used.
# ============================================================


RSI_PERIOD = 14
ATR_PERIOD = 14

EMA_FAST = 9
EMA_SLOW = 21

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

STRUCTURE_LOOKBACK = 20


def _wilder_rma(
    series: pd.Series,
    period: int,
) -> pd.Series:
    """
    Wilder's RMA / SMMA.

    Equivalent to an EMA with alpha=1/period,
    which is commonly used for RSI and ATR.
    """

    return series.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()


def _calculate_rsi(
    close: pd.Series,
    period: int = RSI_PERIOD,
) -> pd.Series:
    """Calculate RSI using Wilder smoothing."""

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = _wilder_rma(gain, period)
    avg_loss = _wilder_rma(loss, period)

    rsi = pd.Series(
        np.nan,
        index=close.index,
        dtype=float,
    )

    # Normal RSI calculation.
    valid_loss = avg_loss > 0

    rs = avg_gain[valid_loss] / avg_loss[valid_loss]

    rsi.loc[valid_loss] = (
        100 - (100 / (1 + rs))
    )

    # Consecutive gains.
    rsi.loc[
        (avg_loss == 0) & (avg_gain > 0)
    ] = 100.0

    # Consecutive losses.
    rsi.loc[
        (avg_gain == 0) & (avg_loss > 0)
    ] = 0.0

    # Flat market.
    rsi.loc[
        (avg_gain == 0) & (avg_loss == 0)
    ] = 50.0

    return rsi


def _calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = ATR_PERIOD,
) -> tuple[pd.Series, pd.Series]:
    """Calculate True Range and Wilder ATR."""

    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            (high - low).abs(),
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = _wilder_rma(
        true_range,
        period,
    )

    return true_range, atr


def calculate_indicators(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate all technical and candle indicators used
    by the Apex signal engine.

    The input dataframe must contain:

        open
        high
        low
        close

    Volume is optional.
    """

    if df is None or df.empty:
        raise ValueError(
            "Cannot calculate indicators from empty market data."
        )

    required_columns = {
        "open",
        "high",
        "low",
        "close",
    }

    missing = (
        required_columns - set(df.columns)
    )

    if missing:
        raise ValueError(
            "Missing required OHLC columns: "
            + ", ".join(sorted(missing))
        )

    result = df.copy()

    # --------------------------------------------------------
    # Normalize OHLC
    # --------------------------------------------------------

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
    ).copy()

    result = result.reset_index(
        drop=True
    )

    if len(result) < 50:
        raise ValueError(
            "Not enough candles for indicator calculation: "
            f"{len(result)}"
        )

    # --------------------------------------------------------
    # Candle sanity
    # --------------------------------------------------------

    result["candle_range"] = (
        result["high"]
        - result["low"]
    ).abs()

    result["candle_body"] = (
        result["close"]
        - result["open"]
    ).abs()

    result["body_to_range"] = np.where(
        result["candle_range"] > 0,
        result["candle_body"]
        / result["candle_range"],
        0.0,
    )

    result["upper_wick"] = (
        result["high"]
        - result[["open", "close"]].max(axis=1)
    ).clip(lower=0)

    result["lower_wick"] = (
        result[["open", "close"]].min(axis=1)
        - result["low"]
    ).clip(lower=0)

    result["bullish_candle"] = (
        result["close"]
        > result["open"]
    )

    result["bearish_candle"] = (
        result["close"]
        < result["open"]
    )

    # --------------------------------------------------------
    # EMA 9 / EMA 21
    # --------------------------------------------------------

    result["ema9"] = (
        result["close"]
        .ewm(
            span=EMA_FAST,
            adjust=False,
            min_periods=EMA_FAST,
        )
        .mean()
    )

    result["ema21"] = (
        result["close"]
        .ewm(
            span=EMA_SLOW,
            adjust=False,
            min_periods=EMA_SLOW,
        )
        .mean()
    )

    # EMA spread.
    result["ema_spread"] = (
        result["ema9"]
        - result["ema21"]
    )

    # EMA spread relative to price.
    result["ema_spread_pct"] = np.where(
        result["close"] != 0,
        (
            result["ema_spread"]
            / result["close"]
        ) * 100,
        0.0,
    )

    # EMA slopes.
    result["ema9_slope"] = (
        result["ema9"]
        - result["ema9"].shift(1)
    )

    result["ema21_slope"] = (
        result["ema21"]
        - result["ema21"].shift(1)
    )

    # --------------------------------------------------------
    # RSI 14
    # --------------------------------------------------------

    result["rsi"] = _calculate_rsi(
        result["close"],
        RSI_PERIOD,
    )

    # RSI slope.
    result["rsi_slope"] = (
        result["rsi"]
        - result["rsi"].shift(1)
    )

    # --------------------------------------------------------
    # MACD 12 / 26 / 9
    # --------------------------------------------------------

    ema12 = (
        result["close"]
        .ewm(
            span=MACD_FAST,
            adjust=False,
            min_periods=MACD_FAST,
        )
        .mean()
    )

    ema26 = (
        result["close"]
        .ewm(
            span=MACD_SLOW,
            adjust=False,
            min_periods=MACD_SLOW,
        )
        .mean()
    )

    result["macd"] = (
        ema12 - ema26
    )

    result["macd_signal"] = (
        result["macd"]
        .ewm(
            span=MACD_SIGNAL,
            adjust=False,
            min_periods=MACD_SIGNAL,
        )
        .mean()
    )

    result["macd_histogram"] = (
        result["macd"]
        - result["macd_signal"]
    )

    result["macd_histogram_slope"] = (
        result["macd_histogram"]
        - result["macd_histogram"].shift(1)
    )

    # --------------------------------------------------------
    # ATR 14
    # --------------------------------------------------------

    (
        result["true_range"],
        result["atr"],
    ) = _calculate_atr(
        result["high"],
        result["low"],
        result["close"],
        ATR_PERIOD,
    )

    # Candle size relative to volatility.
    result["body_atr_ratio"] = np.where(
        result["atr"] > 0,
        result["candle_body"]
        / result["atr"],
        0.0,
    )

    result["range_atr_ratio"] = np.where(
        result["atr"] > 0,
        result["candle_range"]
        / result["atr"],
        0.0,
    )

    # --------------------------------------------------------
    # Rolling market structure
    #
    # Shift(1) is intentional.
    # It prevents the current candle from being used
    # to define its own previous structure level.
    # --------------------------------------------------------

    result["previous_swing_high"] = (
        result["high"]
        .rolling(
            STRUCTURE_LOOKBACK,
            min_periods=STRUCTURE_LOOKBACK,
        )
        .max()
        .shift(1)
    )

    result["previous_swing_low"] = (
        result["low"]
        .rolling(
            STRUCTURE_LOOKBACK,
            min_periods=STRUCTURE_LOOKBACK,
        )
        .min()
        .shift(1)
    )

    # --------------------------------------------------------
    # Break-of-structure helpers
    # --------------------------------------------------------

    result["bullish_structure_break"] = (
        result["close"]
        > result["previous_swing_high"]
    )

    result["bearish_structure_break"] = (
        result["close"]
        < result["previous_swing_low"]
    )

    # --------------------------------------------------------
    # Distance from structure
    # --------------------------------------------------------

    result["distance_from_swing_high"] = (
        result["previous_swing_high"]
        - result["close"]
    )

    result["distance_from_swing_low"] = (
        result["close"]
        - result["previous_swing_low"]
    )

    # --------------------------------------------------------
    # Final numeric cleanup
    #
    # Do not blindly fill indicator NaNs with zero.
    # Early rows must remain invalid until the indicator
    # has enough history.
    # --------------------------------------------------------

    numeric_columns = result.select_dtypes(
        include=[np.number]
    ).columns

    result[numeric_columns] = (
        result[numeric_columns]
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
    )

    return result


def get_latest_indicator_row(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Return the most recent row with valid core indicators.
    """

    if df is None or df.empty:
        raise ValueError(
            "Indicator dataframe is empty."
        )

    row = df.iloc[-1]

    required = [
        "ema9",
        "ema21",
        "rsi",
        "macd",
        "macd_signal",
        "atr",
    ]

    for column in required:
        value = row.get(column)

        if (
            value is None
            or pd.isna(value)
        ):
            raise ValueError(
                f"Invalid indicator value: {column}"
            )

    return row


__all__ = [
    "calculate_indicators",
    "get_latest_indicator_row",
]
