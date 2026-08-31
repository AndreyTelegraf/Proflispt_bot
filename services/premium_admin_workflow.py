"""Premium admin approval/rejection workflows.

This layer contains business workflow orchestration for premium moderation.
Aiogram handlers should stay as transport glue only.
"""

from __future__ import annotations

import logging

from config import Config
from database import db
from services.premium_admin_dispatcher import (
    edit_admin_approval,
    edit_admin_pin_disabled,
    edit_admin_rejection,
    edit_admin_repost_source_blocked,
    notify_user_approval,
    notify_user_pin_disabled,
    notify_user_rejection,
)
from services.premium_publication_effects import apply_premium_publication_effects
from services.premium_publish_plan import build_premium_publish_plan
from services.premium_publisher import publish_premium_post_to_telegram
from services.premium_repost_cleanup import build_repost_cleanup_plan, cleanup_old_repost_messages
from services.premium_repost_policy import validate_premium_repost_request

logger = logging.getLogger(__name__)


class PremiumAdminWorkflowError(Exception):
    """Raised when premium admin workflow cannot be completed."""


def load_premium_post_and_user(post_id: int) -> tuple[dict | None, dict | None]:
    post = db.get_premium_post(post_id)
    if not post:
        return None, None

    user = db.get_user_by_id(post["user_id"])
    if not user:
        return post, None

    return post, user


async def approve_premium_request(
    *,
    bot,
    admin_message,
    post: dict,
    user: dict,
    post_id: int,
    admin_id: int,
) -> str:
    if post.get("action_type") == "repost":
        try:
            validate_premium_repost_request(db, post)
        except ValueError as exc:
            logger.error("Repost request #%s is no longer eligible: %s", post_id, exc)
            raise PremiumAdminWorkflowError(str(exc)) from exc

    db.approve_premium_post(post_id, admin_id)

    repost_cleanup_plan = build_repost_cleanup_plan(post)

    try:
        if post.get("action_type") == "pin":
            db.reject_premium_post(post_id, admin_id, "Pin product disabled")
            await notify_user_pin_disabled(bot, user=user)
            await edit_admin_pin_disabled(admin_message, post_id=post_id)
            return "pin_disabled"

        publish_plan = build_premium_publish_plan(post, Config)
        post_text = publish_plan.post_text
        topic_id = publish_plan.topic_id
        publish_chat_id = publish_plan.publish_chat_id
        is_baraholka_publish = publish_plan.is_baraholka_publish

        await cleanup_old_repost_messages(bot, Config, repost_cleanup_plan)

        publish_result = await publish_premium_post_to_telegram(
            bot,
            post,
            post_text=post_text,
            publish_chat_id=publish_chat_id,
            topic_id=topic_id,
        )
        published_message = publish_result.message
        published_message_ids = publish_result.message_ids

        if published_message:
            await apply_premium_publication_effects(
                bot=bot,
                db=db,
                post=post,
                post_id=post_id,
                published_message=published_message,
                published_message_ids=published_message_ids,
                publish_chat_id=publish_chat_id,
                topic_id=topic_id,
                old_post_id_to_supersede=repost_cleanup_plan.old_post_id_to_supersede,
            )

        await notify_user_approval(
            bot,
            user=user,
            post=post,
            publish_chat_id=publish_chat_id,
            topic_id=topic_id,
            published_message=published_message,
            is_baraholka_publish=is_baraholka_publish,
        )
        await edit_admin_approval(admin_message, post_id=post_id)
        return "approved"

    except Exception as e:
        logger.error("Failed to approve premium post: %s", e)
        raise PremiumAdminWorkflowError(str(e)) from e


async def reject_premium_request(
    *,
    bot,
    admin_message,
    post: dict,
    user: dict,
    post_id: int,
    admin_id: int,
) -> None:
    db.reject_premium_post(post_id, admin_id, "Отклонено администратором")

    try:
        await notify_user_rejection(bot, user=user, post=post)
    except Exception as e:
        logger.error("Failed to notify user about rejection: %s", e)

    await edit_admin_rejection(admin_message, post_id=post_id)


async def block_repost_source_request(
    *,
    bot,
    admin_message,
    post: dict,
    user: dict,
    post_id: int,
    admin_id: int,
) -> int:
    if post.get("action_type") != "repost":
        raise PremiumAdminWorkflowError(f"Post #{post_id} is not a repost request")

    reason = f"Заблокировано администратором из заявки #{post_id}"
    try:
        source_post_id = db.block_repost_source_from_request(
            post_id,
            admin_id,
            reason,
        )
    except Exception as exc:
        logger.error("Failed to block repost source for request #%s: %s", post_id, exc)
        raise PremiumAdminWorkflowError(str(exc)) from exc

    try:
        await notify_user_rejection(bot, user=user, post=post)
    except Exception as exc:
        logger.error("Failed to notify user about blocked repost source: %s", exc)

    await edit_admin_repost_source_blocked(
        admin_message,
        post_id=post_id,
        source_post_id=source_post_id,
    )
    return source_post_id
