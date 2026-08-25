"""Admin-facing labels for premium moderation requests."""

from __future__ import annotations


def premium_request_label(
    *,
    action_type: str | None,
    mode: str | None,
    payment_amount: object,
    is_baraholka: bool = False,
    repost_kind: str | None = None,
) -> str:
    try:
        amount = float(payment_amount or 0)
    except (TypeError, ValueError):
        amount = 0.0

    if mode == "reviews":
        return "Бесплатный отзыв — €0"

    if mode == "talk_to_me":
        return "Бесплатная публикация «Поговори со мной» — €0"

    if is_baraholka:
        return "Платный перепост в Барахолку — €10"

    if action_type == "repost":
        if repost_kind == "republish":
            return "Повторная публикация — €10"
        return "Ап объявления — €10"

    if action_type == "post" and amount >= 20:
        return "Платный пост с медиа — €20"

    if action_type == "post":
        return "Пост на модерацию"

    return "Заявка на модерацию"
