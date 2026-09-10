from __future__ import annotations

from typing import Optional

import pandas as pd
import requests

from config import (
    TWELVE_DATA_API_KEY,
    CANDLE_LIMIT,
)


# ============================================================
# MARKET SYMBOLS
# ============================================================

CRYPTO_SYMBOL_MAP = {
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
    "SOL/USD": "SOL-USD",
    "BNB/USD": "BNB-USD",
    "XRP/USD": "XRP-USD",
    "DOGE/USD": "DOGE-USD",
    "ADA/USD": "ADA-USD",
}

FOREX_AND_COMMODITIES = [
    "XAU/USD",
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
]

ALL_MARKETS = [
    *CRYPTO_SYMBOL_MAP.keys(),
    *FOREX_AND_COMMODITIES,
]

MARKETS = ALL_MARKETS


# ============================================================
# TIMEFRAME ROUTING
# ============================================================

# Coinbase uses seconds for candle granularity.
COINBASE_INTERVAL_MAP = {
    "15min": 900,
    "1h": 3600,
}


# ============================================================
# API ENDPOINTS
# ============================================================

COINBASE_CANDLES_URL = (
    "https://api.exchange.coinbase.com/products/{}/candles"
)

TWELVE_DATA_URL = (
    "https://api.twelvedata.com/time_series"
)


# ============================================================
# COINBASE CRYPTO DATA
# ============================================================

