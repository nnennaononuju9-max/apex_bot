"""
Payment method selection, proof upload, and admin approve/reject flow.
Extracted and cleaned from the original bot.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
from database import (
    activate_vip,
    add_crypto_payment_option,
    approve_payment,
    create_payment,
    get_crypto_payment_options,
    get_payment_settings,
    get_referral_by_referred_user,
    get_rewarded_referral_count,
    mark_referral_rewarded,
    reject_payment,
    update_payment_settings,
)
from utils.formatting import premium_badge

logger = logging.getLogger(__name__)

# In-memory pending payment state (user is waiting to send proof)
PENDING_PAYMENTS: dict[int, dict[str, Any]] = {}

VIP_CURRENCY = getattr(config, "VIP_CURRENCY", "NGN")
REFERRAL_REWARD_DAYS = getattr(config, "REFERRAL_REWARD_DAYS", 5)
REFERRAL_REWARD_LIMIT = getattr(config, "REFERRAL_REWARD_LIMIT", 4)

VIP_PLANS = {
    "weekly": {
        "label": "Weekly",
        "price": getattr(config, "VIP_WEEKLY_PRICE", 2000),
        "duration_days": getattr(config, "VIP_WEEKLY_DURATION_DAYS", 7),
        "emoji": "👑",
        "badge": "👑 VIP",
    },
    "monthly": {
        "label": "Monthly",
        "price": getattr(config, "VIP_MONTHLY_PRICE", 5000),
        "duration_days": getattr(config, "VIP_MONTHLY_DURATION_DAYS", 30),
        "emoji": "💎",
        "badge": "💎 PREMIUM VIP",
    },
}


def is_admin(user_id: int) -> bool:
    return user_id in getattr(config, "ADMIN_IDS", set())


# ============================================================
# VIP MENUS
# ============================================================

async def send_vip_menu(message, user_id: int) -> None:
    from database import get_active_vip, is_vip

    if is_vip(user_id):
        vip_row = get_active_vip(user_id)
        expiry = (
            vip_row["expiry_date"].strftime("%Y-%m-%d %H:%M UTC")
            if vip_row
            else "active"
        )
        plan = (vip_row or {}).get("plan") or "monthly"
        badge = premium_badge(plan)
        text = f"""
👑💎═══════════════════💎👑
       *V I P   M E M B E R S H I P*
👑💎═══════════════════💎👑

Status: {badge} — *ACTIVE*
📅 Plan: *{VIP_PLANS.get(plan, VIP_PLANS['monthly'])['label']}*
⏳ Expiry: *{expiry}*

✨ *Your VIP Perks:*
• High-score 90+ & 100+ Apex Elite signals
• Live Binance Crypto signals with precise entry/TP/SL
• Full technical confluence & MACD/RSI confirmations
• 24/7 Priority Mentor Support
""".strip()
    else:
        text = f"""
✨👑═══════════════════👑✨
     *U P G R A D E   T O   V I P*
✨👑═══════════════════👑✨

Unlock algorithmic Forex, Gold, and Binance Crypto signals:

• VIP setups delivered first (30+ mins before free channel)
• Crypto: BTC, ETH, SOL, BNB, XRP, DOGE, ADA
• Monthly plan includes the **PREMIUM VIP Badge**
• Full TP1, TP2, TP3 targets

*Subscription Pricing:*
👑 Weekly Plan: {VIP_CURRENCY} {VIP_PLANS['weekly']['price']:,} / 7 days
💎 Monthly Plan: {VIP_CURRENCY} {VIP_PLANS['monthly']['price']:,} / 30 days
""".strip()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Choose VIP Plan & Subscribe", callback_data="vip_buy")],
        [InlineKeyboardButton("🎁 Claim 24h Free VIP Trial", callback_data="vip_claim_trial")],
    ])
    await message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def send_plan_selection_menu(message) -> None:
    weekly = VIP_PLANS["weekly"]
    monthly = VIP_PLANS["monthly"]

    text = f"""
✨👑 *SELECT YOUR VIP MEMBERSHIP PLAN* 👑✨

👑 *Weekly Pass* — {VIP_CURRENCY} {weekly['price']:,} / {weekly['duration_days']} days
• Active 👑 VIP Badge
• 90+ score signals across Forex & Crypto

