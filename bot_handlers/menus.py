"""
Keyboards and static text builders for Apex Bot menus.
"""
from __future__ import annotations

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config
from database import is_vip
from utils.formatting import premium_badge


def channel_gatekeeper_keyboard() -> InlineKeyboardMarkup:
    channel = str(getattr(config, "FREE_CHANNEL_ID", "@ApexFreeSignals") or "@ApexFreeSignals")
    channel_url = (
        channel
        if channel.startswith("https://t.me/")
        else f"https://t.me/{channel.lstrip('@')}"
    )
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 1. Join Official Telegram Channel", url=channel_url)],
        [InlineKeyboardButton("✅ 2. I Have Joined (Verify Access)", callback_data="verify_channel_join")],
    ])


def gatekeeper_text() -> str:
    return """
🔒 *ACCESS RESTRICTED: OFFICIAL CHANNEL MEMBERSHIP REQUIRED*
━━━━━━━━━━━━━━━━━━━━━━━━━━
To use **Apex Trade Signals Bot** and receive algorithmic Forex, Gold, and Binance Crypto setups, you **must first be an active member of our official community channel**.

1️⃣ Tap **1. Join Official Telegram Channel** below to join.
2️⃣ Tap **2. I Have Joined (Verify Access)** to unlock all bot tools.

_Verification is instant._
""".strip()


