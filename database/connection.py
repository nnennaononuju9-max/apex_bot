"""
Database connection and schema initialization for Apex Bot.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row

import config

# ============================================================
# DATABASE CONNECTION
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL", "") or getattr(config, "DATABASE_URL", "")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is missing.")
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    if not DATABASE_URL:
        print("[WARN] No DATABASE_URL provided. Database initialization skipped.")
        return

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_admin BOOLEAN DEFAULT FALSE,
                    is_blocked BOOLEAN DEFAULT FALSE,
                    first_started_at TIMESTAMPTZ DEFAULT NOW(),
                    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
                    referred_by BIGINT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
            """)

            # VIP Subscriptions table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vip_subscriptions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                    start_date TIMESTAMPTZ NOT NULL,
                    expiry_date TIMESTAMPTZ NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    payment_id BIGINT,
                    plan TEXT NOT NULL DEFAULT 'monthly',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            cur.execute("""
                ALTER TABLE vip_subscriptions
                ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'monthly';
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_vip_subscriptions_user ON vip_subscriptions(user_id);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_vip_subscriptions_expiry ON vip_subscriptions(expiry_date);
            """)

            # Payments table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                    amount NUMERIC(18, 2) NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'NGN',
                    plan TEXT NOT NULL DEFAULT 'monthly',
                    duration_days INTEGER NOT NULL DEFAULT 30,
                    method TEXT NOT NULL,
                    crypto_coin TEXT,
                    crypto_network TEXT,
                    crypto_wallet_address TEXT,
                    transaction_reference TEXT,
                    transaction_hash TEXT,
                    screenshot_file_id TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    approved_by BIGINT,
                    approved_at TIMESTAMPTZ,
                    rejected_by BIGINT,
                    rejected_at TIMESTAMPTZ,
                    rejection_reason TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            cur.execute("""
                ALTER TABLE payments ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'monthly';
            """)
            cur.execute("""
                ALTER TABLE payments ADD COLUMN IF NOT EXISTS duration_days INTEGER NOT NULL DEFAULT 30;
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
            """)

            # Referrals table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id BIGSERIAL PRIMARY KEY,
                    referrer_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                    referred_user_id BIGINT UNIQUE NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                    reward_days INTEGER DEFAULT 0,
                    reward_granted BOOLEAN DEFAULT FALSE,
                    rewarded_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            # Payment Settings table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS payment_settings (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    opay_enabled BOOLEAN DEFAULT TRUE,
                    opay_name TEXT,
                    opay_number TEXT,
                    bank_enabled BOOLEAN DEFAULT TRUE,
                    bank_name TEXT,
                    bank_account_name TEXT,
                    bank_account_number TEXT,
                    crypto_enabled BOOLEAN DEFAULT TRUE,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            cur.execute("""
                INSERT INTO payment_settings (
                    id, opay_enabled, opay_name, opay_number,
                    bank_enabled, bank_name, bank_account_name, bank_account_number,
                    crypto_enabled
                )
                VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
            """, (
                getattr(config, "OPAY_PAYMENTS_ENABLED", True),
                getattr(config, "OPAY_NAME", None),
                getattr(config, "OPAY_NUMBER", None),
                getattr(config, "BANK_PAYMENTS_ENABLED", True),
                getattr(config, "BANK_NAME", None),
                getattr(config, "BANK_ACCOUNT_NAME", None),
                getattr(config, "BANK_ACCOUNT_NUMBER", None),
                getattr(config, "CRYPTO_PAYMENTS_ENABLED", True),
            ))

            # Backfill NULL bank/opay details on existing row (production fix)
            cur.execute("""
                UPDATE payment_settings
                SET
                    opay_name = COALESCE(opay_name, %s),
                    opay_number = COALESCE(opay_number, %s),
                    bank_name = COALESCE(bank_name, %s),
                    bank_account_name = COALESCE(bank_account_name, %s),
                    bank_account_number = COALESCE(bank_account_number, %s)
                WHERE id = 1;
            """, (
                getattr(config, "OPAY_NAME", None),
                getattr(config, "OPAY_NUMBER", None),
                getattr(config, "BANK_NAME", None),
                getattr(config, "BANK_ACCOUNT_NAME", None),
                getattr(config, "BANK_ACCOUNT_NUMBER", None),
            ))

            # Crypto Options table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS crypto_payment_options (
                    id BIGSERIAL PRIMARY KEY,
                    coin TEXT NOT NULL,
                    network TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(coin, network)
                );
            """)

            # Signal Daily Limits table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS signal_daily_counts (
                    id BIGSERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    signal_date DATE NOT NULL,
                    signal_count INTEGER DEFAULT 0,
                    last_signal_at TIMESTAMPTZ,
                    UNIQUE(symbol, signal_date)
                );
            """)

              # Paper trades
