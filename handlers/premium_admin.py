"""Admin handlers for premium posts."""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from services.formatting import format_premium_posting_html
from services.catalog_listing_renderer import build_catalog_listing_payload_from_premium_post, render_catalog_listing_html
from services.catalog_modes import get_catalog_mode_slugs, get_catalog_topic_id
from services.catalog_specialized_renderers import build_housing_listing_payload_from_premium_post, build_review_listing_html_from_premium_post, render_housing_listing_html
from services.directory_links import directory_message_url
from services.post_identity import format_premium_post_identity_text

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

    if post.get("action_type") == "repost":
        import json
        try:
            repost_notes = json.loads(post.get("admin_notes") or "{}")
        except Exception:
            repost_notes = {}
        old_post_id_to_supersede = repost_notes.get("old_post_id")
        repost_old_chat_id = repost_notes.get("old_chat_id")
        repost_old_message_id = repost_notes.get("old_message_id")
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
        from services.formatting import format_premium_posting_html
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

        # Format the post text
        if post.get('mode') in ('job_seeker', 'job_offer'):
            post_text = format_premium_posting_html(post)
        elif post.get('mode') in ('housing_wanted', 'owner_real_estate'):
            _hs_payload = build_housing_listing_payload_from_premium_post(post)
            post_text = render_housing_listing_html(_hs_payload)
        elif post.get('mode') == 'reviews':
            post_text = build_review_listing_html_from_premium_post(post)
        else:
            if post['mode'] in get_catalog_mode_slugs():
                _generic_payload = build_catalog_listing_payload_from_premium_post(post)
                post_text = render_catalog_listing_html(_generic_payload)
            else:
                logger.warning(
                    "Unknown mode %r for premium post #%s, falling back to format_premium_posting_html",
                    post.get('mode'), post.get('id'),
                )
                post_text = format_premium_posting_html(post)

        # Determine topic ID based on mode
        topic_id = None
        _baraholka_publish = False
        if post['mode'] == 'job_seeker':
            topic_id = Config.JOB_SEEKING_TOPIC_ID
        elif post['mode'] == 'job_offer':
            topic_id = Config.JOB_OFFERING_TOPIC_ID
        elif post['mode'] in ('housing_wanted', 'owner_real_estate'):
            import json as _json_hn
            try:
                _hn = _json_hn.loads(post.get('admin_notes') or '{}')
                _baraholka_publish = bool(_hn.get('baraholka_repost_target'))
            except Exception:
                pass
            if _baraholka_publish:
                topic_id = Config.BARAHOLKA_HOUSING_TOPIC_ID
            else:
                from services.sections_registry import load_sections_registry
                _hs_sec = {
                    'housing_wanted': 'Ищу жильё',
                    'owner_real_estate': 'Недвижимость от хозяев',
                }.get(post['mode'])
                if _hs_sec:
                    registry = load_sections_registry()
                    topic_id = int(registry.get_topic_id(_hs_sec))
        elif post['mode'] == 'reviews':
            topic_id = 12860
        else:
            topic_id = get_catalog_topic_id(post['mode'])
        publish_chat_id = Config.BARAHOLKA_CHANNEL_ID if _baraholka_publish else Config.CHANNEL_ID
        
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

        # Publish with media
        published_message = None
        published_message_ids = []
        
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
                    chat_id=publish_chat_id,
                    media=media_group,
                    message_thread_id=topic_id
                )
                published_message = published_messages[0] if published_messages else None
                published_message_ids = [m.message_id for m in published_messages]
            else:
                # Single media
                media = media_list[0]
                if media['type'] == 'photo':
                    published_message = await callback.bot.send_photo(
                        chat_id=publish_chat_id,
                        photo=media['file_id'],
                        caption=post_text,
                        message_thread_id=topic_id,
                        parse_mode="HTML"
                    )
                    published_message_ids = [published_message.message_id]
                else:
                    published_message = await callback.bot.send_video(
                        chat_id=publish_chat_id,
                        video=media['file_id'],
                        caption=post_text,
                        message_thread_id=topic_id,
                        parse_mode="HTML"
                    )
                    published_message_ids = [published_message.message_id]
        else:
            # Fallback to old format
            if post['media_type'] == 'photo':
                published_message = await callback.bot.send_photo(
                    chat_id=publish_chat_id,
                    photo=post['media_file_id'],
                    caption=post_text,
                    message_thread_id=topic_id,
                    parse_mode="HTML"
                )
                published_message_ids = [published_message.message_id]
            elif post['media_type'] == 'video':
                published_message = await callback.bot.send_video(
                    chat_id=publish_chat_id,
                    video=post['media_file_id'],
                    caption=post_text,
                    message_thread_id=topic_id,
                    parse_mode="HTML"
                )
                published_message_ids = [published_message.message_id]
            elif post.get("action_type") == "repost":
                published_message = await callback.bot.send_message(
                    chat_id=publish_chat_id,
                    text=post_text,
                    message_thread_id=topic_id,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                published_message_ids = [published_message.message_id]
            elif post.get('mode') == 'reviews':
                published_message = await callback.bot.send_message(
                    chat_id=publish_chat_id,
                    text=post_text,
                    message_thread_id=topic_id,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                published_message_ids = [published_message.message_id]

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
                        review_topic_id=12860,
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