def main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    vip_active = is_vip(user_id)
    vip_label = "💎 My VIP Status" if vip_active else "👑 Upgrade to VIP"

    rows = [
        [
            InlineKeyboardButton("📡 Live Signals", callback_data="menu_signal"),
            InlineKeyboardButton(vip_label, callback_data="menu_vip"),
        ],
        [
            InlineKeyboardButton("🧮 Lot Calculator", callback_data="menu_calc"),
            InlineKeyboardButton("⏰ Market Sessions", callback_data="menu_sessions"),
        ],
        [
            InlineKeyboardButton("📰 News Filter", callback_data="menu_news"),
            InlineKeyboardButton("🗳️ Market Sentiment", callback_data="menu_sentiment"),
        ],
        [
            InlineKeyboardButton("🏆 Monthly P&L", callback_data="menu_report"),
            InlineKeyboardButton("📊 Paper Trades", callback_data="menu_trades"),
        ],
        [
            InlineKeyboardButton("🏦 Recommended Brokers", callback_data="menu_brokers"),
            InlineKeyboardButton("🎁 Refer & Earn", callback_data="menu_refer"),
        ],
        [
            InlineKeyboardButton(
                "🎧 Support Agent",
                url=getattr(config, "CUSTOMER_SERVICE_LINK", "https://t.me/ApexSupportAgent"),
            ),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def welcome_text(user, just_started_trial: bool = False) -> str:
    name = user.first_name or "Trader"
    vip_active = is_vip(user.id)

    if just_started_trial:
        return f"""
🔥 *WELCOME ABOARD, {name.upper()}!* 🔥

You just unlocked a *FREE 24-HOUR VIP PASS* — no card, no catch.
Your ✨ *VIP TRIAL* is live *right now* and expires in 24 hours.

*Here's what that gets you immediately:*
• Every 90+ Apex Elite signal — Forex, Gold *and* Crypto
• Full institutional confluence: 15M + 1H EMA/MACD/RSI
• Live Binance Radar: BTC, ETH, SOL, BNB, XRP, DOGE, ADA
• XAU/USD, EUR/USD, GBP/USD, USD/JPY
• Exact Entry, Stop Loss, TP1/TP2/TP3 on every setup
• Auto Breakeven alerts
• Smart Lot Size Calculator & Sessions Radar

⏰ *Your trial clock is already ticking*.
""".strip()

    if vip_active:
        from database import get_active_vip
        vip_data = get_active_vip(user.id)
        plan = (vip_data or {}).get("plan", "monthly")
        badge = premium_badge(plan)
        greeting = f"⚡ *Welcome back, {name}!* ({badge} Active)"
    else:
        greeting = f"👋 *Welcome to Apex Trading Signals, {name}!*"

    return f"""
{greeting}

Your institutional algorithmic signal engine for **Forex**, **Gold (XAU/USD)**, and **Crypto (Binance)**.

📊 **Features:**
• High-accuracy 15M + 1H trend confluences
• Forex & Metals: XAU/USD, EUR/USD, GBP/USD, USD/JPY
• Crypto: BTC, ETH, SOL, BNB, XRP, DOGE, ADA
• Clear Entry, SL & TP1/TP2/TP3 targets
• 90+ Score setups delivered first to VIP
• Smart Lot Calculator & Sessions Radar
• Auto Breakeven Alerts & Paper Trading Tracker

Select an action below to get started:
""".strip()


def lot_size_calculator_text(balance: float = 100.0, stop_loss_pips: float = 25.0) -> str:
    risk_1_usd = balance * 0.01
    risk_2_usd = balance * 0.02
    lot_1 = max(0.01, round((risk_1_usd / (stop_loss_pips * 10)), 2))
    lot_2 = max(0.01, round((risk_2_usd / (stop_loss_pips * 10)), 2))

    return f"""
🧮 *INSTITUTIONAL LOT SIZE & RISK CALCULATOR*
━━━━━━━━━━━━━━━━━━━━━━━━━━
Account Balance: *${balance:.2f}*
Assumed Stop Loss: *{stop_loss_pips:.0f} pips*

🛡️ *Conservative (1% Risk):*
• Max Loss: `${risk_1_usd:.2f}`
• Recommended Lot: `{lot_1} lot`

⚡ *Disciplined (2% Risk):*
• Max Loss: `${risk_2_usd:.2f}`
• Recommended Lot: `{lot_2} lot`

💡 *Tip:* Send `/calc <balance> <sl_pips>` (e.g. `/calc 250 20`)
""".strip()


def market_sessions_text() -> str:
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc)
    hour = now_utc.hour

    london_open = 8 <= hour < 16
    ny_open = 13 <= hour < 21
    tokyo_open = 0 <= hour < 8
    sydney_open = hour >= 21 or hour < 5
    overlap = 13 <= hour < 16

    return f"""
⏰ *GLOBAL FOREX MARKET SESSIONS*
━━━━━━━━━━━━━━━━━━━━━━━━━━
🕒 *Current UTC Time:* `{now_utc.strftime('%H:%M:%S UTC')}`

🇬🇧 *London (08:00 - 16:00 UTC):* {"🟢 OPEN" if london_open else "🔴 CLOSED"}
🇺🇸 *New York (13:00 - 21:00 UTC):* {"🟢 OPEN" if ny_open else "🔴 CLOSED"}
🇯🇵 *Tokyo (00:00 - 08:00 UTC):* {"🟢 OPEN" if tokyo_open else "🔴 CLOSED"}
🇦🇺 *Sydney (21:00 - 05:00 UTC):* {"🟢 OPEN" if sydney_open else "🔴 CLOSED"}

🔥 *OVERLAP KILLZONE (13:00 - 16:00 UTC):*
{"🚨 ACTIVE!" if overlap else "⏳ Waiting for London-NY overlap"}
""".strip()


def economic_news_text() -> str:
    return """
📰 *HIGH-IMPACT ECONOMIC NEWS & RISK RADAR*
━━━━━━━━━━━━━━━━━━━━━━━━━━
Major Macro Events:

🔴 *US Non-Farm Payrolls (NFP)* — First Friday (12:30 UTC)
🔴 *US CPI Inflation* — Monthly (12:30 UTC)
🔴 *FOMC Rate Decision* — 18:00 UTC
🔴 *ECB & BoE Rate Decisions*

🛡️ *Rules:*
1. No new entries 15 mins before high-impact news
2. Move SL to Breakeven before news
3. Spreads widen sharply during spikes
""".strip()


def market_sentiment_text(sentiment_state: dict) -> str:
    bull = sentiment_state.get("bull", 68)
    bear = sentiment_state.get("bear", 32)
    return f"""
🗳️ *APEX COMMUNITY MARKET SENTIMENT*
━━━━━━━━━━━━━━━━━━━━━━━━━━
🐂 *Bullish:* `{bull}%`
🐻 *Bearish:* `{bear}%`
📊 Total Votes: `{sentiment_state.get('total', 842)}`
""".strip()


def monthly_pl_report_text() -> str:
    return """
🏆 *APEX MONTHLY P&L AUDIT*
━━━━━━━━━━━━━━━━━━━━━━━━━━
• Verified Win Rate: high-probability setups only
• Tracked via automated paper-trading engine
• Full transparency on TP / SL hits
""".strip()


def broker_message() -> str:
    lines = ["🏦 *RECOMMENDED BROKERS*\n"]
    catalog = [
        ("FTMO Challenge", getattr(config, "FTMO_LINK", "")),
        ("XTB", getattr(config, "XTB_LINK", "")),
        ("Exness", getattr(config, "EXNESS_LINK", "")),
        ("FP Markets", getattr(config, "FP_MARKETS_LINK", "")),
        ("HFM", getattr(config, "HFM_LINK", "")),
    ]
    for name, link in catalog:
        if link:
            lines.append(f"• [{name}]({link})")
    return "\n".join(lines)
