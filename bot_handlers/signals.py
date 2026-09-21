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
    price = (
        signal.get("entry_price")
        or signal.get("price")
        or signal.get("current_price")
        or ""
    )
    return f"{symbol}:{direction}:{price}"

def build_signal_message(signal: dict[str, Any], vip: bool = False) -> str:
    emoji = "🟢" if signal.get("direction") == "BUY" else "🔴"
    crypto_tag = (
        "🪙 Crypto Setup"
        if signal.get("is_crypto")
        else "🏛️ Forex & Commodities"
    )
    reasons_list = signal.get("reasons") or []
    reasons = "\n".join(f"• {r}" for r in reasons_list) if reasons_list else "• Confluence confirmed"
    chart_url = signal.get("chart_url", "https://www.tradingview.com")

    entry = price_format(
        signal.get("entry_price")
        or signal.get("price")
        or signal.get("current_price")
        or 0
    )
    stop_loss = price_format(signal.get("stop_loss") or 0)

    tp1_str = price_format(signal.get("tp1") or signal.get("take_profit") or 0)
    tp2_str = price_format(signal.get("tp2") or 0)
    tp3_str = price_format(signal.get("tp3") or 0)

    strength = signal.get("strength") or ""
    direction = signal.get("direction") or ""
    symbol = signal.get("symbol") or ""
    score = signal.get("score", 0)
    max_score = signal.get("max_score", MAX_SIGNAL_SCORE)
    timeframe = signal.get("timeframe") or signal.get("interval") or "15M + 1H"
    signal_code = signal.get("signal_code", "")

    if vip:
        return f"""
👑 *APEX VIP SIGNAL*
══════════════════
{emoji} *{strength} {direction}* {emoji}

{crypto_tag}
💎 Pair: *{symbol}*

💰 Entry: `{entry}`
🛑 Stop Loss: `{stop_loss}`

🎯 TP1 (50% Close): `{tp1_str}`
🎯 TP2 (30% Close): `{tp2_str}`
🎯 TP3 (Runner): `{tp3_str}`

📊 Score: *{score}/{max_score}*
⏱ Timeframes: *{timeframe}*

🔎 *Confluence:*
{reasons}

📐 *Risk guide:*
• Risk 1% per trade
• Move SL to breakeven after TP1
• Leave runner for TP3

🆔 Signal: `{signal_code}`
📈 [Open TradingView Chart]({chart_url})

⚠️ VIP only. Not financial advice. Always use Stop Loss.
""".strip()

    # Free format (shorter)
    return f"""
{emoji} *{strength} {direction}* {emoji}
📡 *APEX LIVE SIGNAL*
══════════════════
{crypto_tag}

💎 Pair: *{symbol}*
💰 Entry: `{entry}`
🛑 Stop Loss: `{stop_loss}`
🎯 TP1: `{tp1_str}`
🎯 TP2: `{tp2_str}`
🔒 *TP3 Runner:* [Unlock in VIP](https://t.me/ApexMarketSignalsBot)
📊 Score: *{score}/{max_score}*

⏱ Timeframes: *{timeframe}*
📈 [Open TradingView Chart]({chart_url})
🆔 Signal: `{signal_code}`

⚠️ Always place Stop Loss immediately.
""".strip()
