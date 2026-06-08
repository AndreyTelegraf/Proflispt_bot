"""Post-publication side effects for premium posts.

This service applies DB updates and secondary side effects after Telegram
publication succeeds. It does not render content and does not send the main
Telegram publication.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def apply_premium_publication_effects(
    *,
    bot,
    db,
    post: dict,
    post_id: int,
    published_message,
    published_message_ids: list[int],
    publish_chat_id: int,
    topic_id: int | None,
    old_post_id_to_supersede,
) -> None:
    db.update_premium_post_publication(
        post_id,
        published_message.message_id,
        publish_chat_id,
        topic_id,
        published_message_ids=published_message_ids,
    )
    logger.info(
        "Premium post #%s published to channel with message_id: %s",
        post_id,
        published_message.message_id,
    )

    try:
        from services.auto_repost import maybe_auto_repost_cargo
        await maybe_auto_repost_cargo(
            bot,
            db,
            chat_id=publish_chat_id,
            topic_id=topic_id,
            mode=post.get("mode"),
            action_type=post.get("action_type") or "post",
        )
    except Exception as auto_repost_error:
        logger.warning(
            "Cargo auto repost failed for premium post #%s: %s",
            post_id,
            auto_repost_error,
        )

    if post.get("mode") == "reviews":
        try:
            db.add_review_index(
                post.get("social_media", ""),
                post_id,
                published_message.message_id,
                review_topic_id=topic_id,
            )
        except Exception as e:
            logger.warning("review_index insert failed for post #%s: %s", post_id, e)

    if post.get("action_type") == "repost" and old_post_id_to_supersede:
        db.mark_premium_post_superseded(int(old_post_id_to_supersede))
