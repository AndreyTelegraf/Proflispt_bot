"""Automatic promotional reposts for selected topics."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from config import Config

logger = logging.getLogger(__name__)

CARGO_TOPIC_ID = 364
CARGO_PROMO_MESSAGE_ID = 35049
CARGO_REPOST_EVERY = 5
CARGO_REPOST_DELAY_SECONDS = 25 * 60
AUTO_REPOST_POLL_SECONDS = 60
STATE_KEY = "cargo_topic_364_promo_35049"

_scheduler_task: asyncio.Task | None = None


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _ensure_auto_repost_state_schema(db) -> None:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auto_repost_state (
                key TEXT PRIMARY KEY,
                last_count INTEGER NOT NULL DEFAULT 0,
                last_repost_message_id INTEGER,
                pending_due_at TEXT,
                pending_trigger_count INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("PRAGMA table_info(auto_repost_state)")
        columns = {row["name"] for row in cursor.fetchall()}

        if "last_repost_message_id" not in columns:
            cursor.execute("ALTER TABLE auto_repost_state ADD COLUMN last_repost_message_id INTEGER")
        if "pending_due_at" not in columns:
            cursor.execute("ALTER TABLE auto_repost_state ADD COLUMN pending_due_at TEXT")
        if "pending_trigger_count" not in columns:
            cursor.execute("ALTER TABLE auto_repost_state ADD COLUMN pending_trigger_count INTEGER")
        if "updated_at" not in columns:
            cursor.execute("ALTER TABLE auto_repost_state ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        conn.commit()


async def _copy_cargo_promo(bot, db, *, chat_id: int, trigger_count: int) -> None:
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
                key,
                last_count,
                last_repost_message_id,
                pending_due_at,
                pending_trigger_count,
                updated_at
            ) VALUES (?, ?, ?, NULL, NULL, ?)
            ON CONFLICT(key) DO UPDATE SET
                last_count = excluded.last_count,
                last_repost_message_id = excluded.last_repost_message_id,
                pending_due_at = NULL,
                pending_trigger_count = NULL,
                updated_at = excluded.updated_at
        """, (STATE_KEY, int(trigger_count), copied_message_id, _now_iso()))
        conn.commit()

    logger.info(
        "Auto-reposted cargo promo message %s to topic %s; trigger_count=%s",
        CARGO_PROMO_MESSAGE_ID,
        CARGO_TOPIC_ID,
        trigger_count,
    )


async def process_due_auto_reposts(bot, db) -> None:
    _ensure_auto_repost_state_schema(db)

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pending_due_at, pending_trigger_count
            FROM auto_repost_state
            WHERE key = ?
        """, (STATE_KEY,))
        row = cursor.fetchone()

    if not row:
        return

    due_at = _parse_dt(row["pending_due_at"])
    trigger_count = row["pending_trigger_count"]

    if not due_at or trigger_count is None:
        return

    if datetime.utcnow() < due_at:
        return

    await _copy_cargo_promo(
        bot,
        db,
        chat_id=int(Config.CHANNEL_ID),
        trigger_count=int(trigger_count),
    )


async def _auto_repost_scheduler_loop(bot, db) -> None:
    while True:
        try:
            await process_due_auto_reposts(bot, db)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Auto repost scheduler error: %s", exc)

        await asyncio.sleep(AUTO_REPOST_POLL_SECONDS)


async def start_auto_repost_scheduler(bot, db) -> None:
    global _scheduler_task

    if _scheduler_task and not _scheduler_task.done():
        return

    _ensure_auto_repost_state_schema(db)
    _scheduler_task = asyncio.create_task(_auto_repost_scheduler_loop(bot, db))
    logger.info("Auto repost scheduler started")


async def maybe_auto_repost_cargo(
    bot,
    db,
    *,
    chat_id: int,
    topic_id: int | None,
    mode: str | None,
    action_type: str | None,
) -> None:
    """Persistently schedule cargo promo copy 25 minutes after each 5 newly published cargo posts.

    First matching publication initializes baseline as current_count - 1, so counting
    starts from the first real publication after deployment and does not backfill old posts.
    """
    if int(chat_id) != int(Config.CHANNEL_ID):
        return
    if int(topic_id or 0) != CARGO_TOPIC_ID:
        return
    if mode != "cargo_transport":
        return
    if (action_type or "post") != "post":
        return

    _ensure_auto_repost_state_schema(db)

    with db.get_connection() as conn:
        cursor = conn.cursor()

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

        cursor.execute("""
            SELECT last_count, pending_due_at
            FROM auto_repost_state
            WHERE key = ?
        """, (STATE_KEY,))
        row = cursor.fetchone()

        if row is None:
            last_count = max(current_count - 1, 0)
            cursor.execute("""
                INSERT INTO auto_repost_state (
                    key,
                    last_count,
                    pending_due_at,
                    pending_trigger_count,
                    updated_at
                ) VALUES (?, ?, NULL, NULL, ?)
            """, (STATE_KEY, last_count, _now_iso()))
            conn.commit()
        else:
            last_count = int(row["last_count"] or 0)
            if row["pending_due_at"]:
                logger.info(
                    "Cargo auto repost already pending; current_count=%s",
                    current_count,
                )
                return

        if current_count - last_count < CARGO_REPOST_EVERY:
            return

        due_at = datetime.utcnow() + timedelta(seconds=CARGO_REPOST_DELAY_SECONDS)
        cursor.execute("""
            INSERT INTO auto_repost_state (
                key,
                last_count,
                pending_due_at,
                pending_trigger_count,
                updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                pending_due_at = excluded.pending_due_at,
                pending_trigger_count = excluded.pending_trigger_count,
                updated_at = excluded.updated_at
        """, (
            STATE_KEY,
            last_count,
            due_at.isoformat(timespec="seconds"),
            current_count,
            _now_iso(),
        ))
        conn.commit()

    logger.info(
        "Persistently scheduled cargo promo message %s to topic %s at %s UTC; trigger_count=%s",
        CARGO_PROMO_MESSAGE_ID,
        CARGO_TOPIC_ID,
        due_at.isoformat(timespec="seconds"),
        current_count,
    )
