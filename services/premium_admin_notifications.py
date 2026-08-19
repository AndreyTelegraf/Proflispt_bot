"""Notification text/keyboards for premium admin moderation."""

from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services.post_identity import format_premium_post_identity_text


@dataclass(frozen=True)
class PremiumAdminNotification:
    text: str
    reply_markup: InlineKeyboardMarkup
    parse_mode: str | None = None


def _main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="В главное меню", callback_data="go:main")]
    ])


def _back_to_my_postings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад", callback_data="back_to_my_postings")]
    ])


def build_pin_disabled_user_notification() -> PremiumAdminNotification:
    return PremiumAdminNotification(
        text="Закрепление больше недоступно. Если вы уже оплатили закрепление, обратитесь к администратору.",
        reply_markup=_main_menu_kb(),
    )


def build_approval_user_notification(
    post: dict,
    *,
    message_link: str | None,
    is_baraholka_publish: bool,
) -> PremiumAdminNotification:
    identity = format_premium_post_identity_text(post)

    if post.get("action_type") == "repost" and is_baraholka_publish:
        return PremiumAdminNotification(
            text=(
                f"{identity}\n\n"
                "Опубликовано в Барахолке.\n\n"
                "Удалить его можно через администратора @baraholka_pt"
            ),
            reply_markup=_main_menu_kb(),
        )

    if post.get("action_type") == "repost":
        return PremiumAdminNotification(
            text=(
                f"{identity}\n\n"
                "Теперь это самое новое объявление в разделе.\n\n"
                "Удалить его можно через раздел \"Мои объявления\"."
            ),
            reply_markup=_back_to_my_postings_kb(),
        )

    if post.get("mode") == "reviews":
        return PremiumAdminNotification(
            text=f"Ваш отзыв опубликован!\nСсылка: {message_link}" if message_link else "Ваш отзыв опубликован!",
            reply_markup=_main_menu_kb(),
        )

    if post.get("mode") == "talk_to_me":
        return PremiumAdminNotification(
            text=(
                f"Ваша публикация в разделе «Поговори со мной» опубликована!\nСсылка: {message_link}"
                if message_link
                else "Ваша публикация в разделе «Поговори со мной» опубликована!"
            ),
            reply_markup=_main_menu_kb(),
        )

    return PremiumAdminNotification(
        text=(
            f"{identity}\n\n"
            "Объявление с медиа опубликовано.\n\n"
            "Отредактировать или удалить его можно через раздел \"Мои объявления\"."
        ),
        reply_markup=_main_menu_kb(),
    )


def build_rejection_user_notification(post: dict) -> PremiumAdminNotification:
    if post.get("mode") == "reviews":
        text = (
            "Ваш отзыв отклонён.\n\n"
            "Возможно содержание не соответствует требованиям Справочника.\n\n"
            "Обратитесь к администратору: https://t.me/kak_odin"
        )
    elif post.get("mode") == "talk_to_me":
        text = (
            "Ваша публикация в разделе «Поговори со мной» отклонена.\n\n"
            "Возможно, содержание не соответствует требованиям Справочника.\n\n"
            "Обратитесь к администратору: https://t.me/kak_odin"
        )
    else:
        text = (
            "Ваш премиум-пост отклонен.\n\n"
            "Возможно его содержание не соответствует требованиям Справочника или всё ещё не подтверждена оплата.\n\n"
            "Обратитесь к администратору: https://t.me/kak_odin"
        )

    return PremiumAdminNotification(
        text=text,
        reply_markup=_main_menu_kb(),
    )


def build_approval_admin_text(post_id: int) -> str:
    return (
        f"<b>Премиум-пост #{post_id} одобрен и опубликован!</b>\n\n"
        "Пользователь уведомлен об одобрении.\n"
        "Пост опубликован в канале."
    )


def build_rejection_admin_text(post_id: int) -> str:
    return (
        f"<b>Премиум-пост #{post_id} отклонен.</b>\n\n"
        "Пользователь уведомлен об отклонении."
    )
