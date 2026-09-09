"""
Automatic market scan job — posts free & VIP signals on a schedule.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
from database import (
    are_signals_paused,
    get_free_channel,
    get_vip_channel,
    open_paper_trade,
)
from engine import (
    MARKETS,
    generate_free_signal,
    mark_signal_posted,
)
from bot_handlers.signals import build_signal_message, get_score, get_signal_key

logger = logging.getLogger(__name__)

# In-memory dedupe for the current process lifetime
_delivered_signal_keys: set[str] = set()
_pending_elite_signals: dict[str, dict[str, Any]] = {}

VIP_SIGNAL_MIN_SCORE = getattr(config, "VIP_SCAN_SCORE", 90)


async def automatic_signal_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Scans all markets and posts high-probability setups.
    Uses non-blocking threads and short rate-limit spacing.
    """
    if are_signals_paused():
        return

    vip_channel = get_vip_channel()
    free_channel = get_free_channel()

    for symbol in MARKETS:
        try:
            signal = await asyncio.to_thread(generate_free_signal, symbol)
            if not signal:
                await asyncio.sleep(1.0)
                continue

            signal_key = get_signal_key(signal)
            if signal_key in _delivered_signal_keys:
                await asyncio.sleep(1.0)
                continue

            score = get_score(signal)

            # VIP Priority Signals (Score 90+)
            if score >= VIP_SIGNAL_MIN_SCORE:
                if vip_channel:
                    await context.bot.send_message(
                        chat_id=vip_channel,
                        text=build_signal_message(signal, vip=True),
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True,
                    )

                _pending_elite_signals[signal_key] = signal
                buttons = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "📢 Release to Free Channel",
                        callback_data=f"release_free_{signal_key}",
                    )
                ]])
                for admin_id in getattr(config, "ADMIN_IDS", set()):
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=(
                                f"👑 VIP Signal posted for {symbol}. "
                                "Tap below to also release to free channel:\n\n"
                                + build_signal_message(signal, vip=True)
                            ),
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=buttons,
                            disable_web_page_preview=True,
                        )
                    except Exception as err:
                        logger.error("Admin alert error: %s", err)

                _delivered_signal_keys.add(signal_key)
                mark_signal_posted(symbol)
                _record_paper_trade(signal, signal_key, symbol, score)
                await asyncio.sleep(1.0)
                continue

            # Free Channel Signals
            if free_channel:
                await context.bot.send_message(
                    chat_id=free_channel,
                    text=build_signal_message(signal, vip=False),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
                _delivered_signal_keys.add(signal_key)
                mark_signal_posted(symbol)
                _record_paper_trade(signal, signal_key, symbol, score)

            await asyncio.sleep(1.0)

        except Exception as err:
            logger.error("Signal error on %s: %s", symbol, err)
            await asyncio.sleep(1.0)


def _record_paper_trade(signal: dict, signal_key: str, symbol: str, score: int) -> None:
    if not getattr(config, "PAPER_TRADING_ENABLED", True):
        return
    try:
        entry_p = float(
            signal.get("price")
            or signal.get("entry_price")
            or signal.get("current_price")
            or 0.0
        )
        sl_p = float(signal.get("stop_loss") or 0.0)
        tp_p = float(
            signal.get("tp2")
            or signal.get("take_profit")
            or signal.get("take_profit_1")
            or 0.0
        )
        if entry_p > 0 and sl_p > 0 and tp_p > 0:
            open_paper_trade(
                signal_code=signal_key,
                symbol=symbol,
                direction=str(signal.get("direction", "BUY")).upper(),
                signal_score=score,
                entry_price=entry_p,
                stop_loss=sl_p,
                take_profit=tp_p,
            )
    except Exception as p_err:
        logger.debug("Paper trade record notice: %s", p_err)


def get_pending_elite_signals() -> dict[str, dict[str, Any]]:
    return _pending_elite_signals
