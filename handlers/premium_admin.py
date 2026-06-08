"""Admin handlers for premium posts."""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from services.directory_links import directory_message_url
from services.post_identity import format_premium_post_identity_text
from services.premium_publish_plan import build_premium_publish_plan
from services.premium_publisher import publish_premium_post_to_telegram

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
            await callback.bot.send_message(
                chat_id=user['telegram_id'],
                text="Закрепление больше недоступно. Если вы уже оплатили закрепление, обратитесь к администратору.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="В главное меню", callback_data="go:main")]
                ]),
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
            db.update_premium_post_publication(post_id, published_message.message_id, publish_chat_id, topic_id, published_message_ids=published_message_ids)
            logger.info(f"Premium post #{post_id} published to channel with message_id: {published_message.message_id}")

            try:
                from services.auto_repost import maybe_auto_repost_cargo
                await maybe_auto_repost_cargo(
                    callback.bot,
                    db,
                    chat_id=publish_chat_id,
                    topic_id=topic_id,
                    mode=post.get("mode"),
                    action_type=post.get("action_type") or "post",
                )
            except Exception as auto_repost_error:
                logger.warning("Cargo auto repost failed for premium post #%s: %s", post_id, auto_repost_error)

            if post.get('mode') == 'reviews':
                try:
                    db.add_review_index(
                        post.get("social_media", ""),
                        post_id,
                        published_message.message_id,
                        review_topic_id=topic_id,
                    )
                except Exception as e:
                    logger.warning(f"review_index insert failed for post #{post_id}: {e}")

            if post.get("action_type") == "repost" and old_post_id_to_supersede:
                db.mark_premium_post_superseded(int(old_post_id_to_supersede))

        # Notify user
        message_link = None
        if published_message:
            try:
                chat_info = await callback.bot.get_chat(publish_chat_id)
                if chat_info.username:
                    message_link = f"https://t.me/{chat_info.username}/{published_message.message_id}"
            except Exception as e:
                logger.warning(f"Could not build premium post link: {e}")

        identity = format_premium_post_identity_text(post)

        if post.get("action_type") == "repost" and _baraholka_publish:
            user_text = (
                f"{identity}\n\n"
                "Опубликовано в Барахолке.\n\n"
                "Удалить его можно через администратора @baraholka_pt"
            )
            main_menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="В главное меню", callback_data="go:main")]
            ])
        elif post.get("action_type") == "repost":
            user_text = (
                f"{identity}\n\n"
                "Теперь это самое новое объявление в разделе.\n\n"
                "Удалить его можно через раздел \"Мои объявления\"."
            )
            main_menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="← Назад", callback_data="back_to_my_postings")]
            ])
        elif post.get('mode') == 'reviews':
            if message_link:
                user_text = f"Ваш отзыв опубликован!\nСсылка: {message_link}"
            else:
                user_text = "Ваш отзыв опубликован!"
            main_menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="В главное меню", callback_data="go:main")]
            ])
        else:
            user_text = (
                f"{identity}\n\n"
                "Объявление с медиа опубликовано.\n\n"
                "Отредактировать или удалить его можно через раздел \"Мои объявления\"."
            )
            main_menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="В главное меню", callback_data="go:main")]
            ])

        await callback.bot.send_message(
            chat_id=user['telegram_id'],
            text=user_text,
            reply_markup=main_menu_keyboard,
            disable_web_page_preview=True,
        )
        
        # Update admin message
        await callback.message.edit_text(
            f"✅ <b>Премиум-пост #{post_id} одобрен и опубликован!</b>\n\n"
            f"Пользователь уведомлен об одобрении.\n"
            f"Пост опубликован в канале.",
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
    if post.get('mode') == 'reviews':
        user_text = (
            "🚫 **Ваш отзыв отклонён.**\n\n"
            "Возможно содержание не соответствует требованиям Справочника.\n\n"
            "Обратитесь к [администратору](https://t.me/andreytelegraf)."
        )
    else:
        user_text = (
            "🚫 **Ваш премиум-пост отклонен :(**\n\n"
            "Возможно его содержание не соответствует требованиям Справочника или всё ещё не подтверждена оплата.\n\n"
            "Обратитесь к [администратору](https://t.me/andreytelegraf)."
        )
    
    main_menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="В главное меню", callback_data="go:main")]
    ])
    try:
        await callback.bot.send_message(
            chat_id=user['telegram_id'],
            text=user_text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Failed to notify user about rejection: {e}")
    
    # Update admin message
    await callback.message.edit_text(
        f"🚫 **Премиум-пост #{post_id} отклонен.**\n\n"
        f"Пользователь уведомлен об отклонении.",
        parse_mode="Markdown"
    )
    
    await callback.answer("🚫 Пост отклонен!")
