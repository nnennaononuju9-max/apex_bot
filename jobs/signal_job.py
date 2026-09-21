"""
Automatic signal scanning job.

Runs on a schedule (see main.py) and posts qualified
free / VIP signals to the configured Telegram channels.
"""
from __future__ import annotations

import asyncio
import logging

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
from database import (
    are_signals_paused,
    get_free_channel,
    get_vip_channel,
    open_paper_trade,
)
from engine.market_data import MARKETS
from engine.signal_manager import (
    confirm_signal_delivery,
    prepare_free_signal,
    prepare_vip_signal,
    prune_old_signal_keys,
    signal_is_publishable,
)
from bot_handlers.signals import build_signal_message

logger = logging.getLogger(__name__)


async def automatic_signal_job(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Scan all markets and post eligible signals.
    """

    try:
        if are_signals_paused():
            logger.info("Signals are paused — skipping scan.")
            return
    except Exception as err:
        logger.error("Unable to read signals-paused flag: %s", err)

    free_channel = None
    vip_channel = None

    try:
        free_channel = get_free_channel()
    except Exception as err:
        logger.error("Unable to load free channel: %s", err)

    try:
        vip_channel = get_vip_channel()
    except Exception as err:
        logger.error("Unable to load VIP channel: %s", err)

    if not free_channel and not vip_channel:
        logger.warning("No free or VIP channel configured — nothing to post.")
        return

    prune_old_signal_keys()

    markets = list(MARKETS)
    logger.info("Starting automatic signal scan across %d markets.", len(markets))

    for symbol in markets:
        try:
            await _process_market(
                context,
                symbol=symbol,
                free_channel=free_channel,
                vip_channel=vip_channel,
            )
        except Exception:
            logger.exception("Unhandled error while scanning %s", symbol)

        await asyncio.sleep(0.4)

    logger.info("Automatic signal scan finished.")


async def _process_market(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    symbol: str,
    free_channel: str | None,
    vip_channel: str | None,
) -> None:
    """Scan one market for VIP first, then free."""

    # VIP first so free does not lock the setup before VIP posts
    if vip_channel:
        vip_signal = await asyncio.to_thread(
            prepare_vip_signal,
            symbol,
        )

        if vip_signal and signal_is_publishable(vip_signal):
            await _deliver_signal(
                context,
                signal=vip_signal,
                channel_id=vip_channel,
                vip=True,
            )

    if free_channel:
        free_signal = await asyncio.to_thread(
            prepare_free_signal,
            symbol,
        )

        if free_signal and signal_is_publishable(free_signal):
            await _deliver_signal(
                context,
                signal=free_signal,
                channel_id=free_channel,
                vip=False,
    )

async def _deliver_signal(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    signal: dict,
    channel_id: str,
    vip: bool,
) -> None:
    """Format, send, confirm delivery, and open paper trade."""

    symbol = signal.get("symbol", "UNKNOWN")
    direction = signal.get("direction", "")
    score = signal.get("score", 0)

    try:
        text = build_signal_message(signal, vip=vip)
    except Exception as err:
        logger.error("Failed to format signal for %s: %s", symbol, err)
        return

    try:
        await context.bot.send_message(
            chat_id=channel_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except Exception as err:
        logger.error(
            "Failed to post %s signal for %s to %s: %s",
            "VIP" if vip else "FREE",
            symbol,
            channel_id,
            err,
        )
        return

    try:
        confirmed = confirm_signal_delivery(signal)
        if not confirmed:
            logger.info(
                "Signal for %s was already marked delivered (duplicate).",
                symbol,
            )
            return
    except Exception as err:
        logger.error("Failed to confirm delivery for %s: %s", symbol, err)
        return

    logger.info(
        "Posted %s %s signal for %s (score=%s)",
        "VIP" if vip else "FREE",
        direction,
        symbol,
        score,
    )

    if getattr(config, "PAPER_TRADING_ENABLED", True):
        try:
            open_paper_trade(
                signal_code=str(signal.get("signal_code") or ""),
                symbol=str(signal.get("symbol")),
                direction=str(signal.get("direction")),
                signal_score=int(signal.get("score") or 0),
                entry_price=float(signal.get("entry_price")),
                stop_loss=float(signal.get("stop_loss")),
                take_profit=float(
                    signal.get("tp3")
                    or signal.get("take_profit")
                    or signal.get("tp1")
                    or 0
                ),
                tp1=float(signal["tp1"]) if signal.get("tp1") is not None else None,
                tp2=float(signal["tp2"]) if signal.get("tp2") is not None else None,
                tp3=float(signal["tp3"]) if signal.get("tp3") is not None else None,
            )
        except Exception as err:
            logger.error("Failed to open paper trade for %s: %s", symbol, err)
