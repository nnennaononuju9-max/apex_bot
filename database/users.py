"""
User management for Apex Bot.
"""
from __future__ import annotations

from typing import Any, Optional

from .connection import DATABASE_URL, get_connection


def create_or_update_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    referred_by: Optional[int] = None,
) -> bool:
    """Returns True if this was a brand-new user (first-ever /start)."""
    if not DATABASE_URL:
        return False

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (
                    telegram_id, username, first_name, last_name, referred_by
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_seen_at = NOW(),
                    updated_at = NOW()
                RETURNING (xmax = 0) AS is_new
            """, (telegram_id, username, first_name, last_name, referred_by))
            row = cur.fetchone()
        conn.commit()
    return bool(row and row["is_new"])


def get_user(telegram_id: int) -> Optional[dict[str, Any]]:
    if not DATABASE_URL:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
            return cur.fetchone()


def get_all_user_ids() -> list[int]:
    if not DATABASE_URL:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT telegram_id FROM users WHERE is_blocked = FALSE")
            rows = cur.fetchall()
            return [r["telegram_id"] for r in rows]
