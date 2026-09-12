"""
Paper trade monitor job — monitors open simulated trades against live prices.
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


async def paper_trade_monitor_job(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Monitor all open paper trades.

    Rules:
    - BUY: TP above entry, SL below entry.
    - SELL: TP below entry, SL above entry.
    - TP = positive R.
    - SL = -1R.
    - Breakeven alert is sent once at 50% progress toward TP.
    - Database remains the source of truth for trade state.
    """

    if not getattr(config, "PAPER_TRADING_ENABLED", True):
        return

    try:
        open_trades = get_open_paper_trades()
    except Exception as err:
        logger.error("Unable to load open paper trades: %s", err)
        return

    if not open_trades:
        return

    vip_channel = get_vip_channel()
    free_channel = get_free_channel()

    for trade in open_trades:
        try:
            trade_id = trade["id"]
            symbol = str(trade["symbol"])
            direction = str(trade["direction"]).upper()

            entry = float(trade["entry_price"])
            sl = float(trade["stop_loss"])
            tp = float(trade["take_profit"])

            current_price = await asyncio.to_thread(
                get_latest_price,
                symbol,
            )

            if current_price is None:
                continue

            current_price = float(current_price)

            if current_price <= 0:
                continue

            # --------------------------------------------------
            # Validate trade geometry
            # --------------------------------------------------

            if direction == "BUY":
                if not (sl < entry < tp):
                    logger.warning(
                        "Invalid BUY trade geometry: id=%s symbol=%s "
                        "entry=%s sl=%s tp=%s",
                        trade_id,
                        symbol,
                        entry,
                        sl,
                        tp,
                    )
                    continue

            elif direction == "SELL":
                if not (tp < entry < sl):
                    logger.warning(
                        "Invalid SELL trade geometry: id=%s symbol=%s "
                        "entry=%s sl=%s tp=%s",
                        trade_id,
                        symbol,
                        entry,
                        sl,
                        tp,
                    )
                    continue

            else:
                logger.warning(
                    "Unknown paper trade direction: %s",
                    direction,
                )
                continue

            # --------------------------------------------------
            # Risk / reward
            # --------------------------------------------------

            risk = abs(entry - sl)
            reward = abs(tp - entry)

            if risk <= 0:
                logger.warning(
                    "Invalid zero-risk trade: id=%s symbol=%s",
                    trade_id,
                    symbol,
                )
                continue

            full_tp_r = reward / risk

            # --------------------------------------------------
            # Check TP / SL
            # --------------------------------------------------

            hit_tp = False
            hit_sl = False

            if direction == "BUY":
                hit_tp = current_price >= tp
                hit_sl = current_price <= sl

            elif direction == "SELL":
                hit_tp = current_price <= tp
                hit_sl = current_price >= sl

            # --------------------------------------------------
            # TAKE PROFIT
            # --------------------------------------------------

            if hit_tp:
                r_multiple = round(full_tp_r, 2)

                closed = close_paper_trade(
                    trade_id=trade_id,
                    exit_price=current_price,
                    result="tp_hit",
                    r_multiple=r_multiple,
                )

                # Another monitor cycle/process may have closed it.
                if not closed:
                    continue

                alert = (
                    "🎯 *PAPER TRADE — TAKE PROFIT HIT!*\n\n"
                    f"• *Market:* #{symbol}\n"
                    f"• *Direction:* `{direction}`\n"
                    f"• *Entry:* `{entry}`\n"
                    f"• *Exit:* `{current_price}`\n"
                    f"• *Result:* `+{r_multiple}R`\n\n"
                    "✅ *Take-profit target reached.*"
                )

                await _send_trade_alert(
                    context,
                    alert,
                    vip_channel,
                    free_channel,
                )

                await asyncio.sleep(0.25)
                continue

            # --------------------------------------------------
            # STOP LOSS
            # --------------------------------------------------

            if hit_sl:
                closed = close_paper_trade(
                    trade_id=trade_id,
                    exit_price=current_price,
                    result="sl_hit",
                    r_multiple=-1.0,
                )

                if not closed:
                    continue

                alert = (
                    "🛑 *PAPER TRADE — STOP LOSS HIT*\n\n"
                    f"• *Market:* #{symbol}\n"
                    f"• *Direction:* `{direction}`\n"
                    f"• *Entry:* `{entry}`\n"
                    f"• *Exit:* `{current_price}`\n"
                    f"• *Result:* `-1.00R`\n\n"
                    "📉 *Trade closed at the defined risk level.*"
                )

                # SL results go to VIP only, matching your
                # existing behaviour.
                if vip_channel:
                    await _send_message(
                        context,
                        vip_channel,
                        alert,
                    )

                await asyncio.sleep(0.25)
                continue

            # --------------------------------------------------
            # BREAKEVEN / TRADE PROGRESS
            # --------------------------------------------------

            progress = 0.0

            if direction == "BUY":
                progress = (current_price - entry) / (tp - entry)

            elif direction == "SELL":
                progress = (entry - current_price) / (entry - tp)

            progress = max(0.0, min(progress, 1.0))

            # At 50% progress, send one alert.
            if progress >= 0.50 and not trade.get("breakeven_alerted"):
                progress_percent = round(progress * 100)

                be_msg = (
                    "🛡️ *PAPER TRADE — BREAKEVEN ALERT*\n\n"
                    f"• *Market:* #{symbol}\n"
                    f"• *Direction:* `{direction}`\n"
                    f"• *Entry:* `{entry}`\n"
                    f"• *Current Price:* `{current_price}`\n"
                    f"• *TP Progress:* `{progress_percent}%`\n\n"
                    f"⚠️ *Consider moving SL to entry:* `{entry}`\n"
                    "This would reduce the remaining downside risk."
                )

                if vip_channel:
                    await _send_message(
                        context,
                        vip_channel,
                        be_msg,
                    )

                mark_breakeven_alerted(trade_id)

            await asyncio.sleep(0.25)

        except Exception as err:
            logger.exception(
                "Paper trade monitor error on %s: %s",
                trade.get("symbol", "UNKNOWN"),
            )


async def _send_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: str,
    text: str,
) -> None:
    """Safely send a Telegram message."""

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except Exception as err:
        logger.error(
            "Failed to send paper trade alert to %s: %s",
            chat_id,
            err,
        )


async def _send_trade_alert(
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    vip_channel: str | None,
    free_channel: str | None,
) -> None:
    """Send TP alerts to VIP and free channels."""

    if vip_channel:
        await _send_message(
            context,
            vip_channel,
            text,
        )

    if free_channel:
        await _send_message(
            context,
            free_channel,
            text,
        )
