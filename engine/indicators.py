from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate technical indicators used by the Apex signal engine.

    Indicators:
    - EMA 9
    - EMA 21
    - RSI 14
    - MACD
    - MACD Signal
    - ATR 14
    """

    if df is None or df.empty:
        raise ValueError("Cannot calculate indicators from empty market data.")

    required_columns = {"open", "high", "low", "close"}

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required OHLC columns: {', '.join(sorted(missing))}"
        )

    result = df.copy()

    # --------------------------------------------------------
    # Ensure numeric OHLC data
    # --------------------------------------------------------

    for column in ["open", "high", "low", "close"]:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    result = result.dropna(
        subset=["open", "high", "low", "close"]
    ).reset_index(drop=True)

    if len(result) < 50:
        raise ValueError(
            f"Not enough candles for indicator calculation: {len(result)}"
        )

    # --------------------------------------------------------
    # EMA 9 / EMA 21
    # --------------------------------------------------------

    result["ema9"] = (
        result["close"]
        .ewm(span=9, adjust=False, min_periods=9)
        .mean()
    )

    result["ema21"] = (
        result["close"]
        .ewm(span=21, adjust=False, min_periods=21)
        .mean()
    )

    # --------------------------------------------------------
    # RSI 14
    # --------------------------------------------------------

    delta = result["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(
        window=14,
        min_periods=14,
    ).mean()

    avg_loss = loss.rolling(
        window=14,
        min_periods=14,
    ).mean()

    # Avoid division-by-zero.
    rs = avg_gain / avg_loss.replace(0, np.nan)

    result["rsi"] = 100 - (
        100 / (1 + rs)
    )

    # Handle a market with consecutive gains.
    result.loc[
        (avg_loss == 0) & (avg_gain > 0),
        "rsi",
    ] = 100.0

    # Handle a market with consecutive losses.
    result.loc[
        (avg_gain == 0) & (avg_loss > 0),
        "rsi",
    ] = 0.0

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    ema12 = (
        result["close"]
        .ewm(span=12, adjust=False, min_periods=12)
        .mean()
    )

    ema26 = (
        result["close"]
        .ewm(span=26, adjust=False, min_periods=26)
        .mean()
    )

    result["macd"] = ema12 - ema26

    result["macd_signal"] = (
        result["macd"]
        .ewm(span=9, adjust=False, min_periods=9)
        .mean()
    )

    result["macd_histogram"] = (
        result["macd"] - result["macd_signal"]
    )

    # --------------------------------------------------------
    # ATR 14
    # --------------------------------------------------------

    previous_close = result["close"].shift(1)

    high_low = (
        result["high"] - result["low"]
    ).abs()

    high_previous_close = (
        result["high"] - previous_close
    ).abs()

    low_previous_close = (
        result["low"] - previous_close
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_previous_close,
            low_previous_close,
        ],
        axis=1,
    ).max(axis=1)

    result["true_range"] = true_range

    result["atr"] = (
        true_range
        .rolling(window=14, min_periods=14)
        .mean()
    )

    return result


def get_latest_indicator_row(
    df: pd.DataFrame,
) -> pd.Series:
    """
    Return the most recent completed indicator row.

    The latest row is returned only if the core indicators
    contain valid values.
    """

    if df is None or df.empty:
        raise ValueError("Indicator dataframe is empty.")

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

        if value is None or pd.isna(value):
            raise ValueError(
                f"Invalid indicator value: {column}"
            )

    return row
