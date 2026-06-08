"""Access helpers for My Postings handlers."""

from __future__ import annotations


def load_owned_premium_post(db, *, post_id: int, telegram_user_id: int) -> tuple[dict | None, dict | None, str | None]:
    post = db.get_premium_post(post_id)
    if not post:
        return None, None, "Объявление не найдено."

    user = db.get_user(telegram_user_id)
    if not user or post["user_id"] != user["id"]:
        return post, user, "Это объявление недоступно для вашего аккаунта."

    return post, user, None
