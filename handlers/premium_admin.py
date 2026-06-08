"""Admin handlers for premium posts."""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import db
from services.premium_publish_plan import build_premium_publish_plan
from services.premium_publisher import publish_premium_post_to_telegram
from services.premium_publication_effects import apply_premium_publication_effects
from services.premium_repost_cleanup import build_repost_cleanup_plan, cleanup_old_repost_messages
from services.premium_admin_notifications import (
    build_approval_admin_text,
    build_approval_user_notification,
    build_pin_disabled_user_notification,
    build_rejection_admin_text,
    build_rejection_user_notification,
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
            notification = build_pin_disabled_user_notification()
            await callback.bot.send_message(
                chat_id=user['telegram_id'],
                text=notification.text,
                reply_markup=notification.reply_markup,
                disable_web_page_preview=True,
            )
            await callback.message.edit_text(
                f"<b>Pin #{post_id} отклонён.</b>\n\nЗакрепление отключено.",
                parse_mode="HTML",
            )
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

        # Notify user
        message_link = None
        if published_message:
            try:
                chat_info = await callback.bot.get_chat(publish_chat_id)
                if chat_info.username:
                    message_link = f"https://t.me/{chat_info.username}/{published_message.message_id}"
            except Exception as e:
                logger.warning(f"Could not build premium post link: {e}")

        notification = build_approval_user_notification(
            post,
            message_link=message_link,
            is_baraholka_publish=_baraholka_publish,
        )
        await callback.bot.send_message(
            chat_id=user['telegram_id'],
            text=notification.text,
            reply_markup=notification.reply_markup,
            disable_web_page_preview=True,
        )
        
        # Update admin message
        await callback.message.edit_text(
            build_approval_admin_text(post_id),
            parse_mode="HTML"
        )
        
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

    # Notify user
    notification = build_rejection_user_notification(post)
    try:
        await callback.bot.send_message(
            chat_id=user['telegram_id'],
            text=notification.text,
            reply_markup=notification.reply_markup,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Failed to notify user about rejection: {e}")
    
    # Update admin message
    await callback.message.edit_text(
        build_rejection_admin_text(post_id),
        parse_mode="HTML"
    )
    
    await callback.answer("🚫 Пост отклонен!")
