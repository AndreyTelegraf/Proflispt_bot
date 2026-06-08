"""View helpers for the My Postings screen."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton


def premium_post_status_label(post: dict) -> str:
    status = post.get("status")
    if status == "published":
        return "Опубликовано"
    if status == "deleted" and post.get("expired_notified_at"):
        return "Истёк срок публикации"
    if status == "deleted":
        return "Удалено"
    if status == "superseded":
        return "Заменено новым апом"
    if status == "pending":
        payment_status = post.get("payment_status")
        if payment_status == "approved":
            return "Оплачено, ждёт публикации"
        if payment_status == "pending":
            return "Ожидает оплаты или модерации"
        return "На модерации"
    if status == "rejected":
        return "Отклонено"
    return str(status or "Неизвестно")


def premium_post_action_rows(post: dict, post_id: int) -> list[list[InlineKeyboardButton]]:
    status = post.get("status")
    mode = post.get("mode")
    action_type = post.get("action_type")

    if status == "deleted":
        return [
            [InlineKeyboardButton(text="Опубликовать снова — €10", callback_data=f"repost_premium_{post_id}")],
        ]

    if status != "published":
        return []

    is_housing = mode in ("housing_wanted", "owner_real_estate") and action_type == "post"
    is_housing_wanted = mode == "housing_wanted" and action_type == "post"

    if is_housing_wanted:
        return [
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_premium_{post_id}")],
        ]

    if is_housing:
        return [
            [InlineKeyboardButton(text="Платный перепост в Барахолку — €10", callback_data=f"hs:baraholka_mypostings:{post_id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_premium_{post_id}")],
        ]

    return [
        [InlineKeyboardButton(text="Поднять — €10", callback_data=f"repost_premium_{post_id}")],
        [InlineKeyboardButton(text="Удалить", callback_data=f"delete_premium_{post_id}")],
    ]
