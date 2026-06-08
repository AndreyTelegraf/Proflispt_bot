"""Admin handlers for premium posts."""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import db
from services.premium_publish_plan import build_premium_publish_plan
from services.premium_publisher import publish_premium_post_to_telegram
from services.premium_publication_effects import apply_premium_publication_effects
from services.premium_repost_cleanup import build_repost_cleanup_plan, cleanup_old_repost_messages
from services.premium_admin_dispatcher import (
    edit_admin_approval,
    edit_admin_pin_disabled,
    edit_admin_rejection,
    notify_user_approval,
    notify_user_pin_disabled,
    notify_user_rejection,
)

logger = logging.getLogger(__name__)

router = Router()

@router.callback_query(F.data.startswith("admin:approve_premium:"))
async def admin_approve_premium(callback: CallbackQuery):
    """Admin approves premium post payment."""
    # Check if user is admin
    if callback.from_user.id != 336224597:
        await callback.answer("🚫 У вас нет прав для выполнения этой команды.", show_alert=True)
        return
    
    post_id = int(callback.data.split(":")[2])
    
    # Get premium post
    post = db.get_premium_post(post_id)
    if not post:
        await callback.answer("🚫 Пост не найден.", show_alert=True)
        return
    
    # Get user's telegram_id
    user = db.get_user_by_id(post['user_id'])
    if not user:
        await callback.answer("🚫 Пользователь не найден.", show_alert=True)
        return
    
    # Approve premium post
    db.approve_premium_post(post_id, callback.from_user.id)

    repost_cleanup_plan = build_repost_cleanup_plan(post)

    try:
        # Publish premium post to channel
        from config import Config
        from datetime import datetime, timedelta

        if post.get("action_type") == "pin":
            db.reject_premium_post(post_id, callback.from_user.id, "Pin product disabled")
            await notify_user_pin_disabled(callback.bot, user=user)
            await edit_admin_pin_disabled(callback.message, post_id=post_id)
            await callback.answer("Закрепление отключено.", show_alert=True)
            return

        publish_plan = build_premium_publish_plan(post, Config)
        post_text = publish_plan.post_text
        topic_id = publish_plan.topic_id
        publish_chat_id = publish_plan.publish_chat_id
        _baraholka_publish = publish_plan.is_baraholka_publish
        
        await cleanup_old_repost_messages(callback.bot, Config, repost_cleanup_plan)

        publish_result = await publish_premium_post_to_telegram(
            callback.bot,
            post,
            post_text=post_text,
            publish_chat_id=publish_chat_id,
            topic_id=topic_id,
        )
        published_message = publish_result.message
        published_message_ids = publish_result.message_ids

        # Update post with publication info
        if published_message:
            await apply_premium_publication_effects(
                bot=callback.bot,
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
            callback.bot,
            user=user,
            post=post,
            publish_chat_id=publish_chat_id,
            published_message=published_message,
            is_baraholka_publish=_baraholka_publish,
        )
        await edit_admin_approval(callback.message, post_id=post_id)
        
    except Exception as e:
        logger.error(f"Failed to approve premium post: {e}")
        await callback.answer("Не удалось одобрить пост. Проверьте лог и попробуйте ещё раз.", show_alert=True)
        return
    
    await callback.answer("✅ Пост одобрен!")

@router.callback_query(F.data.startswith("admin:reject_premium:"))
async def admin_reject_premium(callback: CallbackQuery):
    """Admin rejects premium post."""
    # Check if user is admin
    if callback.from_user.id != 336224597:
        await callback.answer("🚫 У вас нет прав для выполнения этой команды.", show_alert=True)
        return
    
    post_id = int(callback.data.split(":")[2])
    
    # Get premium post
    post = db.get_premium_post(post_id)
    if not post:
        await callback.answer("🚫 Пост не найден.", show_alert=True)
        return
    
    # Get user's telegram_id
    user = db.get_user_by_id(post['user_id'])
    if not user:
        await callback.answer("🚫 Пользователь не найден.", show_alert=True)
        return
    
    # Reject premium post
    db.reject_premium_post(post_id, callback.from_user.id, "Отклонено администратором")

    try:
        await notify_user_rejection(callback.bot, user=user, post=post)
    except Exception as e:
        logger.error(f"Failed to notify user about rejection: {e}")
    
    await edit_admin_rejection(callback.message, post_id=post_id)
    
    await callback.answer("🚫 Пост отклонен!")
