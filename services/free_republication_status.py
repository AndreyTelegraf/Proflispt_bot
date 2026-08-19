"""User-facing status of free repeat publication availability."""

from __future__ import annotations

from datetime import datetime


_RUSSIAN_MONTHS = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def format_russian_date(value: datetime) -> str:
    return f"{value.day} {_RUSSIAN_MONTHS[value.month]} {value.year} года"


def free_republication_status_text(db, post: dict) -> str | None:
    """Return availability text for an original free directory publication."""
    if post.get("action_type") != "post":
        return None

    if float(post.get("payment_amount") or 0) != 0:
        return None

    mode = str(post.get("mode") or "")
    if not mode or mode in {"reviews", "talk_to_me"}:
        return None

    phone = str(
        post.get("phone_main")
        or post.get("phone_whatsapp")
        or ""
    ).strip()
    if not phone:
        return None

    duplicate_allowed, duplicate_available_at = (
        db.get_free_republication_availability(
            int(post["user_id"]),
            mode,
            phone,
        )
    )
    monthly_allowed, monthly_available_at, _monthly_message = (
        db.get_premium_post_monthly_limit_availability(
            int(post["user_id"]),
            mode,
        )
    )

    if duplicate_allowed and monthly_allowed:
        return "Бесплатная повторная публикация доступна сейчас."

    blockers = [
        value
        for value in (
            duplicate_available_at,
            monthly_available_at,
        )
        if value is not None
    ]

    if not blockers:
        return "Бесплатная повторная публикация сейчас недоступна."

    available_at = max(blockers)
    return (
        "Бесплатная повторная публикация будет доступна "
        f"{format_russian_date(available_at)}."
    )
