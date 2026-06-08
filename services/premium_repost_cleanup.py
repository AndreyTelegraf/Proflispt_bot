"""Old repost cleanup helpers for premium admin approval."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from services.directory_links import directory_message_url

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RepostCleanupPlan:
    old_post_id_to_supersede: object | None
    old_chat_id: object | None
    old_message_id: object | None
    old_topic_id: object | None
    old_published_message_ids: list


def build_repost_cleanup_plan(post: dict) -> RepostCleanupPlan:
    if post.get("action_type") != "repost":
        return RepostCleanupPlan(None, None, None, None, [])

    try:
        notes = json.loads(post.get("admin_notes") or "{}")
    except Exception:
        notes = {}

    return RepostCleanupPlan(
        old_post_id_to_supersede=notes.get("old_post_id"),
        old_chat_id=notes.get("old_chat_id"),
        old_message_id=notes.get("old_message_id"),
        old_topic_id=notes.get("old_topic_id"),
        old_published_message_ids=notes.get("old_published_message_ids") or [],
    )


async def cleanup_old_repost_messages(bot, config, plan: RepostCleanupPlan) -> None:
    if not plan.old_chat_id:
        return

    ids_to_delete = (
        plan.old_published_message_ids
        if plan.old_published_message_ids
        else ([plan.old_message_id] if plan.old_message_id else [])
    )

    for mid in ids_to_delete:
        try:
            await bot.delete_message(
                chat_id=int(plan.old_chat_id),
                message_id=int(mid),
            )
            logger.info("Deleted old repost message %s from chat %s", mid, plan.old_chat_id)
        except Exception as delete_error:
            logger.warning("Could not delete old repost message %s: %s", mid, delete_error)

            try:
                old_link = directory_message_url(mid, plan.old_topic_id)
                await bot.send_message(
                    config.ADMIN_IDS[0],
                    (
                        "Не удалось удалить старый пост после апа.\n\n"
                        f"Ссылка: {old_link}\n"
                        f"post_id={plan.old_post_id_to_supersede}\n"
                        f"message_id={mid}\n"
                        f"Ошибка: {delete_error}"
                    ),
                    disable_web_page_preview=True,
                )
            except Exception as notify_error:
                logger.warning(
                    "Could not notify admin about undeleted message %s: %s",
                    mid,
                    notify_error,
                )
