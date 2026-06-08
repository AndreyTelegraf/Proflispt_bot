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

def _back_to_main_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="← Назад", callback_data="go:main")
    ]])


def build_my_postings_missing_user_screen() -> tuple[str, InlineKeyboardMarkup]:
    return "🚫 Пользователь не найден в базе данных.", _back_to_main_markup()


def build_my_postings_empty_screen() -> tuple[str, InlineKeyboardMarkup]:
    return (
        "📋 Мои объявления\n\n"
        "У вас пока нет активных объявлений.\n"
        "Подайте первое объявление нажав на кнопку «Опубликовать» в главном меню:",
        _back_to_main_markup(),
    )


def build_my_postings_no_items_screen() -> tuple[str, InlineKeyboardMarkup]:
    return "У вас нет объявлений.", _back_to_main_markup()


def build_my_postings_nav_row(*, index: int, total: int) -> list[InlineKeyboardButton]:
    nav_row: list[InlineKeyboardButton] = []
    if index > 0:
        nav_row.append(InlineKeyboardButton(text="←", callback_data="myprev"))
    if index < total - 1:
        nav_row.append(InlineKeyboardButton(text="→", callback_data="mynext"))
    return nav_row

def build_premium_delete_confirm_screen(*, post: dict, post_id: int) -> tuple[str, InlineKeyboardMarkup]:
    from services.post_identity import build_premium_post_identity_view

    view = build_premium_post_identity_view(post)
    identity = format_premium_post_identity_text(post)
    text = (
        "Удалить объявление? Это действие нельзя отменить.\n\n"
        f"{identity}\n"
        f"Статус: {view.publication_status}"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"do_delete_premium_{post_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_my_postings"),
        ],
    ])
    return text, markup


def build_premium_delete_done_screen(*, post: dict) -> tuple[str, InlineKeyboardMarkup]:
    identity = format_premium_post_identity_text(post)
    return (
        f"Объявление удалено.\n\n{identity}",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="В главное меню", callback_data="go:main")],
        ]),
    )

