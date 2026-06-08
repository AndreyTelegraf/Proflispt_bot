"""Premium post deletion helpers."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _published_message_ids(post: dict) -> list:
    message_ids = post.get("published_message_ids") or []
    if not message_ids and post.get("message_id"):
        message_ids = [post["message_id"]]
    return message_ids


async def _mark_as_deleted(bot, *, chat_id: int, message_id: int, post_id: int) -> bool:
    marker_text = "Объявление удалено пользователем."
    try:
        await bot.edit_message_text(
            chat_id=int(chat_id),
            message_id=int(message_id),
            text=marker_text,
        )
        return True
    except Exception as text_error:
        try:
            await bot.edit_message_caption(
                chat_id=int(chat_id),
                message_id=int(message_id),
                caption=marker_text,
            )
            return True
        except Exception as caption_error:
            logger.warning(
                "Could not mark premium post %s as deleted after Telegram refused deletion: text_error=%s caption_error=%s",
                post_id,
                text_error,
                caption_error,
            )
            return False


async def delete_premium_post_publication(bot, *, db, post: dict, post_id: int) -> bool:
    message_ids = _published_message_ids(post)
    chat_id = post.get("chat_id")
    channel_cleanup_done = not bool(chat_id and message_ids)
    undeletable_seen = False

    if chat_id:
        for mid in message_ids:
            try:
                await bot.delete_message(chat_id=int(chat_id), message_id=int(mid))
                channel_cleanup_done = True
            except Exception as e:
                err = str(e).lower()
                if (
                    "message to delete not found" in err
                    or "message_id_invalid" in err
                    or "chat not found" in err
                    or "message not found" in err
                ):
                    channel_cleanup_done = True
                    continue

                if "message can't be deleted" in err:
                    undeletable_seen = True
                    logger.warning(
                        "Premium post message %s cannot be deleted, will try to mark it deleted: %s",
                        mid,
                        e,
                    )
                    continue

                logger.warning("Could not delete premium post message %s: %s", mid, e)

        if undeletable_seen and not channel_cleanup_done and message_ids:
            channel_cleanup_done = await _mark_as_deleted(
                bot,
                chat_id=int(chat_id),
                message_id=int(message_ids[0]),
                post_id=post_id,
            )

    if not channel_cleanup_done:
        return False

    db.delete_premium_post(post_id)
    return True
