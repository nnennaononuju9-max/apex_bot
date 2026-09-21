"""
Callback query router for Apex Bot.
"""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
from database import (
    claim_vip_trial,
    get_free_channel,
    get_open_paper_trades,
    get_paper_trade_stats,
    get_vip_channel,
    is_vip,
)
from bot_handlers.menus import (
    broker_message,
    economic_news_text,
    lot_size_calculator_text,
    main_menu_keyboard,
    market_sentiment_text,
    market_sessions_text,
    monthly_pl_report_text,
    welcome_text,
)
from bot_handlers.commands import check_channel_membership, is_admin, _community_sentiment
from bot_handlers.payments import (
    handle_admin_payment_decision,
    handle_crypto_choice,
    handle_payment_method_choice,
    send_payment_method_menu,
    send_plan_selection_menu,
    send_vip_menu,
)

logger = logging.getLogger(__name__)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_home")],
    ])


async def menu_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # ---- Channel gate ----
    if data == "verify_channel_join":
        has_joined = await check_channel_membership(user_id, context)
        if has_joined:
            await query.answer("✅ Channel membership verified!", show_alert=True)
            await query.edit_message_text(
                welcome_text(query.from_user),
                reply_markup=main_menu_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await query.answer("❌ You have not joined the channel yet.", show_alert=True)
        return

    # ---- Back to main menu ----
    if data == "menu_home":
        await query.edit_message_text(
            welcome_text(query.from_user),
            reply_markup=main_menu_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ---- Main menu screens (edit in place + Back button) ----
    if data == "menu_calc":
        await query.edit_message_text(
            lot_size_calculator_text(100.0, 25.0),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data.startswith("calc_quick_"):
        val = float(data.replace("calc_quick_", ""))
        await query.edit_message_text(
            lot_size_calculator_text(val, 25.0),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "menu_sessions":
        await query.edit_message_text(
            market_sessions_text(),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "menu_news":
        await query.edit_message_text(
            economic_news_text(),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "menu_sentiment":
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🐂 Vote Bullish", callback_data="vote_bull"),
                InlineKeyboardButton("🐻 Vote Bearish", callback_data="vote_bear"),
            ],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_home")],
        ])
        await query.edit_message_text(
            market_sentiment_text(_community_sentiment),
            reply_markup=buttons,
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "vote_bull":
        _community_sentiment["bull"] = min(95, _community_sentiment["bull"] + 1)
        _community_sentiment["bear"] = max(5, 100 - _community_sentiment["bull"])
        _community_sentiment["total"] += 1
        await query.answer("🐂 Bullish vote recorded!", show_alert=True)
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🐂 Vote Bullish", callback_data="vote_bull"),
                InlineKeyboardButton("🐻 Vote Bearish", callback_data="vote_bear"),
            ],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_home")],
        ])
        await query.edit_message_text(
            market_sentiment_text(_community_sentiment),
            reply_markup=buttons,
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "vote_bear":
        _community_sentiment["bear"] = min(95, _community_sentiment["bear"] + 1)
        _community_sentiment["bull"] = max(5, 100 - _community_sentiment["bear"])
        _community_sentiment["total"] += 1
        await query.answer("🐻 Bearish vote recorded!", show_alert=True)
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🐂 Vote Bullish", callback_data="vote_bull"),
                InlineKeyboardButton("🐻 Vote Bearish", callback_data="vote_bear"),
            ],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_home")],
        ])
        await query.edit_message_text(
            market_sentiment_text(_community_sentiment),
            reply_markup=buttons,
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "menu_report":
        await query.edit_message_text(
            monthly_pl_report_text(),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "menu_trades":
        from database import get_recent_paper_trades

        stats = get_paper_trade_stats()
        open_trades = get_open_paper_trades()
        recent = get_recent_paper_trades(5)

        lines = [
            "📊 *APEX TRADE REVIEW*\n",
            "*Overview*",
            f"• Total trades: `{stats['total']}`",
            f"• Open: `{stats['open']}`",
            f"• Wins: `{stats['wins']}`",
            f"• Losses: `{stats['losses']}`",
            f"• Win rate: `{stats['win_rate']}%`",
            f"• Total R: `{stats['total_r']:+}R`\n",
        ]

        if open_trades:
            lines.append("*Open positions*")
            for ot in open_trades[:6]:
                entry = ot.get("entry_price", "")
                sl = ot.get("stop_loss", "")
                lines.append(
                    f"🟢 *{ot['symbol']}* {ot['direction']}\n"
                    f"   Entry `{entry}` | SL `{sl}`"
                )
            lines.append("")

        if recent:
            lines.append("*Recent closed*")
            for t in recent:
                result = str(t.get("result") or "")
                if result == "open":
                    continue
                symbol = t.get("symbol") or ""
                direction = t.get("direction") or ""
                r_mult = t.get("r_multiple")
                r_txt = f"{float(r_mult):+.1f}R" if r_mult is not None else "—"

                if result in ("tp_hit", "tp1_hit", "tp2_hit", "tp3_hit"):
                    mark = "✅"
                elif result == "sl_hit":
                    mark = "🛑"
                else:
                    mark = "•"

                lines.append(f"{mark} {symbol} {direction} | {result} | {r_txt}")
            lines.append("")

        lines.append("_Risk small. Protect capital. Process over prediction._")

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "menu_signal":
        free_channel = get_free_channel()
        vip_channel = get_vip_channel()
        lines = ["📡 *LATEST SIGNALS*\n"]
        if free_channel:
            lines.append(f"Free channel: {free_channel}")
        if is_vip(user_id) and vip_channel:
            lines.append(f"VIP channel: {vip_channel}")
        lines.append(
            "\nMarkets: BTC, ETH, SOL, BNB, XRP, DOGE, ADA, XAU, EUR, GBP, JPY"
        )
        lines.append("\n📢 https://t.me/ApexTradesHub")
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    elif data == "menu_vip":
        await send_vip_menu(query.message, user_id)

    elif data == "menu_brokers":
        await query.edit_message_text(
            broker_message(),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    elif data == "menu_refer":
        bot_username = getattr(config, "BOT_USERNAME", "ApexMarketSignalsBot").lstrip("@")
        link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        await query.edit_message_text(
            f"🎁 *Refer & Earn*\n\nShare your link:\n`{link}`\n\n"
            f"You earn +{getattr(config, 'REFERRAL_REWARD_DAYS', 5)} VIP days "
            f"(limit {getattr(config, 'REFERRAL_REWARD_LIMIT', 4)} rewards).",
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    # ---- VIP / Payment flow (kept as-is) ----
    elif data == "vip_buy":
        await send_plan_selection_menu(query.message)
    elif data == "vip_claim_trial":
        success, msg = claim_vip_trial(user_id)
        await query.answer(msg, show_alert=True)
        if success:
            await send_vip_menu(query.message, user_id)
    elif data.startswith("vip_plan_"):
        plan = data[len("vip_plan_"):]
        await send_payment_method_menu(query.message, user_id, plan)
    elif data.startswith("pay_method_"):
        method, _, plan = data[len("pay_method_"):].rpartition("_")
        await handle_payment_method_choice(query, method, plan)
    elif data.startswith("pay_crypto_"):
        option_id_str, _, plan = data[len("pay_crypto_"):].rpartition("_")
        await handle_crypto_choice(query, int(option_id_str), plan)
    elif data.startswith("pay_admin_approve_"):
        await handle_admin_payment_decision(
            query, context, int(data[len("pay_admin_approve_"):]), approve=True
        )
    elif data.startswith("pay_admin_reject_"):
        await handle_admin_payment_decision(
            query, context, int(data[len("pay_admin_reject_"):]), approve=False
        )
    elif data.startswith("release_free_"):
        if not is_admin(user_id):
            await query.answer("⛔ Admin only.", show_alert=True)
            return
        await query.answer("Release-to-free handled by signal job.")
