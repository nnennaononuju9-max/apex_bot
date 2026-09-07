"""
Payment workflow and settings for Apex Bot.
"""
from __future__ import annotations

from typing import Any, Optional

from .connection import DATABASE_URL, get_connection


def create_payment(
    user_id: int,
    amount: float,
    currency: str,
    method: str,
    plan: str = "monthly",
    duration_days: int = 30,
    crypto_coin: Optional[str] = None,
    crypto_network: Optional[str] = None,
    crypto_wallet_address: Optional[str] = None,
    transaction_reference: Optional[str] = None,
    transaction_hash: Optional[str] = None,
    screenshot_file_id: Optional[str] = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO payments (
                    user_id, amount, currency, plan, duration_days,
                    method, crypto_coin, crypto_network, crypto_wallet_address,
                    transaction_reference, transaction_hash, screenshot_file_id, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                RETURNING id
            """, (
                user_id, amount, currency, plan, duration_days,
                method, crypto_coin, crypto_network, crypto_wallet_address,
                transaction_reference, transaction_hash, screenshot_file_id,
            ))
            payment = cur.fetchone()
        conn.commit()
    return payment["id"]


def get_pending_payments() -> list[dict[str, Any]]:
    if not DATABASE_URL:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.*, u.username, u.first_name, u.last_name
                FROM payments p
                JOIN users u ON u.telegram_id = p.user_id
                WHERE p.status = 'pending'
                ORDER BY p.created_at ASC
            """)
            return cur.fetchall()


def get_pending_payment_for_user(user_id: int) -> Optional[dict[str, Any]]:
    if not DATABASE_URL:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM payments
                WHERE user_id = %s AND status = 'pending'
                ORDER BY created_at ASC LIMIT 1
            """, (user_id,))
            return cur.fetchone()


def approve_payment(payment_id: int, admin_id: int) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE payments
                SET status = 'approved', approved_by = %s, approved_at = NOW(), updated_at = NOW()
                WHERE id = %s AND status = 'pending'
                RETURNING *
            """, (admin_id, payment_id))
            payment = cur.fetchone()
        conn.commit()
    return payment


def reject_payment(
    payment_id: int,
    admin_id: int,
    reason: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE payments
                SET status = 'rejected', rejected_by = %s, rejected_at = NOW(),
                    rejection_reason = %s, updated_at = NOW()
                WHERE id = %s AND status = 'pending'
                RETURNING *
            """, (admin_id, reason, payment_id))
            payment = cur.fetchone()
        conn.commit()
    return payment


# ============================================================
# PAYMENT SETTINGS
# ============================================================

def get_payment_settings() -> dict[str, Any]:
    if not DATABASE_URL:
        return {
            "opay_enabled": True,
            "opay_name": "Kingsley Signals",
            "opay_number": "8124930192",
            "bank_enabled": True,
            "bank_name": "Access Bank",
            "bank_account_name": "Apex Global",
            "bank_account_number": "1482930194",
            "crypto_enabled": True,
        }
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM payment_settings WHERE id = 1")
            settings = cur.fetchone()
            if settings:
                return settings
            cur.execute("INSERT INTO payment_settings (id) VALUES (1) RETURNING *")
            settings = cur.fetchone()
        conn.commit()
    return settings


def update_payment_settings(**kwargs) -> dict[str, Any]:
    current = get_payment_settings()
    for k, v in kwargs.items():
        if v is not None:
            current[k] = v

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE payment_settings
                SET opay_enabled = %s, opay_name = %s, opay_number = %s,
                    bank_enabled = %s, bank_name = %s, bank_account_name = %s,
                    bank_account_number = %s, crypto_enabled = %s, updated_at = NOW()
                WHERE id = 1 RETURNING *
            """, (
                current.get("opay_enabled", True),
                current.get("opay_name"),
                current.get("opay_number"),
                current.get("bank_enabled", True),
                current.get("bank_name"),
                current.get("bank_account_name"),
                current.get("bank_account_number"),
                current.get("crypto_enabled", True),
            ))
            res = cur.fetchone()
        conn.commit()
    return res


def get_crypto_payment_options() -> list[dict[str, Any]]:
    if not DATABASE_URL:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM crypto_payment_options WHERE enabled = TRUE ORDER BY coin, network"
            )
            return cur.fetchall()


def add_crypto_payment_option(coin: str, network: str, wallet_address: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO crypto_payment_options (coin, network, wallet_address)
                VALUES (%s, %s, %s)
                ON CONFLICT (coin, network)
                DO UPDATE SET
                    wallet_address = EXCLUDED.wallet_address,
                    enabled = TRUE,
                    updated_at = NOW()
            """, (coin.upper(), network, wallet_address))
        conn.commit()
