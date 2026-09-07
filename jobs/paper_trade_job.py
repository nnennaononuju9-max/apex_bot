"""
Paper trade monitor job — checks open simulated trades against live prices.
"""
from __future__ import annotations

import asyncio
import logging

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
from database import (
    close_paper_trade,
    get_free_channel,
    get_open_paper_trades,
    get_vip_channel,
    mark_breakeven_alerted,
)
from engine import get_latest_price

logger = logging.getLogger(__name__)


async def paper_trade_monitor_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Monitors all open paper trades, checks live prices against TP/SL,
    updates the database, and alerts the channels.
    """
    if not getattr(config, "PAPER_TRADING_ENABLED", True):
        return

    open_trades = get_open_paper_trades()
    if not open_trades:
        return

    vip_channel = get_vip_channel()
    free_channel = get_free_channel()

    for trade in open_trades:
        try:
            symbol = trade["symbol"]
            current_price = await asyncio.to_thread(get_latest_price, symbol)
            if not current_price:
                continue

            direction = str(trade["direction"]).upper()
            entry = float(trade["entry_price"])
            sl = float(trade["stop_loss"])
            tp = float(trade["take_profit"])
            trade_id = trade["id"]

            hit_tp = False
            hit_sl = False

            if direction == "BUY":
                if current_price >= tp:
                    hit_tp = True
                elif current_price <= sl:
                    hit_sl = True
            elif direction == "SELL":
                if current_price <= tp:
                    hit_tp = True
                elif current_price >= sl:
                    hit_sl = True

            if hit_tp:
                risk = abs(entry - sl)
                reward = abs(tp - entry)
                r_mult = round(reward / risk, 2) if risk > 0 else 1.5
                close_paper_trade(trade_id, current_price, "tp_hit", r_mult)

                alert = (
                    f"🎯 *[PAPER TRADE: TAKE PROFIT HIT!]*\n\n"
                    f"• *Market:* #{symbol}\n"
                    f"• *Direction:* {direction}\n"
                    f"• *Entry Price:* `{entry}`\n"
                    f"• *Exit Price:* `{current_price}`\n"
                    f"• *Risk:Reward:* `+{r_mult}R` Profit!\n\n"
                    f"✅ *Target reached smoothly.*"
                )
                if vip_channel:
                    await context.bot.send_message(
                        chat_id=vip_channel, text=alert, parse_mode=ParseMode.MARKDOWN
                    )
                if free_channel:
                    await context.bot.send_message(
                        chat_id=free_channel, text=alert, parse_mode=ParseMode.MARKDOWN
                    )

            elif hit_sl:
                close_paper_trade(trade_id, current_price, "sl_hit", -1.0)
                alert = (
                    f"🛑 *[PAPER TRADE: STOP LOSS HIT]*\n\n"
                    f"• *Market:* #{symbol}\n"
                    f"• *Direction:* {direction}\n"
                    f"• *Entry Price:* `{entry}`\n"
                    f"• *Exit Price:* `{current_price}`\n"
                    f"• *Result:* `-1.0R` (Capital preserved)"
                )
                if vip_channel:
                    await context.bot.send_message(
                        chat_id=vip_channel, text=alert, parse_mode=ParseMode.MARKDOWN
                    )

            else:
                # Auto Breakeven Alert when halfway to TP
                progress = 0.0
                if direction == "BUY" and tp > entry:
                    progress = (current_price - entry) / (tp - entry)
                elif direction == "SELL" and entry > tp:
                    progress = (entry - current_price) / (entry - tp)

                if progress >= 0.5 and not trade.get("breakeven_alerted"):
                    be_msg = (
                        f"🛡️ *[MOVE STOP LOSS TO BREAKEVEN]*\n\n"
                        f"• *Market:* #{symbol} ({direction})\n"
                        f"• *Current Gain:* `+{round(progress * 100)}%` towards Take Profit!\n"
                        f"• *Action:* Shift your Stop Loss to your Entry price `{entry}` now.\n"
                        f"• *Result:* Your trade is now **100% Risk-Free**."
                    )
                    if vip_channel:
                        await context.bot.send_message(
                            chat_id=vip_channel, text=be_msg, parse_mode=ParseMode.MARKDOWN
                        )
                    mark_breakeven_alerted(trade_id)

            await asyncio.sleep(0.5)
        except Exception as err:
            logger.error("Paper trade monitor error on %s: %s", trade.get("symbol"), err)
