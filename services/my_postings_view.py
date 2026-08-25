"""View helpers for the My Postings screen."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton

from services.catalog_modes import TALK_TO_ME_MODE
from services.premium_repost_policy import REPUBLISH_KIND, premium_repost_policy


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
        if post.get("mode") == TALK_TO_ME_MODE:
            return "На модерации"
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

    if mode == TALK_TO_ME_MODE:
        if status == "published":
            return [
                [InlineKeyboardButton(text="Удалить", callback_data=f"delete_premium_{post_id}")],
            ]
        return []

    repost_policy = premium_repost_policy(post)

    if status == "deleted":
        if repost_policy.allowed and repost_policy.kind == REPUBLISH_KIND:
            return [
                [InlineKeyboardButton(text="Опубликовать снова — €10", callback_data=f"repost_premium_{post_id}")],
            ]
        return []

    if status != "published":
        return []

    is_housing = mode in ("housing_wanted", "owner_real_estate") and action_type == "post"
    is_housing_wanted = mode == "housing_wanted" and action_type == "post"

    if is_housing_wanted:
        return [
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_premium_{post_id}")],
        ]

    if is_housing:
        rows = []
        if repost_policy.allowed:
            rows.append(
                [InlineKeyboardButton(text="Платный перепост в Барахолку — €10", callback_data=f"hs:baraholka_mypostings:{post_id}")]
            )
        rows.append([InlineKeyboardButton(text="Удалить", callback_data=f"delete_premium_{post_id}")])
        return rows

    rows = []
    if repost_policy.allowed:
        rows.append([InlineKeyboardButton(text="Поднять — €10", callback_data=f"repost_premium_{post_id}")])
    rows.append([InlineKeyboardButton(text="Удалить", callback_data=f"delete_premium_{post_id}")])
    return rows
