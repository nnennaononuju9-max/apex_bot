"""
Automatic market scan job — posts free & VIP signals on a schedule.
Paper trading only records VIP-quality (90+) signals.
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
    generate_vip_signal,
    mark_signal_posted,
)
from bot_handlers.signals import (
    build_signal_message,
    get_score,
    get_signal_key,
)

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

VIP_SIGNAL_MIN_SCORE = getattr(config, "VIP_SCAN_SCORE", 90)

# Prevent the same signal from being delivered repeatedly
_delivered_signal_keys: set[str] = set()

# VIP signals waiting for an admin to release them to free
_pending_elite_signals: dict[str, dict[str, Any]] = {}


# ============================================================
# AUTOMATIC SIGNAL SCANNER
# ============================================================

async def automatic_signal_job(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Scan all configured markets.

    Free signals:
        Generated using the FREE_SIGNAL_SCORE threshold.

    VIP signals:
        Generated using the VIP_SCAN_SCORE threshold.

    Paper trading:
        ONLY records VIP-quality signals (90+).
    """

    if are_signals_paused():
        return

    free_channel = get_free_channel()
    vip_channel = get_vip_channel()

    if not free_channel and not vip_channel:
        logger.warning("No free or VIP channel configured.")
        return

    for symbol in MARKETS:
        try:

            # ==================================================
            # 1. Generate the normal/free signal
            # ==================================================

            free_signal = await asyncio.to_thread(
                generate_free_signal,
                symbol,
            )

            if not free_signal:
                await asyncio.sleep(1.0)
                continue

            score = get_score(free_signal)

            # ==================================================
            # 2. If the free signal is already VIP quality,
            #    use it as the VIP signal.
            #
            #    This avoids generating the same market setup
            #    twice unnecessarily.
            # ==================================================

            if score >= VIP_SIGNAL_MIN_SCORE:

                signal = free_signal

                signal_key = get_signal_key(signal)

                if signal_key in _delivered_signal_keys:
                    await asyncio.sleep(1.0)
                    continue

                # ----------------------------------------------
                # Send VIP signal
                # ----------------------------------------------

                if vip_channel:
                    await context.bot.send_message(
                        chat_id=vip_channel,
                        text=build_signal_message(
                            signal,
                            vip=True,
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True,
                    )

                # ----------------------------------------------
                # Save pending VIP signal for admin release
                # ----------------------------------------------

                _pending_elite_signals[signal_key] = signal

                buttons = InlineKeyboardMarkup(
                    [[
                        InlineKeyboardButton(
                            "📢 Release to Free Channel",
                            callback_data=f"release_free_{signal_key}",
                        )
                    ]]
                )

                # ----------------------------------------------
                # Notify admins
                # ----------------------------------------------

                for admin_id in getattr(
                    config,
                    "ADMIN_IDS",
                    set(),
                ):
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=(
                                f"👑 *VIP Signal posted for {symbol}*\n\n"
                                "Tap below to release this signal "
                                "to the free channel.\n\n"
                                + build_signal_message(
                                    signal,
                                    vip=True,
                                )
                            ),
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=buttons,
                            disable_web_page_preview=True,
                        )

                    except Exception as err:
                        logger.error(
                            "Admin alert error for %s: %s",
                            symbol,
                            err,
                        )

                # ----------------------------------------------
                # Mark as delivered
                # ----------------------------------------------

                _delivered_signal_keys.add(signal_key)

                mark_signal_posted(symbol)

                # ----------------------------------------------
                # IMPORTANT:
                # Only VIP 90+ signals enter paper trading.
                # ----------------------------------------------

                _record_paper_trade(
                    signal,
                    signal_key,
                    symbol,
                    score,
                )

                await asyncio.sleep(1.0)
                continue

            # ==================================================
            # 3. Normal FREE signal
            # ==================================================

            signal = free_signal
            signal_key = get_signal_key(signal)

            if signal_key in _delivered_signal_keys:
                await asyncio.sleep(1.0)
                continue

            if free_channel:
                await context.bot.send_message(
                    chat_id=free_channel,
                    text=build_signal_message(
                        signal,
                        vip=False,
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )

                _delivered_signal_keys.add(signal_key)

                mark_signal_posted(symbol)

                # IMPORTANT:
                # Do NOT record 65-89 free signals
                # as paper trades.

            await asyncio.sleep(1.0)

        except Exception as err:
            logger.exception(
                "Signal error on %s: %s",
                symbol,
                err,
            )

            await asyncio.sleep(1.0)


# ============================================================
# PAPER TRADE RECORDING
# ============================================================

def _record_paper_trade(
    signal: dict,
    signal_key: str,
    symbol: str,
    score: int,
) -> None:
    if not getattr(config, "PAPER_TRADING_ENABLED", True):
        return

    try:
        entry_p = float(
            signal.get("entry_price")
            or signal.get("price")
            or signal.get("current_price")
            or 0.0
        )

        sl_p = float(signal.get("stop_loss") or 0.0)

        tp1_p = float(
            signal.get("tp1")
            or signal.get("take_profit")
            or 0.0
        )

        tp2_p = float(signal.get("tp2") or 0.0)
        tp3_p = float(signal.get("tp3") or 0.0)

        # We need at least Entry, SL and TP1
        if entry_p <= 0 or sl_p <= 0 or tp1_p <= 0:
            logger.warning(
                "Paper trade skipped for %s: invalid Entry/SL/TP1",
                symbol,
            )
            return

        # Keep take_profit populated for compatibility.
        # TP2 is the final target when available;
        # otherwise fall back to TP1.
        final_tp = tp2_p if tp2_p > 0 else tp1_p

        open_paper_trade(
            signal_code=signal_key,
            symbol=symbol,
            direction=str(
                signal.get("direction", "BUY")
            ).upper(),
            signal_score=score,
            entry_price=entry_p,
            stop_loss=sl_p,
            tp1=tp1_p,
            tp2=tp2_p if tp2_p > 0 else None,
            tp3=tp3_p if tp3_p > 0 else None,
            take_profit=final_tp,
        )

    except Exception as p_err:
        logger.exception(
            "Paper trade record error for %s: %s",
            symbol,
        )

    # --------------------------------------------------------
    # Safety check: never paper trade weak/free signals
    # --------------------------------------------------------

    if score < VIP_SIGNAL_MIN_SCORE:
        return

    # --------------------------------------------------------
    # Global paper trading switch
    # --------------------------------------------------------

    if not getattr(
        config,
        "PAPER_TRADING_ENABLED",
        True,
    ):
        return

    try:

        # ----------------------------------------------------
        # Entry
        # ----------------------------------------------------

        entry_p = float(
            signal.get("entry_price")
            or signal.get("price")
            or signal.get("current_price")
            or 0.0
        )

        # ----------------------------------------------------
        # Stop Loss
        # ----------------------------------------------------

        sl_p = float(
            signal.get("stop_loss")
            or 0.0
        )

        # ----------------------------------------------------
        # Take Profit
        #
        # Paper trading uses TP2 as the main target.
        # ----------------------------------------------------

        tp_p = float(
            signal.get("tp2")
            or signal.get("take_profit")
            or signal.get("take_profit_1")
            or 0.0
        )

        # ----------------------------------------------------
        # Validate levels
        # ----------------------------------------------------

        if entry_p <= 0:
            logger.warning(
                "Invalid entry price for %s: %s",
                symbol,
                entry_p,
            )
            return

        if sl_p <= 0:
            logger.warning(
                "Invalid stop loss for %s: %s",
                symbol,
                sl_p,
            )
            return

        if tp_p <= 0:
            logger.warning(
                "Invalid take profit for %s: %s",
                symbol,
                tp_p,
            )
            return

        direction = str(
            signal.get("direction", "BUY")
        ).upper()

        # ----------------------------------------------------
        # Validate direction/price relationship
        # ----------------------------------------------------

        if direction == "BUY":

            if sl_p >= entry_p:
                logger.warning(
                    "Invalid BUY SL for %s: SL=%s Entry=%s",
                    symbol,
                    sl_p,
                    entry_p,
                )
                return

            if tp_p <= entry_p:
                logger.warning(
                    "Invalid BUY TP for %s: TP=%s Entry=%s",
                    symbol,
                    tp_p,
                    entry_p,
                )
                return

        elif direction == "SELL":

            if sl_p <= entry_p:
                logger.warning(
                    "Invalid SELL SL for %s: SL=%s Entry=%s",
                    symbol,
                    sl_p,
                    entry_p,
                )
                return

            if tp_p >= entry_p:
                logger.warning(
                    "Invalid SELL TP for %s: TP=%s Entry=%s",
                    symbol,
                    tp_p,
                    entry_p,
                )
                return

        else:
            logger.warning(
                "Invalid direction for %s: %s",
                symbol,
                direction,
            )
            return

        # ----------------------------------------------------
        # Open paper trade
        # ----------------------------------------------------

        trade_id = open_paper_trade(
            signal_code=signal_key,
            symbol=symbol,
            direction=direction,
            signal_score=score,
            entry_price=entry_p,
            stop_loss=sl_p,
            take_profit=tp_p,
        )

        if trade_id:
            logger.info(
                "Paper trade opened: %s %s score=%s entry=%s SL=%s TP=%s",
                symbol,
                direction,
                score,
                entry_p,
                sl_p,
                tp_p,
            )

    except Exception as err:
        logger.exception(
            "Paper trade record error for %s: %s",
            symbol,
            err,
        )


# ============================================================
# PENDING VIP SIGNALS
# ============================================================

def get_pending_elite_signals() -> dict[str, dict[str, Any]]:
    return _pending_elite_signals
