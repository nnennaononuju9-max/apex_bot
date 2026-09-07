"""
Signal message formatting and small helpers used by the Telegram layer.
"""
from __future__ import annotations

from typing import Any, Optional

from utils.formatting import price_format


MAX_SIGNAL_SCORE = 110


def get_score(signal: dict[str, Any]) -> int:
    try:
        return max(0, min(MAX_SIGNAL_SCORE, int(signal.get("score", 0))))
    except (TypeError, ValueError):
        return 0


def get_signal_key(signal: dict[str, Any]) -> str:
    signal_code = signal.get("signal_code")
    if signal_code:
        return str(signal_code)
    symbol = signal.get("symbol") or "unknown"
    direction = signal.get("direction") or ""
    price = signal.get("price") or ""
    return f"{symbol}:{direction}:{price}"


def build_signal_message(signal: dict[str, Any], vip: bool = False) -> str:
    emoji = "🟢" if signal.get("direction") == "BUY" else "🔴"
    crypto_tag = (
        "🪙 Crypto Setup (Binance)"
        if signal.get("is_crypto")
        else "🏛️ Forex & Commodities"
    )
    reasons = "\n".join(f"• {r}" for r in signal.get("reasons", []))
    chart_url = signal.get("chart_url", "https://www.tradingview.com")

    header = "👑💎 APEX VIP SIGNAL" if vip else "📡 APEX LIVE SIGNAL"

    tp1_str = price_format(signal.get("tp1", signal.get("take_profit", 0)))
    tp2_str = price_format(signal.get("tp2", signal.get("take_profit", 0)))
    tp3_str = price_format(signal.get("tp3", signal.get("take_profit", 0)))

    if vip:
        tp_block = (
            f"🎯 TP1 (50% Close): `{tp1_str}`\n"
            f"🎯 TP2 (30% Close): `{tp2_str}`\n"
            f"🎯 TP3 (Runner): `{tp3_str}`"
        )
    else:
        tp_block = (
            f"🎯 TP1: `{tp1_str}`\n"
            f"🎯 TP2: `{tp2_str}`\n"
            f"🔒 *TP3 Runner & Live Exit Alerts:* "
            f"[Unlock in VIP](https://t.me/ApexTradeSignalsBot)"
        )

    risk_guide = (
        "⚡ Crypto: Spot or 3x-5x Futures Max"
        if signal.get("is_crypto")
        else "⚡ Forex: Risk 1-2% account balance maximum"
    )

    strength = signal.get("strength") or ""
    direction = signal.get("direction") or ""
    symbol = signal.get("symbol") or ""
    price = price_format(signal.get("price", 0))
    stop_loss = price_format(signal.get("stop_loss", 0))
    score = signal.get("score", 0)
    max_score = signal.get("max_score", MAX_SIGNAL_SCORE)
    timeframe = signal.get("timeframe", "15M + 1H")
    signal_code = signal.get("signal_code", "")

    return f"""
{emoji} *{strength} {direction}* {emoji}
{header}
══════════════════
{crypto_tag}

💎 Pair: *{symbol}*
💰 Entry: `{price}`
🛑 Stop Loss: `{stop_loss}`
{tp_block}
📊 Signal Score: *{score}/{max_score}*

🔎 Technical Confluence:
{reasons}

⏱ Timeframes: *{timeframe}*
📈 [Open TradingView Chart]({chart_url})
🆔 Signal: `{signal_code}`

⚠️ {risk_guide}. Always place Stop Loss immediately.
""".strip()
