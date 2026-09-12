"""
Paper trading and daily signal limits for Apex Bot.
"""
from __future__ import annotations

from typing import Any, Optional

from .connection import DATABASE_URL, get_connection


def get_daily_signal_count(symbol: str) -> int:
    if not DATABASE_URL:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT signal_count
                FROM signal_daily_counts
                WHERE symbol = %s AND signal_date = CURRENT_DATE
                """,
                (symbol,),
            )
            res = cur.fetchone()
            return res["signal_count"] if res else 0


def increment_daily_signal_count(symbol: str):
    if not DATABASE_URL:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO signal_daily_counts (symbol, signal_date, signal_count, last_signal_at)
                VALUES (%s, CURRENT_DATE, 1, NOW())
                ON CONFLICT (symbol, signal_date)
                DO UPDATE SET
                    signal_count = signal_daily_counts.signal_count + 1,
                    last_signal_at = NOW()
            """, (symbol,))
        conn.commit()


def open_paper_trade(
    signal_code: str,
    symbol: str,
    direction: str,
    signal_score: int,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    tp1: float | None = None,
    tp2: float | None = None,
    tp3: float | None = None,
):
    if not DATABASE_URL:
        return None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO paper_trades (
                    signal_code,
                    symbol,
                    direction,
                    signal_score,
                    entry_price,
                    stop_loss,
                    tp1,
                    tp2,
                    tp3,
                    take_profit,
                    result
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open'
                )
                ON CONFLICT (signal_code) DO NOTHING
                RETURNING id
            """, (
                signal_code,
                symbol,
                direction,
                signal_score,
                entry_price,
                stop_loss,
                tp1,
                tp2,
                tp3,
                take_profit,
            ))

            res = cur.fetchone()

        conn.commit()

    return res["id"] if res else None


def get_open_paper_trades() -> list[dict[str, Any]]:
    if not DATABASE_URL:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM paper_trades WHERE result = 'open'")
            return cur.fetchall()


def close_paper_trade(
    trade_id: int,
    exit_price: float,
    result: str,
    r_multiple: Optional[float] = None,
):
    if not DATABASE_URL:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE paper_trades
                SET exit_price = %s, result = %s, r_multiple = %s, closed_at = NOW()
                WHERE id = %s AND result = 'open'
                RETURNING *
            """, (exit_price, result, r_multiple, trade_id))
            res = cur.fetchone()
        conn.commit()
    return res


def mark_breakeven_alerted(trade_id: int):
    if not DATABASE_URL:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE paper_trades
                SET breakeven_alerted = TRUE
                WHERE id = %s
            """, (trade_id,))
        conn.commit()


def get_recent_paper_trades(limit: int = 10) -> list[dict[str, Any]]:
    if not DATABASE_URL:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM paper_trades
                ORDER BY opened_at DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()


def get_paper_trade_stats() -> dict[str, Any]:
    if not DATABASE_URL:
        return {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "open": 0,
            "win_rate": 0.0,
            "total_r": 0.0,
        }
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE result = 'open') AS open_count,
                    COUNT(*) FILTER (
                        WHERE result = 'tp_hit'
                           OR result = 'tp1_hit'
                           OR result = 'tp2_hit'
                    ) AS wins,
                    COUNT(*) FILTER (WHERE result = 'sl_hit') AS losses,
                    COALESCE(SUM(r_multiple), 0) AS total_r
                FROM paper_trades
            """)
            row = cur.fetchone()
            if not row:
                return {
                    "total": 0,
                    "wins": 0,
                    "losses": 0,
                    "open": 0,
                    "win_rate": 0.0,
                    "total_r": 0.0,
                }

            closed = (row["wins"] or 0) + (row["losses"] or 0)
            win_rate = round((row["wins"] / closed * 100), 1) if closed > 0 else 0.0
            return {
                "total": row["total"] or 0,
                "open": row["open_count"] or 0,
                "wins": row["wins"] or 0,
                "losses": row["losses"] or 0,
                "win_rate": win_rate,
                "total_r": round(float(row["total_r"] or 0), 2),
    }
    