💎 *Monthly Pro* — {VIP_CURRENCY} {monthly['price']:,} / {monthly['duration_days']} days (Best Value!)
• Top-Tier 💎 **PREMIUM VIP Badge**
• 100+ score Apex Elite signals
• 24/7 Priority Support
""".strip()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"👑 Weekly — {VIP_CURRENCY} {weekly['price']:,}",
            callback_data="vip_plan_weekly",
        )],
        [InlineKeyboardButton(
            f"💎 Monthly — {VIP_CURRENCY} {monthly['price']:,} (Best Value)",
            callback_data="vip_plan_monthly",
        )],
    ])
    await message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def send_payment_method_menu(message, user_id: int, plan: str) -> None:
    if plan not in VIP_PLANS:
        plan = "monthly"
    info = VIP_PLANS[plan]
    settings = get_payment_settings()

    buttons = []
    if settings.get("bank_enabled", True):
        buttons.append([
            InlineKeyboardButton("🏦 Bank Transfer", callback_data=f"pay_method_bank_{plan}")
        ])
    if settings.get("opay_enabled", True):
        buttons.append([
            InlineKeyboardButton("📱 OPay", callback_data=f"pay_method_opay_{plan}")
        ])
    if getattr(config, "CRYPTO_PAYMENTS_ENABLED", True):
        buttons.append([
            InlineKeyboardButton(
                "🪙 Crypto (USDT / TON / BTC)",
                callback_data=f"pay_method_crypto_{plan}",
            )
        ])

    await message.reply_text(
        f"💳 *VIP PAYMENT — {info['emoji']} {info['label']} Plan*\n\n"
        f"Amount: *{VIP_CURRENCY} {info['price']:,}* ({info['duration_days']} days)\n\n"
        "Select your payment method below:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ============================================================
# PAYMENT METHOD HANDLERS
# ============================================================

async def handle_payment_method_choice(query, method: str, plan: str) -> None:
    settings = get_payment_settings()
    user_id = query.from_user.id
    if plan not in VIP_PLANS:
        plan = "monthly"
    info = VIP_PLANS[plan]
    price = info["price"]

    if method == "bank":
        text = f"""
🏦 *BANK TRANSFER PAYMENT*

Bank: *{settings.get('bank_name')}*
Account Name: *{settings.get('bank_account_name')}*
Account Number: `{settings.get('bank_account_number')}`

Plan: *{info['emoji']} {info['label']}* ({info['duration_days']} days)
Amount: *{VIP_CURRENCY} {price:,}*

After sending your transfer, reply here with your **Transaction Reference** or a **screenshot** of the receipt.
""".strip()
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        PENDING_PAYMENTS[user_id] = {
            "method": "bank",
            "amount": price,
            "currency": VIP_CURRENCY,
            "plan": plan,
            "duration_days": info["duration_days"],
            "_created_at": datetime.now(timezone.utc),
        }

    elif method == "opay":
        text = f"""
📱 *OPAY PAYMENT*

OPay Name: *{settings.get('opay_name')}*
OPay Number: `{settings.get('opay_number')}`

Plan: *{info['emoji']} {info['label']}* ({info['duration_days']} days)
Amount: *{VIP_CURRENCY} {price:,}*

After paying, reply here with your **Transaction Reference** or a **screenshot** of the receipt.
""".strip()
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        PENDING_PAYMENTS[user_id] = {
            "method": "opay",
            "amount": price,
            "currency": VIP_CURRENCY,
            "plan": plan,
            "duration_days": info["duration_days"],
            "_created_at": datetime.now(timezone.utc),
        }

    elif method == "crypto":
        options = get_crypto_payment_options()
        if not options:
            await query.message.reply_text(
                "⚠️ Crypto payment is not set up yet. Please choose Bank "
                "Transfer or OPay instead, or contact support.\n\n"
                f"{getattr(config, 'CUSTOMER_SERVICE_LINK', '')}"
            )
            return
        buttons = [
            [InlineKeyboardButton(
                f"{opt['coin']} ({opt['network']})",
                callback_data=f"pay_crypto_{opt['id']}_{plan}",
            )]
            for opt in options
        ]
        await query.message.reply_text(
            "🪙 Choose a crypto currency / network:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )


async def handle_crypto_choice(query, option_id: int, plan: str) -> None:
    options = get_crypto_payment_options()
    option = next((opt for opt in options if opt["id"] == option_id), None)
    if not option:
        await query.message.reply_text(
            "⚠️ That crypto option is no longer available. "
            "Please go back and choose another payment method."
        )
        return

    info = VIP_PLANS.get(plan, VIP_PLANS["monthly"])
    text = f"""
🪙 *{option['coin']} ({option['network']}) PAYMENT*

Wallet Address:
`{option['wallet_address']}`

Plan: *{info['emoji']} {info['label']}* ({info['duration_days']} days)
Amount: *{VIP_CURRENCY} {info['price']:,} equivalent*

