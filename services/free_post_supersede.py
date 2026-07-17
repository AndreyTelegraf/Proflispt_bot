"""Cleanup superseded free directory publications."""

from __future__ import annotations

import json
import logging

from config import Config
from services.directory_links import directory_message_url

logger = logging.getLogger(__name__)


def _message_ids(post: dict) -> list[int]:
    raw = post.get("published_message_ids")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raw = []

    ids = list(raw or [])
    if not ids and post.get("message_id"):
        ids = [post["message_id"]]

    return [int(value) for value in ids if value]


def find_previous_free_publications(
    db,
    *,
    user_id: int,
    mode: str,
    phone_main: str,
    new_post_id: int,
) -> list[dict]:
    """Return older active free posts matching user, mode, and phone."""
    phone = str(phone_main or "").strip()
    if not phone:
        return []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id,
                chat_id,
                topic_id,
                message_id,
                published_message_ids
            FROM premium_posts
            WHERE user_id = ?
              AND mode = ?
              AND id != ?
              AND action_type = 'post'
              AND status = 'published'
              AND payment_status = 'approved'
              AND CAST(COALESCE(payment_amount, 0) AS REAL) = 0
              AND (phone_main = ? OR phone_whatsapp = ?)
              AND (
                  datetime(created_at) < (
                      SELECT datetime(created_at)
                      FROM premium_posts
                      WHERE id = ?
                  )
                  OR (
                      datetime(created_at) = (
                          SELECT datetime(created_at)
                          FROM premium_posts
                          WHERE id = ?
                      )
                      AND id < ?
                  )
              )
            ORDER BY datetime(created_at) ASC, id ASC
            """,
            (
                user_id,
                mode,
                new_post_id,
                phone,
                phone,
                new_post_id,
                new_post_id,
                new_post_id,
            ),
        )
        return [dict(row) for row in cursor.fetchall()]


async def supersede_previous_free_publications(
    bot,
    db,
    *,
    user_id: int,
    mode: str,
    phone_main: str,
    new_post_id: int,
) -> int:
    """Delete older Telegram publications and mark cleaned rows superseded."""
    previous_posts = find_previous_free_publications(
        db,
        user_id=user_id,
        mode=mode,
        phone_main=phone_main,
        new_post_id=new_post_id,
    )

    superseded_count = 0

    for post in previous_posts:
        chat_id = post.get("chat_id")
        message_ids = _message_ids(post)
        cleanup_done = not bool(chat_id and message_ids)

        if chat_id and message_ids:
            cleanup_done = True

            for message_id in message_ids:
                try:
                    await bot.delete_message(
                        chat_id=int(chat_id),
                        message_id=int(message_id),
                    )
                except Exception as error:
                    error_text = str(error).lower()

                    if (
                        "message to delete not found" in error_text
                        or "message_id_invalid" in error_text
                        or "message not found" in error_text
                        or "chat not found" in error_text
                    ):
                        continue

                    cleanup_done = False
                    logger.warning(
                        "Could not remove superseded free post message "
                        "post_id=%s chat_id=%s message_id=%s error=%s",
                        post["id"],
                        chat_id,
                        message_id,
                        error,
                    )

                    try:
                        old_link = directory_message_url(
                            message_id,
                            post.get("topic_id"),
                        )
                        await bot.send_message(
                            Config.ADMIN_IDS[0],
                            (
                                "Не удалось удалить старую бесплатную "
                                "публикацию после размещения новой версии.\n\n"
                                f"Ссылка: {old_link}\n"
                                f"post_id={post['id']}\n"
                                f"new_post_id={new_post_id}\n"
                                f"message_id={message_id}\n"
                                f"Ошибка: {error}"
                            ),
                            disable_web_page_preview=True,
                        )
                    except Exception as notify_error:
                        logger.warning(
                            "Could not notify admin about undeleted "
                            "free post message %s: %s",
                            message_id,
                            notify_error,
                        )

        if not cleanup_done:
            continue

        if db.mark_premium_post_superseded(int(post["id"])):
            superseded_count += 1
            logger.info(
                "Superseded previous free directory post "
                "old_post_id=%s new_post_id=%s",
                post["id"],
                new_post_id,
            )

    return superseded_count
