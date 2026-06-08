"""Admin handlers for premium posts."""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from database import db
from services.directory_links import directory_message_url
from services.premium_publish_plan import build_premium_publish_plan
from services.premium_publisher import publish_premium_post_to_telegram
from services.premium_publication_effects import apply_premium_publication_effects
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

    old_post_id_to_supersede = None
    repost_old_chat_id = None
    repost_old_message_id = None
    repost_old_topic_id = None
    repost_old_published_message_ids = []

    if post.get("action_type") == "repost":
        import json
        try:
            repost_notes = json.loads(post.get("admin_notes") or "{}")
        except Exception:
            repost_notes = {}
        old_post_id_to_supersede = repost_notes.get("old_post_id")
        repost_old_chat_id = repost_notes.get("old_chat_id")
        repost_old_message_id = repost_notes.get("old_message_id")
        repost_old_topic_id = repost_notes.get("old_topic_id")
        repost_old_published_message_ids = repost_notes.get("old_published_message_ids") or []

    pin_old_chat_id = None
    pin_old_message_id = None
    pin_old_topic_id = None

    if post.get("action_type") == "pin":
        import json
        try:
            pin_notes = json.loads(post.get("admin_notes") or "{}")
        except Exception:
            pin_notes = {}
        pin_old_chat_id = pin_notes.get("old_chat_id")
        pin_old_message_id = pin_notes.get("old_message_id")
        pin_old_topic_id = pin_notes.get("old_topic_id")

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
        
        if post.get("action_type") == "repost" and repost_old_chat_id:
            ids_to_delete = repost_old_published_message_ids if repost_old_published_message_ids else (
                [repost_old_message_id] if repost_old_message_id else []
            )
            for mid in ids_to_delete:
                try:
                    await callback.bot.delete_message(
                        chat_id=int(repost_old_chat_id),
                        message_id=int(mid),
                    )
                    logger.info(f"Deleted old repost message {mid} from chat {repost_old_chat_id}")
                except Exception as delete_error:
                    logger.warning(f"Could not delete old repost message {mid}: {delete_error}")

                    try:
                        old_link = directory_message_url(mid, repost_old_topic_id)

                        await callback.bot.send_message(
                            Config.ADMIN_IDS[0],
                            (
                                "Не удалось удалить старый пост после апа.\n\n"
                                f"Ссылка: {old_link}\n"
                                f"post_id={old_post_id_to_supersede}\n"
                                f"message_id={mid}\n"
                                f"Ошибка: {delete_error}"
                            ),
                            disable_web_page_preview=True,
                        )
                    except Exception as notify_error:
                        logger.warning(
                            f"Could not notify admin about undeleted message {mid}: {notify_error}"
                        )

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
                old_post_id_to_supersede=old_post_id_to_supersede,
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
