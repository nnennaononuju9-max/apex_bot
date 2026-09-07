import os

# ============================================================
# TELEGRAM
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Free Telegram channel (e.g. -1001234567890 or @ApexFreeSignals)
FREE_CHANNEL_ID = os.getenv("FREE_CHANNEL_ID", "")

# VIP Telegram channel (e.g. -1009876543210 or @ApexVipSignals)
VIP_CHANNEL_ID = os.getenv("VIP_CHANNEL_ID", "")

# ============================================================
# ADMINS
# ============================================================

# Comma-separated admin Telegram IDs e.g. "123456789,987654321"
ADMIN_IDS = {
    int(admin_id.strip())
    for admin_id in os.getenv("ADMIN_IDS", "").split(",")
    if admin_id.strip().isdigit()
}

# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL", "")

# ============================================================
# MARKET DATA & APIS
# ============================================================

# Twelve Data for Forex & Gold
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")

# Binance API Key (Optional — Binance public endpoints work without key,
# but providing your API key unlocks higher rate limits on cloud servers)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Number of candles requested
CANDLE_LIMIT = int(os.getenv("CANDLE_LIMIT", "150"))

# ============================================================
# BROKER AFFILIATE / PARTNER LINKS
# ============================================================

EXNESS_LINK = os.getenv("EXNESS_LINK", "https://one.exness-track.com/a/partner_apex")
FTMO_LINK = os.getenv("FTMO_LINK", "https://ftmo.com/?ref=apex_partner")
XTB_LINK = os.getenv("XTB_LINK", "https://xtb.com/en?promo=apex_signals")
FP_MARKETS_LINK = os.getenv("FP_MARKETS_LINK", "https://fpmarkets.com/?camp=apex_vip")
HFM_LINK = os.getenv("HFM_LINK", "https://hfm.com/?refid=apex_vip")

# Telegram customer service handle/link
CUSTOMER_SERVICE_LINK = os.getenv("CUSTOMER_SERVICE_LINK", "https://t.me/ApexSupportAgent")

# ============================================================
# SERVER
# ============================================================

PORT = int(os.getenv("PORT", "8080"))

# ============================================================
# SIGNAL SETTINGS
# ============================================================

# Minimum score for signals allowed in the free channel (out of 110)
FREE_SIGNAL_SCORE = int(os.getenv("FREE_SIGNAL_SCORE", "70"))

# Minimum score detected for VIP channel / priority scanner (out of 110)
VIP_SCAN_SCORE = int(os.getenv("VIP_SCAN_SCORE", "90"))

# Automatic market scan interval in minutes (scans all forex + crypto)
SIGNAL_INTERVAL_MINUTES = int(os.getenv("SIGNAL_INTERVAL_MINUTES", "30"))

# Maximum number of automatically posted signals per market per day
MAX_SIGNALS_PER_MARKET_PER_DAY = int(os.getenv("MAX_SIGNALS_PER_MARKET_PER_DAY", "4"))

# ============================================================
# SIGNAL CONTROL
# ============================================================

SIGNALS_PAUSED_DEFAULT = os.getenv("SIGNALS_PAUSED_DEFAULT", "false").lower() == "true"
TEST_MODE_DEFAULT = os.getenv("TEST_MODE_DEFAULT", "false").lower() == "true"

# ============================================================
# VIP SUBSCRIPTION PLANS & PRICING
# ============================================================

VIP_CURRENCY = os.getenv("VIP_CURRENCY", "NGN").upper()

# Weekly plan
VIP_WEEKLY_PRICE = int(os.getenv("VIP_WEEKLY_PRICE", "2000"))
VIP_WEEKLY_DURATION_DAYS = int(os.getenv("VIP_WEEKLY_DURATION_DAYS", "7"))

# Monthly plan (includes 💎 PREMIUM VIP badge)
VIP_MONTHLY_PRICE = int(os.getenv("VIP_MONTHLY_PRICE", "5000"))
VIP_MONTHLY_DURATION_DAYS = int(os.getenv("VIP_MONTHLY_DURATION_DAYS", "30"))

# ============================================================
# REFERRAL PROGRAM (Personal rewards only; auto dashboard disabled)
# ============================================================

REFERRAL_REWARD_DAYS = int(os.getenv("REFERRAL_REWARD_DAYS", "5"))
REFERRAL_REWARD_LIMIT = int(os.getenv("REFERRAL_REWARD_LIMIT", "4"))

# ============================================================
# PAYMENT METHODS (BANK / OPAY / CRYPTO)
# ============================================================

CRYPTO_PAYMENTS_ENABLED = os.getenv("CRYPTO_PAYMENTS_ENABLED", "true").lower() == "true"
OPAY_PAYMENTS_ENABLED = os.getenv("OPAY_PAYMENTS_ENABLED", "true").lower() == "true"
BANK_PAYMENTS_ENABLED = os.getenv("BANK_PAYMENTS_ENABLED", "true").lower() == "true"

# Default fallback payment details
OPAY_NAME = os.getenv("OPAY_NAME", "Kingsley Signals")
OPAY_NUMBER = os.getenv("OPAY_NUMBER", "8124930192")

BANK_NAME = os.getenv("BANK_NAME", "Access Bank")
BANK_ACCOUNT_NAME = os.getenv("BANK_ACCOUNT_NAME", "Apex Capital Global")
BANK_ACCOUNT_NUMBER = os.getenv("BANK_ACCOUNT_NUMBER", "1482930194")

PAYMENT_PROOF_ENABLED = os.getenv("PAYMENT_PROOF_ENABLED", "true").lower() == "true"
ONE_PENDING_PAYMENT_PER_USER = os.getenv("ONE_PENDING_PAYMENT_PER_USER", "true").lower() == "true"

# ============================================================
# BOT IDENTITY
# ============================================================

BOT_NAME = os.getenv("BOT_NAME", "Apex Trade Signals Bot")
BOT_USERNAME = os.getenv("BOT_USERNAME", "ApexTradeSignalsBot")
# Hardcoded mandatory channel membership requirement (Users MUST join channel to use bot)
REQUIRE_FREE_CHANNEL_JOIN = os.getenv("REQUIRE_FREE_CHANNEL_JOIN", "true").lower() == "true"

# ============================================================
# AUTOMATIC PAPER TRADING & PERFORMANCE
# ============================================================

PAPER_TRADING_ENABLED = os.getenv("PAPER_TRADING_ENABLED", "true").lower() == "true"
PAPER_TRADE_CHECK_INTERVAL_SECONDS = int(os.getenv("PAPER_TRADE_CHECK_INTERVAL_SECONDS", "60"))
