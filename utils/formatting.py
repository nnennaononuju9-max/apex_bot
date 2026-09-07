"""Formatting helpers for prices, badges, etc."""
from __future__ import annotations

from typing import Optional


def price_format(price: float) -> str:
    """Format price based on market size (BTC vs EUR vs DOGE)."""
    price = float(price)
    if price >= 1000:
        return f"{price:,.2f}"
    if price >= 10:
        return f"{price:.3f}"
    if price >= 1:
        return f"{price:.4f}"
    return f"{price:.5f}"


def premium_badge(plan: Optional[str]) -> str:
    if plan == "trial":
        return "✨ VIP TRIAL"
    if plan == "weekly":
        return "👑 VIP"
    return "💎 PREMIUM VIP"
  