cur.execute("""
    CREATE TABLE IF NOT EXISTS paper_trades (
        id BIGSERIAL PRIMARY KEY,
        signal_code TEXT UNIQUE NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        signal_score INTEGER,

        entry_price NUMERIC(30, 12) NOT NULL,
        stop_loss NUMERIC(30, 12) NOT NULL,

        tp1 NUMERIC(30, 12),
        tp2 NUMERIC(30, 12),
        tp3 NUMERIC(30, 12),

        take_profit NUMERIC(30, 12) NOT NULL,

        exit_price NUMERIC(30, 12),

        result TEXT NOT NULL DEFAULT 'open',

        tp1_hit BOOLEAN DEFAULT FALSE,
        tp2_hit BOOLEAN DEFAULT FALSE,
        breakeven_alerted BOOLEAN DEFAULT FALSE,

        r_multiple NUMERIC(10, 4),

        opened_at TIMESTAMPTZ DEFAULT NOW(),
        closed_at TIMESTAMPTZ
    );
""")

# Add new columns to existing databases
cur.execute("""
    ALTER TABLE paper_trades
    ADD COLUMN IF NOT EXISTS tp1 NUMERIC(30, 12);
""")

cur.execute("""
    ALTER TABLE paper_trades
    ADD COLUMN IF NOT EXISTS tp2 NUMERIC(30, 12);
""")

cur.execute("""
    ALTER TABLE paper_trades
    ADD COLUMN IF NOT EXISTS tp3 NUMERIC(30, 12);
""")

cur.execute("""
    ALTER TABLE paper_trades
    ADD COLUMN IF NOT EXISTS tp1_hit BOOLEAN DEFAULT FALSE;
""")

cur.execute("""
    ALTER TABLE paper_trades
    ADD COLUMN IF NOT EXISTS tp2_hit BOOLEAN DEFAULT FALSE;
""")

cur.execute("""
    ALTER TABLE paper_trades
    ADD COLUMN IF NOT EXISTS breakeven_alerted BOOLEAN DEFAULT FALSE;
""")

            # Fix: add real flag so breakeven alert is only sent once
            cur.execute("""
                ALTER TABLE paper_trades
                ADD COLUMN IF NOT EXISTS breakeven_alerted BOOLEAN DEFAULT FALSE;
            """)

            # Bot Settings
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

        conn.commit()
    print("[OK] PostgreSQL database initialized.")


# ============================================================
# BOT SETTINGS & CHANNELS
# ============================================================

def set_setting(key: str, value: str):
    if not DATABASE_URL:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bot_settings (key, value, updated_at) VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """, (key, value))
        conn.commit()


def get_setting(key: str, default: Any = None) -> Any:
    if not DATABASE_URL:
        return default
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM bot_settings WHERE key = %s", (key,))
            res = cur.fetchone()
            return res["value"] if res else default


def set_free_channel(channel_id: str):
    set_setting("free_channel_id", str(channel_id))


def get_free_channel() -> Optional[str]:
    return get_setting("free_channel_id") or os.getenv("FREE_CHANNEL_ID")


def set_vip_channel(channel_id: str):
    set_setting("vip_channel_id", str(channel_id))


def get_vip_channel() -> Optional[str]:
    return get_setting("vip_channel_id") or os.getenv("VIP_CHANNEL_ID")


def set_signals_paused(paused: bool):
    set_setting("signals_paused", "true" if paused else "false")


def are_signals_paused() -> bool:
    return str(get_setting("signals_paused", "false")).lower() == "true"
    
