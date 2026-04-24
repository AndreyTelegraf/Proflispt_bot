# RESTAURANTS_GEO_TAG_RENDER_FIX
# RESTAURANTS_PREMIUM_ADMIN_G2_FIX
"""Admin handlers for premium posts."""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from services.formatting import format_premium_posting, format_premium_posting_html

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
    
    try:
        # Publish premium post to channel
        from services.formatting import format_premium_posting, format_premium_posting_html
        from config import Config
        
        # Format the post text
        if post.get('mode') == 'restaurants':
            import json
            from handlers.restaurants_schema import _render_html

            cities_raw = post.get('cities')
            geo_tags = ""
            if cities_raw:
                try:
                    cities = json.loads(cities_raw)
                    if isinstance(cities, list):
                        geo_tags = " ".join(
                            f"#{str(x).strip().lstrip('#').lower()}"
                            for x in cities
                            if str(x).strip()
                        )
                    elif isinstance(cities, str):
                        clean = cities.strip()
                        geo_tags = clean if clean.startswith("#") else f"#{clean.lstrip('#').lower()}"
                    else:
                        clean = str(cities_raw).strip()
                        geo_tags = clean if clean.startswith("#") else f"#{clean.lstrip('#').lower()}"
                except Exception:
                    raw = str(cities_raw).strip()
                    if raw.startswith("[") and raw.endswith("]"):
                        raw = raw[1:-1].strip()
                    raw = raw.strip().strip("'").strip('"').strip()
                    if raw:
                        parts = [p.strip().strip("'").strip('"') for p in raw.split(",") if p.strip()]
                        geo_tags = " ".join(
                            f"#{p.lstrip('#').lower()}" for p in parts if p
                        )

            import json

            review_links = ""
            if post.get("admin_notes"):
                try:
                    notes = json.loads(post["admin_notes"])
                    review_links = notes.get("review_links", "")
                except Exception:
                    pass

            restaurants_payload = {
                "geo_tags": geo_tags,
                "description": post.get("description", ""),
                "social_links": post.get("social_media", ""),
                "telegram": post.get("telegram_username", ""),
                "phone_main": post.get("phone_main", ""),
                "phone_whatsapp": post.get("phone_whatsapp", ""),
                "contact_name": post.get("name", ""),
                "review_links": review_links,
            }
            post_text = _render_html(restaurants_payload)
        else:
            post_text = format_premium_posting_html(post)
        
        # Determine topic ID based on mode
        topic_id = None
        if post['mode'] == 'job_seeker':
            topic_id = Config.JOB_SEEKING_TOPIC_ID
        elif post['mode'] == 'job_offer':
            topic_id = Config.JOB_OFFERING_TOPIC_ID
        elif post['mode'] == 'restaurants':
            from services.sections_registry import load_sections_registry
            registry = load_sections_registry()
            topic_id = int(registry.get_topic_id("Рестораны"))
        
        # Publish with media
        published_message = None
        
        # Parse media_list from DB. get_premium_post() may already return a list.
        import json
        media_list = []
        raw_media_list = post.get('media_list')
        if isinstance(raw_media_list, list):
            media_list = raw_media_list
        elif raw_media_list:
            try:
                media_list = json.loads(raw_media_list)
            except (json.JSONDecodeError, TypeError):
                media_list = []
        
        if media_list:
            # Send media group if multiple media
            if len(media_list) > 1:
                from aiogram.types import InputMediaPhoto, InputMediaVideo
                
                media_group = []
                for i, media in enumerate(media_list):
                    if i == 0:  # First media gets the caption
                        if media['type'] == 'photo':
                            media_group.append(InputMediaPhoto(
                                media=media['file_id'],
                                caption=post_text,
                                parse_mode="HTML"
                            ))
                        else:
                            media_group.append(InputMediaVideo(
                                media=media['file_id'],
                                caption=post_text,
                                parse_mode="HTML"
                            ))
                    else:
                        if media['type'] == 'photo':
                            media_group.append(InputMediaPhoto(media=media['file_id']))
                        else:
                            media_group.append(InputMediaVideo(media=media['file_id']))
                
                published_messages = await callback.bot.send_media_group(
                    chat_id=Config.CHANNEL_ID,
                    media=media_group,
                    message_thread_id=topic_id
                )
                published_message = published_messages[0] if published_messages else None
            else:
                # Single media
                media = media_list[0]
                if media['type'] == 'photo':
                    published_message = await callback.bot.send_photo(
                        chat_id=Config.CHANNEL_ID,
                        photo=media['file_id'],
                        caption=post_text,
                        message_thread_id=topic_id,
                        parse_mode="HTML"
                    )
                else:
                    published_message = await callback.bot.send_video(
                        chat_id=Config.CHANNEL_ID,
                        video=media['file_id'],
                        caption=post_text,
                        message_thread_id=topic_id,
                        parse_mode="HTML"
                    )
        else:
            # Fallback to old format
            if post['media_type'] == 'photo':
                published_message = await callback.bot.send_photo(
                    chat_id=Config.CHANNEL_ID,
                    photo=post['media_file_id'],
                    caption=post_text,
                    message_thread_id=topic_id,
                    parse_mode="HTML"
                )
            elif post['media_type'] == 'video':
                published_message = await callback.bot.send_video(
                    chat_id=Config.CHANNEL_ID,
                    video=post['media_file_id'],
                    caption=post_text,
                    message_thread_id=topic_id,
                    parse_mode="HTML"
                )
        
        # Update post with publication info
        if published_message:
            db.update_premium_post_publication(post_id, published_message.message_id, Config.CHANNEL_ID, topic_id)
            logger.info(f"Premium post #{post_id} published to channel with message_id: {published_message.message_id}")
        
        # Notify user
        message_link = None
        if published_message:
            try:
                chat_info = await callback.bot.get_chat(Config.CHANNEL_ID)
                if chat_info.username:
                    message_link = f"https://t.me/{chat_info.username}/{published_message.message_id}"
            except Exception as e:
                logger.warning(f"Could not build premium post link: {e}")

        if message_link:
            user_text = (
                "Ваше объявление с медиа опубликовано!\n"
                f"Ссылка: {message_link}\n\n"
                "Отредактировать или удалить его можно через раздел \"Мои объявления\"."
            )
        else:
            user_text = (
                "Ваше объявление с медиа опубликовано!\n\n"
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
        await callback.answer("🚫 Ошибка при одобрении поста\\.", show_alert=True)
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
    user_text = (
        "🚫 **Ваш премиум-пост отклонен :(**\n\n"
        "Возможно его содержание не соответствует требованиям Справочника или всё ещё не подтверждена оплата.\n\n"
        "Обратитесь к [администратору](https://t.me/andreytelegraf)."
    )
    
    try:
        await callback.bot.send_message(
            chat_id=user['telegram_id'],
            text=user_text,
            parse_mode="Markdown"
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
