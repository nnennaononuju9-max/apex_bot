"""
Apex Bot database package.

Re-exports the main public API so existing imports like:

    from database import get_user, is_vip, open_paper_trade, ...

continue to work.
"""

from .connection import (
    DATABASE_URL,
    get_connection,
    init_db,
    set_setting,
    get_setting,
    set_free_channel,
    get_free_channel,
    set_vip_channel,
    get_vip_channel,
    set_signals_paused,
    are_signals_paused,
)

from .users import (
    create_or_update_user,
    get_user,
    get_all_user_ids,
)

from .vip import (
    get_active_vip,
    is_vip,
    activate_vip,
    expire_old_vip,
    claim_vip_trial,
)

from .payments import (
    create_payment,
    get_pending_payments,
    get_pending_payment_for_user,
    approve_payment,
    reject_payment,
    get_payment_settings,
    update_payment_settings,
    get_crypto_payment_options,
    add_crypto_payment_option,
)

from .referrals import (
    create_referral,
    get_referral_count,
    get_referral_by_referred_user,
    get_rewarded_referral_count,
    mark_referral_rewarded,
)

from .paper_trades import (
    get_daily_signal_count,
    increment_daily_signal_count,
    open_paper_trade,
    get_open_paper_trades,
    close_paper_trade,
    mark_breakeven_alerted,
    get_recent_paper_trades,
    get_paper_trade_stats,
)

__all__ = [
    # connection
    "DATABASE_URL",
    "get_connection",
    "init_db",
    "set_setting",
    "get_setting",
    "set_free_channel",
    "get_free_channel",
    "set_vip_channel",
    "get_vip_channel",
    "set_signals_paused",
    "are_signals_paused",
    # users
    "create_or_update_user",
    "get_user",
    "get_all_user_ids",
    # vip
    "get_active_vip",
    "is_vip",
    "activate_vip",
    "expire_old_vip",
    "claim_vip_trial",
    # payments
    "create_payment",
    "get_pending_payments",
    "get_pending_payment_for_user",
    "approve_payment",
    "reject_payment",
    "get_payment_settings",
    "update_payment_settings",
    "get_crypto_payment_options",
    "add_crypto_payment_option",
    # referrals
    "create_referral",
    "get_referral_count",
    "get_referral_by_referred_user",
    "get_rewarded_referral_count",
    "mark_referral_rewarded",
    # paper trades + signal limits
    "get_daily_signal_count",
    "increment_daily_signal_count",
    "open_paper_trade",
    "get_open_paper_trades",
    "close_paper_trade",
    "mark_breakeven_alerted",
    "get_recent_paper_trades",
    "get_paper_trade_stats",
]

