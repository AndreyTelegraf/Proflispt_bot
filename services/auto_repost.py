"""Automatic promotional reposts for selected topics."""

from __future__ import annotations

import logging
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

CARGO_TOPIC_ID = 364
CARGO_PROMO_MESSAGE_ID = 35049
CARGO_REPOST_EVERY = 5
STATE_KEY = "cargo_topic_364_promo_35049"


async def maybe_auto_repost_cargo(
    bot,
    db,
    *,
    chat_id: int,
    topic_id: int | None,
    mode: str | None,
    action_type: str | None,
) -> None:
    """Copy cargo promo post after each 5 newly published cargo posts.

    First call initializes baseline as current_count - 1, so counting starts
    from the first real publication after deployment and does not backfill old posts.
    """
    if int(chat_id) != int(Config.CHANNEL_ID):
        return
    if int(topic_id or 0) != CARGO_TOPIC_ID:
        return
    if mode != "cargo_transport":
        return
    if (action_type or "post") != "post":
        return

    with db.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auto_repost_state (
                key TEXT PRIMARY KEY,
                last_count INTEGER NOT NULL DEFAULT 0,
                last_repost_message_id INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM premium_posts
            WHERE chat_id = ?
              AND topic_id = ?
              AND mode = 'cargo_transport'
              AND action_type = 'post'
              AND status = 'published'
        """, (int(chat_id), CARGO_TOPIC_ID))
        current_count = int(cursor.fetchone()["cnt"] or 0)

        cursor.execute(
            "SELECT last_count FROM auto_repost_state WHERE key = ?",
            (STATE_KEY,),
        )
        row = cursor.fetchone()

        if row is None:
            last_count = max(current_count - 1, 0)
            cursor.execute("""
                INSERT INTO auto_repost_state (key, last_count, updated_at)
                VALUES (?, ?, ?)
            """, (STATE_KEY, last_count, datetime.now()))
            conn.commit()
        else:
            last_count = int(row["last_count"] or 0)

        if current_count - last_count < CARGO_REPOST_EVERY:
            return

    copied = await bot.copy_message(
        chat_id=int(chat_id),
        from_chat_id=int(chat_id),
        message_id=CARGO_PROMO_MESSAGE_ID,
        message_thread_id=CARGO_TOPIC_ID,
    )

    copied_message_id = getattr(copied, "message_id", None)

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO auto_repost_state (
                key, last_count, last_repost_message_id, updated_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                last_count = excluded.last_count,
                last_repost_message_id = excluded.last_repost_message_id,
                updated_at = excluded.updated_at
        """, (STATE_KEY, current_count, copied_message_id, datetime.now()))
        conn.commit()

    logger.info(
        "Auto-reposted cargo promo message %s to topic %s after %s posts",
        CARGO_PROMO_MESSAGE_ID,
        CARGO_TOPIC_ID,
        current_count,
    )
