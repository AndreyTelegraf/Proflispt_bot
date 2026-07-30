"""Directory post publication guards.

Keeps duplicate/monthly-limit checks out of transport handlers.
"""
from __future__ import annotations


async def check_duplicate_directory_post(
    db,
    *,
    user_id: int,
    mode: str,
    phone_main: str,
) -> tuple[bool, str | None]:
    """Return whether a free directory post may be submitted."""
    can_post, limit_message = db.check_premium_post_monthly_limit(user_id, mode)
    if not can_post:
        return False, limit_message

    return db.check_free_repost_guard(user_id, mode, phone_main)


async def check_active_directory_post(
    db,
    *,
    user_id: int,
    mode: str,
    phone_main: str,
) -> tuple[bool, str | None]:
    """Return whether there is no active matching directory post."""
    phone = str(phone_main or "").strip()
    if not phone:
        return True, None

    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM premium_posts
            WHERE user_id = ?
              AND mode = ?
              AND action_type = 'post'
              AND status IN ('published', 'pending')
              AND (phone_main = ? OR phone_whatsapp = ?)
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, mode, phone, phone),
        ).fetchone()

    if row is None:
        return True, None

    return False, "Такое объявление уже опубликовано или ожидает публикации."
