"""Telegram handlers package."""
from .commands import (
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
from .callbacks import menu_callback_router
from .payments import payment_proof_message_handler
from .admin import (
    setbank_command,
    setopay_command,
    addcrypto_command,
    listcrypto_command,
    setvip_command,
    scancrypto_command,
)

__all__ = [
    "start_command",
    "myvip_command",
    "trial_command",
    "calc_command",
    "sessions_command",
    "news_command",
    "sentiment_command",
    "report_command",
    "brokers_command",
    "papertrades_command",
    "broadcast_command",
    "menu_callback_router",
    "payment_proof_message_handler",
    "setbank_command",
    "setopay_command",
    "addcrypto_command",
    "listcrypto_command",
    "setvip_command",
    "scancrypto_command",
]
