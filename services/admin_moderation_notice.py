"""Shared admin moderation notice helpers."""

from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services.directory_links import directory_message_url



def _requester_link(user) -> str:
    if getattr(user, "username", None):
        username = html.escape(user.username)
        return f'<a href="https://t.me/{username}">@{username}</a>'

    user_id = getattr(user, "id", "")
    first_name = html.escape(getattr(user, "first_name", None) or str(user_id))
    return f'<a href="tg://user?id={user_id}">{first_name}</a>'


def _cities_text(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(c) for c in value)
    return str(value or "")


def _compact_description(value: object, *, limit: int = 120) -> str:
    desc = html.escape(str(value or "").strip().replace("\n", " "))
    if len(desc) > limit:
        return desc[:limit].rstrip() + "…"
    return desc


def _approval_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=f"admin:approve_premium:{post_id}",
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"admin:reject_premium:{post_id}",
            ),
        ],
    ])

async def send_admin_moderation_notice(
    bot,
    *,
    admin_chat_id: int,
    post_id: int,
    preview_text: str,
    control_text: str,
    media_list: list,
) -> None:
    from aiogram.types import InputMediaPhoto, InputMediaVideo

    recipient_chat_id = int(admin_chat_id)

    group = []
    for idx, item in enumerate(media_list[:10]):
        fid = item.get("file_id")
        if not fid:
            continue

        caption = preview_text if idx == 0 else None
        if item.get("type") == "photo":
            group.append(InputMediaPhoto(media=fid, caption=caption, parse_mode="HTML"))
        elif item.get("type") == "video":
            group.append(InputMediaVideo(media=fid, caption=caption, parse_mode="HTML"))

    if group:
        try:
            await bot.send_media_group(chat_id=recipient_chat_id, media=group)
        except Exception:
            await bot.send_message(
                chat_id=recipient_chat_id,
                text=preview_text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    else:
        await bot.send_message(
            chat_id=recipient_chat_id,
            text=preview_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    await bot.send_message(
        chat_id=recipient_chat_id,
        text=control_text,
        reply_markup=_approval_keyboard(post_id),
        disable_web_page_preview=True,
    )


async def send_admin_moderation_notice_from_post(
    bot,
    *,
    post_id: int,
    source_post: dict,
    requester,
    label: str,
    admin_chat_id: int,
    include_old_post_link: bool = False,
) -> None:
    cities_safe = html.escape(_cities_text(source_post.get("cities")))
    name = html.escape(str(source_post.get("name") or ""))
    desc = _compact_description(source_post.get("description"))

    old_link = ""
    if include_old_post_link and source_post.get("message_id"):
        old_link = "\nСтарый пост: " + directory_message_url(
            source_post["message_id"],
            source_post.get("topic_id"),
        )

    admin_text = (
        f"<b>{html.escape(label)} #{post_id}</b>\n\n"
        f"<b>{name}</b> ({cities_safe})\n"
        f"{desc}"
        f"{old_link}\n\n"
        f"Пользователь: {_requester_link(requester)}"
    )

    recipient_chat_id = int(admin_chat_id)

    await bot.send_message(
        recipient_chat_id,
        admin_text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=_approval_keyboard(post_id),
    )