After sending, reply here with the **Transaction Hash (TxID)** or screenshot.
""".strip()
    await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    PENDING_PAYMENTS[query.from_user.id] = {
        "method": "crypto",
        "amount": info["price"],
        "currency": VIP_CURRENCY,
        "plan": plan,
        "duration_days": info["duration_days"],
        "crypto_coin": option["coin"],
        "crypto_network": option["network"],
        "crypto_wallet_address": option["wallet_address"],
        "_created_at": datetime.now(timezone.utc),
    }


# ============================================================
# PAYMENT PROOF HANDLER
# ============================================================

async def payment_proof_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    user = update.effective_user
    if not user or user.id not in PENDING_PAYMENTS:
        return

    pending = PENDING_PAYMENTS.pop(user.id)
    screenshot_file_id = None
    reference = None

    if update.message.photo:
        screenshot_file_id = update.message.photo[-1].file_id
        reference = update.message.caption or "Photo receipt uploaded"
    elif update.message.text:
        reference = update.message.text

    plan = pending.get("plan", "monthly")
    duration_days = pending.get("duration_days", 30)

    payment_id = create_payment(
        user_id=user.id,
        amount=pending["amount"],
        currency=pending["currency"],
        plan=plan,
        duration_days=duration_days,
        method=pending["method"],
        crypto_coin=pending.get("crypto_coin"),
        crypto_network=pending.get("crypto_network"),
        crypto_wallet_address=pending.get("crypto_wallet_address"),
        transaction_reference=reference,
        transaction_hash=reference if pending["method"] == "crypto" else None,
        screenshot_file_id=screenshot_file_id,
    )

    await update.message.reply_text(
        "✅ **Payment submitted for verification!**\n"
        "An admin will review and activate your VIP Badge shortly.",
        parse_mode=ParseMode.MARKDOWN,
    )

    safe_handle = (
        (user.username or user.first_name or "Trader")
        .replace("_", "\\_")
        .replace("*", "\\*")
    )
    safe_ref = (
        str(reference or "Receipt attached")
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("`", "")
    )
    admin_buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ Approve VIP", callback_data=f"pay_admin_approve_{payment_id}"
        ),
        InlineKeyboardButton(
            "❌ Reject", callback_data=f"pay_admin_reject_{payment_id}"
        ),
    ]])
    admin_text = f"""
💳 *NEW VIP PAYMENT PROOF*
User: @{safe_handle} (`{user.id}`)
Plan: *{plan.upper()}* ({duration_days} days)
Amount: *{pending['currency']} {pending['amount']:,}*
Method: *{pending['method']}*
Reference: `{safe_ref}`
""".strip()

    for admin_id in getattr(config, "ADMIN_IDS", set()):
        try:
            if screenshot_file_id:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=screenshot_file_id,
                    caption=admin_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=admin_buttons,
                )
            else:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=admin_buttons,
                )
        except Exception as err:
            logger.error("Admin notification failed: %s", err)


# ============================================================
# ADMIN APPROVE / REJECT
# ============================================================

async def handle_admin_payment_decision(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    payment_id: int,
    approve: bool,
) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Admin only.", show_alert=True)
        return

    if approve:
        payment = approve_payment(payment_id, query.from_user.id)
        if not payment:
            await query.answer("Already handled.", show_alert=True)
            return

        plan = payment.get("plan") or "monthly"
        duration_days = payment.get("duration_days") or 30
        activate_vip(payment["user_id"], duration_days, payment_id, plan=plan)

        badge = premium_badge(plan)
        try:
            await context.bot.send_message(
                chat_id=payment["user_id"],
                text=(
                    f"🎉 *CONGRATULATIONS!*\n"
                    f"Your VIP payment has been verified!\n"
                    f"Your {badge} is now ACTIVE for {duration_days} days."
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as err:
            logger.warning("Failed to notify user: %s", err)

        # Referral reward wiring
        referral = get_referral_by_referred_user(payment["user_id"])
        if referral and not referral.get("reward_granted"):
            if get_rewarded_referral_count(referral["referrer_id"]) < REFERRAL_REWARD_LIMIT:
                mark_referral_rewarded(referral["id"], REFERRAL_REWARD_DAYS)
                activate_vip(referral["referrer_id"], REFERRAL_REWARD_DAYS, plan="weekly")
                try:
                    await context.bot.send_message(
                        chat_id=referral["referrer_id"],
                        text=(
                            f"🎁 *REFERRAL REWARD!*\n"
                            f"Someone you referred just bought VIP — you just earned "
                            f"*{REFERRAL_REWARD_DAYS} free VIP days*!"
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as err:
                    logger.warning("Failed to notify referrer: %s", err)

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"✅ Payment #{payment_id} approved. VIP Badge active."
        )
    else:
        reject_payment(
            payment_id,
            query.from_user.id,
            "Invalid receipt or payment not received",
        )
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"❌ Payment #{payment_id} rejected.")
