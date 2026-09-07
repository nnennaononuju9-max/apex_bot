"""Apex signal engine package."""

from .market_data import get_data, get_latest_price, MARKETS, CRYPTO_SYMBOL_MAP
from .indicators import calculate_indicators
from .scoring import score_signal, get_strength, MAX_SCORE
from .risk import build_risk_profile
from .signal_generator import (
    create_signal,
    generate_free_signal,
    generate_vip_signal,
    mark_signal_posted,
    market_can_receive_signal,
)
from .signal_manager import SignalManager

__all__ = [
    "get_data",
    "get_latest_price",
    "MARKETS",
    "CRYPTO_SYMBOL_MAP",
    "calculate_indicators",
    "score_signal",
    "get_strength",
    "MAX_SCORE",
    "build_risk_profile",
    "create_signal",
    "generate_free_signal",
    "generate_vip_signal",
    "mark_signal_posted",
    "market_can_receive_signal",
    "SignalManager",
]
