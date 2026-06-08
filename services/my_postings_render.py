"""Render helpers for the My Postings screen."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services.post_identity import format_premium_post_identity_text
from services.my_postings_view import premium_post_action_rows, premium_post_status_label


def build_my_posting_screen(
    *,
    post: dict,
    post_id: int,
    counter: str,
    nav_row: list[InlineKeyboardButton],
) -> tuple[str, InlineKeyboardMarkup]:
    status_label = premium_post_status_label(post)
    identity = format_premium_post_identity_text(post)
    text = (
        f"📋 Мои объявления {counter}\n\n"
        f"{identity}\n"
        f"Статус: {status_label}"
    )

    inline_keyboard = []
    if nav_row:
        inline_keyboard.append(nav_row)
    inline_keyboard.extend(premium_post_action_rows(post, post_id))
    inline_keyboard.append([InlineKeyboardButton(text="← Назад", callback_data="go:main")])

    return text, InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
