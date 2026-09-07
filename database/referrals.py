"""
Referral helpers for Apex Bot (personal rewards only).
"""
from __future__ import annotations

from typing import Any, Optional

from .connection import DATABASE_URL, get_connection


def create_referral(referrer_id: int, referred_user_id: int) -> bool:
    if referrer_id == referred_user_id or not DATABASE_URL:
        return False
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO referrals (referrer_id, referred_user_id)
                VALUES (%s, %s)
                ON CONFLICT (referred_user_id) DO NOTHING
                RETURNING id
            """, (referrer_id, referred_user_id))
            res = cur.fetchone()
        conn.commit()
    return res is not None


def get_referral_count(referrer_id: int) -> int:
    if not DATABASE_URL:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total FROM referrals WHERE referrer_id = %s",
                (referrer_id,),
            )
            return cur.fetchone()["total"]


def get_referral_by_referred_user(referred_user_id: int) -> Optional[dict[str, Any]]:
    if not DATABASE_URL:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM referrals WHERE referred_user_id = %s",
                (referred_user_id,),
            )
            return cur.fetchone()


def get_rewarded_referral_count(referrer_id: int) -> int:
    if not DATABASE_URL:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM referrals
                WHERE referrer_id = %s AND reward_granted = TRUE
                """,
                (referrer_id,),
            )
            return cur.fetchone()["total"]


def mark_referral_rewarded(referral_id: int, reward_days: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE referrals
                SET reward_days = %s, reward_granted = TRUE, rewarded_at = NOW()
                WHERE id = %s
                RETURNING *
            """, (reward_days, referral_id))
            res = cur.fetchone()
        conn.commit()
    return res
