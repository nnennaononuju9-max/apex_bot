"""
VIP subscription system for Apex Bot.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .connection import DATABASE_URL, get_connection


def get_active_vip(telegram_id: int) -> Optional[dict[str, Any]]:
    if not DATABASE_URL:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM vip_subscriptions
                WHERE user_id = %s
                  AND status = 'active'
                  AND expiry_date > NOW()
                ORDER BY expiry_date DESC
                LIMIT 1
            """, (telegram_id,))
            return cur.fetchone()


def is_vip(telegram_id: int) -> bool:
    return get_active_vip(telegram_id) is not None


def activate_vip(
    telegram_id: int,
    duration_days: int,
    payment_id: Optional[int] = None,
    plan: str = "monthly",
):
    """
    Activates or extends VIP status.
    - plan='weekly'  -> VIP badge
    - plan='monthly' -> PREMIUM VIP badge
    - plan='trial'   -> 24h trial
    """
    if not DATABASE_URL:
        return

    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM vip_subscriptions
                WHERE user_id = %s
                  AND status = 'active'
                  AND expiry_date > NOW()
                ORDER BY expiry_date DESC
                LIMIT 1
                FOR UPDATE
            """, (telegram_id,))
            existing = cur.fetchone()

            if existing:
                new_expiry = existing["expiry_date"] + timedelta(days=duration_days)
                cur.execute("""
                    UPDATE vip_subscriptions
                    SET expiry_date = %s,
                        payment_id = COALESCE(%s, payment_id),
                        plan = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (new_expiry, payment_id, plan, existing["id"]))
            else:
                expiry = now + timedelta(days=duration_days)
                cur.execute("""
                    INSERT INTO vip_subscriptions (
                        user_id, start_date, expiry_date, status, payment_id, plan
                    )
                    VALUES (%s, %s, %s, 'active', %s, %s)
                """, (telegram_id, now, expiry, payment_id, plan))
        conn.commit()


def expire_old_vip() -> int:
    if not DATABASE_URL:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE vip_subscriptions
                SET status = 'expired', updated_at = NOW()
                WHERE status = 'active' AND expiry_date <= NOW()
            """)
            affected = cur.rowcount
        conn.commit()
    return affected


def claim_vip_trial(telegram_id: int) -> tuple[bool, str]:
    if not DATABASE_URL:
        return True, "VIP Trial activated (24 Hours)!"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM vip_subscriptions
                WHERE user_id = %s AND plan = 'trial'
                LIMIT 1
            """, (telegram_id,))
            if cur.fetchone():
                return False, "You have already claimed your one-time 24-Hour Free VIP Trial."

    activate_vip(telegram_id, duration_days=1, plan="trial")
    return True, "Your 24-Hour VIP Trial has been activated successfully!"
