"""Telegram dispatch helpers for premium admin approval/rejection notifications."""

from __future__ import annotations

import logging

from services.premium_admin_notifications import (
    build_approval_admin_text,
    build_approval_user_notification,
    build_pin_disabled_user_notification,
    build_rejection_admin_text,
    build_rejection_user_notification,
)

logger = logging.getLogger(__name__)


async def build_message_link(bot, *, chat_id: int, message_id: int | None) -> str | None:
    if not message_id:
        return None

    try:
        chat_info = await bot.get_chat(chat_id)
        if chat_info.username:
            return f"https://t.me/{chat_info.username}/{message_id}"
    except Exception as e:
        logger.warning("Could not build premium post link: %s", e)

    return None


async def notify_user_pin_disabled(bot, *, user: dict) -> None:
    notification = build_pin_disabled_user_notification()
    await bot.send_message(
        chat_id=user["telegram_id"],
        text=notification.text,
        reply_markup=notification.reply_markup,
        disable_web_page_preview=True,
    )


async def edit_admin_pin_disabled(message, *, post_id: int) -> None:
    await message.edit_text(
        f"<b>Pin #{post_id} отклонён.</b>\n\nЗакрепление отключено.",
        parse_mode="HTML",
    )


async def notify_user_approval(
    bot,
    *,
    user: dict,
    post: dict,
    publish_chat_id: int,
    published_message,
    is_baraholka_publish: bool,
) -> None:
    message_link = await build_message_link(
        bot,
        chat_id=publish_chat_id,
        message_id=published_message.message_id if published_message else None,
    )
    notification = build_approval_user_notification(
        post,
        message_link=message_link,
        is_baraholka_publish=is_baraholka_publish,
    )
    await bot.send_message(
        chat_id=user["telegram_id"],
        text=notification.text,
        reply_markup=notification.reply_markup,
        disable_web_page_preview=True,
    )


async def edit_admin_approval(message, *, post_id: int) -> None:
    await message.edit_text(
        build_approval_admin_text(post_id),
        parse_mode="HTML",
    )


async def notify_user_rejection(bot, *, user: dict, post: dict) -> None:
    notification = build_rejection_user_notification(post)
    await bot.send_message(
        chat_id=user["telegram_id"],
        text=notification.text,
        reply_markup=notification.reply_markup,
        disable_web_page_preview=True,
    )


async def edit_admin_rejection(message, *, post_id: int) -> None:
    await message.edit_text(
        build_rejection_admin_text(post_id),
        parse_mode="HTML",
    )


async def edit_admin_repost_source_blocked(
    message,
    *,
    post_id: int,
    source_post_id: int,
) -> None:
    await message.edit_text(
        (
            f"<b>Заявка #{post_id} отклонена.</b>\n\n"
            f"Для исходного объявления #{source_post_id} запрещены ап и повторная публикация."
        ),
        parse_mode="HTML",
    )