def get_data_coinbase(
    symbol: str,
    interval: str,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candle data from Coinbase Exchange.

    Used for crypto markets:
        BTC/USD
        ETH/USD
        SOL/USD
        BNB/USD
        XRP/USD
        DOGE/USD
        ADA/USD
    """

    coinbase_symbol = CRYPTO_SYMBOL_MAP.get(symbol)

    if not coinbase_symbol:
        print(
            f"⚠️ No Coinbase symbol mapping for {symbol}"
        )
        return None

    granularity = COINBASE_INTERVAL_MAP.get(interval)

    if granularity is None:
        print(
            f"⚠️ Unsupported Coinbase interval: "
            f"{interval}"
        )
        return None

    # Coinbase permits a maximum of 300 candles.
    limit = min(int(CANDLE_LIMIT), 300)

    try:
        response = requests.get(
            COINBASE_CANDLES_URL.format(
                coinbase_symbol
            ),
            params={
                "granularity": granularity,
            },
            headers={
                "Accept": "application/json",
            },
            timeout=20,
        )

        response.raise_for_status()

        raw = response.json()

        if not isinstance(raw, list) or not raw:
            print(
                f"⚪ Coinbase returned no data: "
                f"{symbol} {interval}"
            )
            return None

        # Coinbase candle format:
        # [
        #   time,
        #   low,
        #   high,
        #   open,
        #   close,
        #   volume
        # ]
        columns = [
            "timestamp",
            "low",
            "high",
            "open",
            "close",
            "volume",
        ]

        df = pd.DataFrame(
            raw,
            columns=columns,
        )

        # ----------------------------------------------------
        # Convert timestamp
        # ----------------------------------------------------

        df["datetime"] = pd.to_datetime(
            df["timestamp"],
            unit="s",
            utc=True,
            errors="coerce",
        )

        # ----------------------------------------------------
        # Convert numeric columns
        # ----------------------------------------------------

        for column in [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        # ----------------------------------------------------
        # Keep required engine columns
        # ----------------------------------------------------

        df = df[
            [
                "datetime",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ]

        df = df.dropna(
            subset=[
                "datetime",
                "open",
                "high",
                "low",
                "close",
            ]
        )

        df = (
            df.sort_values("datetime")
            .drop_duplicates(
                subset=["datetime"],
                keep="last",
            )
            .reset_index(drop=True)
        )

        # Keep the newest requested candles.
        if len(df) > limit:
            df = df.tail(limit).reset_index(drop=True)

        if len(df) < 50:
            print(
                f"⚪ Not enough Coinbase candles: "
                f"{symbol} {interval} "
                f"({len(df)})"
            )
            return None

        return df

    except requests.RequestException as error:
        print(
            f"❌ Coinbase request error "
            f"{symbol} {interval}: {error}"
        )
        return None

    except ValueError as error:
        print(
            f"❌ Coinbase response parsing error "
            f"{symbol} {interval}: {error}"
        )
        return None

    except Exception as error:
        print(
            f"❌ Unexpected Coinbase error "
            f"{symbol} {interval}: {error}"
        )
        return None


# ============================================================
# TWELVE DATA
# ============================================================

def get_data_twelve_data(
    symbol: str,
    interval: str,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLC candle data from Twelve Data.

    Used for Forex and Gold.
    """

    if not TWELVE_DATA_API_KEY:
        print(
            "❌ TWELVE_DATA_API_KEY is missing."
        )
        return None

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": CANDLE_LIMIT,
        "apikey": TWELVE_DATA_API_KEY,
        "timezone": "UTC",
    }

    try:
        response = requests.get(
            TWELVE_DATA_URL,
            params=params,
            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("status") == "error":
            print(
                f"❌ Twelve Data error "
                f"{symbol} {interval}: "
                f"{data.get('message', 'Unknown error')}"
            )
            return None

        values = data.get("values")

        if not values:
            print(
                f"⚪ Twelve Data returned no candles: "
                f"{symbol} {interval}"
            )
            return None

        df = pd.DataFrame(values)

        required_columns = [
            "datetime",
            "open",
            "high",
            "low",
            "close",
        ]

        if not all(
            column in df.columns
            for column in required_columns
        ):
            print(
                f"❌ Twelve Data response missing "
                f"required columns: {symbol}"
            )
            return None

        # ----------------------------------------------------
        # Convert datetime
        # ----------------------------------------------------

        df["datetime"] = pd.to_datetime(
            df["datetime"],
            utc=True,
            errors="coerce",
        )

        # ----------------------------------------------------
        # Convert OHLC values
        # ----------------------------------------------------

        for column in [
            "open",
            "high",
            "low",
            "close",
        ]:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        # ----------------------------------------------------
        # Keep clean market data
        # ----------------------------------------------------

        keep_columns = [
            "datetime",
            "open",
            "high",
            "low",
            "close",
        ]

        if "volume" in df.columns:
            keep_columns.append("volume")

        df = df[keep_columns]

        df = df.dropna(
            subset=[
                "datetime",
                "open",
                "high",
                "low",
                "close",
            ]
        )

        df = (
            df.sort_values("datetime")
            .drop_duplicates(
                subset=["datetime"],
                keep="last",
            )
            .reset_index(drop=True)
        )

        if len(df) < 50:
            print(
                f"⚪ Not enough Twelve Data candles: "
                f"{symbol} {interval} "
                f"({len(df)})"
            )
            return None

        return df

    except requests.RequestException as error:
        print(
            f"❌ Twelve Data request error "
            f"{symbol} {interval}: {error}"
        )
        return None

    except ValueError as error:
        print(
            f"❌ Twelve Data response parsing error "
            f"{symbol} {interval}: {error}"
        )
        return None

    except Exception as error:
        print(
            f"❌ Unexpected Twelve Data error "
            f"{symbol} {interval}: {error}"
        )
        return None


# ============================================================
# UNIVERSAL MARKET DATA ROUTER
# ============================================================

def get_data(
    symbol: str,
    interval: str,
) -> Optional[pd.DataFrame]:
    """
    Universal market-data router.

    Crypto -> Coinbase
    Forex/Gold -> Twelve Data
    """

    symbol = symbol.upper().strip()

    if symbol in CRYPTO_SYMBOL_MAP:
        return get_data_coinbase(
            symbol,
            interval,
        )

    if symbol in FOREX_AND_COMMODITIES:
        return get_data_twelve_data(
            symbol,
            interval,
        )

    print(
        f"⚠️ Unsupported market symbol: {symbol}"
    )

    return None


# ============================================================
# LATEST PRICE
# ============================================================

def get_latest_price(
    symbol: str,
    interval: str = "15min",
) -> Optional[float]:
    """
    Return the latest available closing price.
    """

    df = get_data(
        symbol,
        interval,
    )

    if df is None or df.empty:
        return None

    try:
        price = float(
            df.iloc[-1]["close"]
        )

        if price <= 0:
            return None

        return price

    except (
        TypeError,
        ValueError,
        KeyError,
    ):
        return None


# ============================================================
# MARKET VALIDATION
# ============================================================

def is_supported_market(
    symbol: str,
) -> bool:
    return symbol.upper().strip() in ALL_MARKETS


def is_crypto_market(
    symbol: str,
) -> bool:
    return symbol.upper().strip() in CRYPTO_SYMBOL_MAP


def get_market_type(
    symbol: str,
) -> str:
    symbol = symbol.upper().strip()

    if symbol in CRYPTO_SYMBOL_MAP:
        return "crypto"

    if symbol in FOREX_AND_COMMODITIES:
        return "forex_commodity"

    return "unknown"
