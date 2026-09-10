"""
Apex Trade Signals Bot — entry point.
"""
from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
from database import init_db, set_free_channel, set_vip_channel
from jobs import automatic_signal_job, paper_trade_monitor_job
from bot_handlers.commands import (
    start_command,
    myvip_command,
    trial_command,
    calc_command,
    sessions_command,
    news_command,
    sentiment_command,
    report_command,
    brokers_command,
    papertrades_command,
    broadcast_command,
)
from bot_handlers.admin import (
    setbank_command,
    setopay_command,
    addcrypto_command,
    listcrypto_command,
    setvip_command,
    scancrypto_command,
    pausesignals_command,
    resumesignals_command,
    signalstatus_command,
)
from utils.logging import setup_logging

setup_logging()
logger = logging.getLogger("apex")


async def post_init(application: Application) -> None:
    init_db()
    if getattr(config, "FREE_CHANNEL_ID", None):
        set_free_channel(str(config.FREE_CHANNEL_ID))
    if getattr(config, "VIP_CHANNEL_ID", None):
        set_vip_channel(str(config.VIP_CHANNEL_ID))
    logger.info("Apex Trading Bot started successfully.")


def main() -> None:
    token = getattr(config, "BOT_TOKEN", None)
    if not token:
        raise RuntimeError("BOT_TOKEN is missing in config / environment.")

    if not getattr(config, "DATABASE_URL", None):
        raise RuntimeError(
            "DATABASE_URL is missing or empty. "
            "Set DATABASE_URL before starting the bot."
        )

    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    # ---- User commands ----
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("vip", myvip_command))
    application.add_handler(CommandHandler("myvip", myvip_command))
    application.add_handler(CommandHandler("trial", trial_command))
    application.add_handler(CommandHandler("brokers", brokers_command))
    application.add_handler(CommandHandler("calc", calc_command))
    application.add_handler(CommandHandler("lotsize", calc_command))
    application.add_handler(CommandHandler("sessions", sessions_command))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CommandHandler("sentiment", sentiment_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("trades", papertrades_command))
    application.add_handler(CommandHandler("papertrades", papertrades_command))
    application.add_handler(CommandHandler("performance", papertrades_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))

    # ---- Admin commands ----
    application.add_handler(CommandHandler("setvip", setvip_command))
    application.add_handler(CommandHandler("setbank", setbank_command))
    application.add_handler(CommandHandler("setopay", setopay_command))
    application.add_handler(CommandHandler("addcrypto", addcrypto_command))
    application.add_handler(CommandHandler("listcrypto", listcrypto_command))
    application.add_handler(CommandHandler("scancrypto", scancrypto_command))
    application.add_handler(CommandHandler("pausesignals", pausesignals_command))
    application.add_handler(CommandHandler("resumesignals", resumesignals_command))
    application.add_handler(CommandHandler("signalstatus", signalstatus_command))

    # ---- Callbacks ----
    application.add_handler(CallbackQueryHandler(menu_callback_router))

    # ---- Payment proof ----
    application.add_handler(
        MessageHandler(
            (filters.TEXT & \~filters.COMMAND) | filters.PHOTO,
            payment_proof_message_handler,
        )
)

    # ---- Jobs ----
    application.job_queue.run_repeating(
        automatic_signal_job,
        interval=getattr(config, "SIGNAL_INTERVAL_MINUTES", 30) * 60,
        first=15,
    )

    if getattr(config, "PAPER_TRADING_ENABLED", True):
        application.job_queue.run_repeating(
            paper_trade_monitor_job,
            interval=getattr(config, "PAPER_TRADE_CHECK_INTERVAL_SECONDS", 60),
            first=20,
        )

    logger.info("Apex Telegram Bot is now polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
