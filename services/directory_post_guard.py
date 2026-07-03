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
    """Return whether a directory post may be submitted for publication.

    This covers both free publication and paid directory submission.
    """
    can_post, limit_message = db.check_premium_post_monthly_limit(user_id, mode)
    if not can_post:
        return False, limit_message

    return db.check_free_repost_guard(user_id, mode, phone_main)
