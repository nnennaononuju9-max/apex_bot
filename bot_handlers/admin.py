"""
Admin-only commands: setvip, setbank, setopay, addcrypto, listcrypto, scancrypto.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from database import (
    activate_vip,
    add_crypto_payment_option,
    get_crypto_payment_options,
    update_payment_settings,
)
from engine import create_signal
from telegram.signals import build_signal_message
from utils.formatting import premium_badge

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    import config
    return user_id in getattr(config, "ADMIN_IDS", set())


async def setbank_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: /setbank BankName|AccountName|AccountNumber"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    raw = " ".join(context.args)
    parts = [part.strip() for part in raw.split("|")]

    if len(parts) != 3:
        await update.message.reply_text(
            "Usage: /setbank BankName|AccountName|AccountNumber"
        )
        return

    update_payment_settings(
        bank_enabled=True,
        bank_name=parts[0],
        bank_account_name=parts[1],
        bank_account_number=parts[2],
    )
    await update.message.reply_text("✅ Bank details updated.")


async def setopay_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: /setopay Name|Number"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    raw = " ".join(context.args)
    parts = [part.strip() for part in raw.split("|")]

    if len(parts) != 2:
        await update.message.reply_text("Usage: /setopay Name|Number")
        return

    update_payment_settings(
        opay_enabled=True,
        opay_name=parts[0],
        opay_number=parts[1],
    )
    await update.message.reply_text("✅ OPay details updated.")


async def addcrypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: /addcrypto Coin|Network|WalletAddress"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    raw = " ".join(context.args)
    parts = [part.strip() for part in raw.split("|")]

    if len(parts) != 3:
        await update.message.reply_text(
            "Usage: /addcrypto Coin|Network|WalletAddress\n"
            "Example: /addcrypto USDT|BEP20|0xABC..."
        )
        return

    add_crypto_payment_option(parts[0], parts[1], parts[2])
    await update.message.reply_text(f"✅ {parts[0].upper()} ({parts[1]}) added.")


async def listcrypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: list configured crypto wallets."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    options = get_crypto_payment_options()
    if not options:
        await update.message.reply_text(
            "No crypto options configured yet. Use /addcrypto to add one."
        )
        return

    lines = ["🪙 *Configured crypto payment options:*\n"]
    for option in options:
        lines.append(
            f"• {option['coin']} ({option['network']}): `{option['wallet_address']}`"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def setvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: /setvip <telegram_id> <days> [weekly|monthly]"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /setvip TELEGRAM_ID DAYS [weekly|monthly]\n"
            "Example: /setvip 123456789 30 monthly"
        )
        return

    try:
        target_id = int(context.args[0])
        days = int(context.args[1])
        plan = context.args[2].lower() if len(context.args) > 2 else "monthly"
        if plan not in ("weekly", "monthly", "trial"):
            plan = "monthly"

        activate_vip(target_id, days, plan=plan)
        badge = premium_badge(plan)
        await update.message.reply_text(
            f"✅ Success! Activated {badge} for user `{target_id}` for {days} days."
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"🎉 An admin has activated your {badge} for {days} days! "
                    "Enjoy full VIP signals access."
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
    except Exception as err:
        await update.message.reply_text(f"Error: {err}")


async def scancrypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin: on-demand scan of the 7 Binance crypto markets."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    crypto_markets = [
        "BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD",
        "XRP/USD", "DOGE/USD", "ADA/USD",
    ]
    await update.message.reply_text(
        f"🔍 Scanning {len(crypto_markets)} Binance crypto currencies..."
    )

    found = 0
    for symbol in crypto_markets:
        signal = create_signal(symbol, minimum_score=70)
        if signal:
            found += 1
            await update.message.reply_text(
                build_signal_message(signal, vip=signal.get("score", 0) >= 90),
                parse_mode=ParseMode.MARKDOWN,
            )

    if found == 0:
        await update.message.reply_text(
            "⚪ No qualifying crypto setups right now (requires 70+ score)."
        )
