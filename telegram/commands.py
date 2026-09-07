"""
Command handlers for Apex Bot.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
from database import (
    claim_vip_trial,
    create_or_update_user,
    create_referral,
    get_all_user_ids,
    get_active_vip,
    get_open_paper_trades,
    get_paper_trade_stats,
    get_recent_paper_trades,
    is_vip,
)
from telegram.menus import (
    channel_gatekeeper_keyboard,
    gatekeeper_text,
    lot_size_calculator_text,
    main_menu_keyboard,
    market_sessions_text,
    economic_news_text,
    market_sentiment_text,
    monthly_pl_report_text,
    welcome_text,
    broker_message,
)
from utils.formatting import premium_badge

logger = logging.getLogger(__name__)

_community_sentiment = {"bull": 68, "bear": 32, "total": 842}


def is_admin(user_id: int) -> bool:
    return user_id in getattr(config, "ADMIN_IDS", set())


async def check_channel_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if is_admin(user_id):
        return True
    if not getattr(config, "REQUIRE_FREE_CHANNEL_JOIN", True):
        return True
    channel_id = getattr(config, "FREE_CHANNEL_ID", None)
    if not channel_id:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ("member", "administrator", "creator", "restricted")
    except Exception as err:
        logger.warning("Channel check notice for %s: %s", user_id, err)
        return True


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    referred_by: Optional[int] = None
    if context.args:
        payload = context.args[0]
        if payload.startswith("ref_"):
            try:
                candidate = int(payload[4:])
                if candidate != user.id:
                    referred_by = candidate
            except ValueError:
                pass

    is_new_user = create_or_update_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        referred_by=referred_by,
    )

    if referred_by:
        create_referral(referred_by, user.id)

    just_started_trial = False
    if is_new_user:
        started, _ = claim_vip_trial(user.id)
        just_started_trial = started

    has_joined = await check_channel_membership(user.id, context)
    if not has_joined:
        await update.message.reply_text(
            gatekeeper_text(),
            reply_markup=channel_gatekeeper_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
        return

    await update.message.reply_text(
        welcome_text(user, just_started_trial=just_started_trial),
        reply_markup=main_menu_keyboard(user.id),
        parse_mode=ParseMode.MARKDOWN,
    )


async def myvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram.payments import send_vip_menu
    await send_vip_menu(update.message, update.effective_user.id)


async def trial_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    success, msg = claim_vip_trial(user.id)
    if success:
        badge = premium_badge("trial")
        await update.message.reply_text(
            f"*24-HOUR VIP TRIAL ACTIVATED!*\n\n"
            f"Your {badge} is now active for 24 hours.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(f"ℹ️ {msg}")


async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    balance = 100.0
    sl = 25.0
    if context.args:
        try:
            balance = float(context.args[0])
            if len(context.args) >= 2:
                sl = float(context.args[1])
        except ValueError:
            pass
    await update.message.reply_text(
        lot_size_calculator_text(balance, sl),
        parse_mode=ParseMode.MARKDOWN,
    )


async def sessions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(market_sessions_text(), parse_mode=ParseMode.MARKDOWN)


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(economic_news_text(), parse_mode=ParseMode.MARKDOWN)


async def sentiment_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🐂 Vote Bullish", callback_data="vote_bull"),
            InlineKeyboardButton("🐻 Vote Bearish", callback_data="vote_bear"),
        ]
    ])
    await update.message.reply_text(
        market_sentiment_text(_community_sentiment),
        reply_markup=buttons,
        parse_mode=ParseMode.MARKDOWN,
    )


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(monthly_pl_report_text(), parse_mode=ParseMode.MARKDOWN)


async def brokers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        broker_message(),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def papertrades_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    stats = get_paper_trade_stats()
    open_trades = get_open_paper_trades()
    recent = get_recent_paper_trades(5)

    lines = [
        "📊 *APEX PAPER TRADING TRACKER*\n",
        f"• Total Signals: `{stats['total']}`",
        f"• Open: `{stats['open']}`",
        f"• Wins: `🎯 {stats['wins']}`",
        f"• Losses: `🛑 {stats['losses']}`",
        f"• Win Rate: `🏆 {stats['win_rate']}%`",
        f"• Total R: `📈 {stats['total_r']:+}R`\n",
    ]
    if open_trades:
        lines.append("🟢 *OPEN POSITIONS:*")
        for ot in open_trades[:6]:
            lines.append(
                f"• *{ot['symbol']}* ({ot['direction']}) | "
                f"Entry: `{float(ot['entry_price'])}`"
            )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    announcement = " ".join(context.args)
    user_ids = get_all_user_ids()
    sent = failed = 0
    status = await update.message.reply_text(f"Broadcasting to {len(user_ids)} users...")

    for uid in user_ids:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 *APEX ANNOUNCEMENT*\n\n{announcement}",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await status.edit_text(
        f"✅ Broadcast complete.\n• Delivered: *{sent}*\n• Failed: *{failed}*",
        parse_mode=ParseMode.MARKDOWN,
    )


# Placeholders for admin payment helpers (full flow lives in payments.py)
async def setvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return
    await update.message.reply_text(
        "Usage: /setvip <telegram_id> <days> [weekly|monthly|trial]"
    )
