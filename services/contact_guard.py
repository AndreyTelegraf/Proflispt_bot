"""Shared validation for user-provided description text."""

from __future__ import annotations

import re

PLAIN_TEXT_ERROR = (
    "В описании допускается только текст. "
    "Медиа, ссылки и контакты можно будет добавить на следующих шагах."
)

CITY_HASHTAG_ERROR = (
    "Города и хэштеги не нужно добавлять в описание. "
    "Укажите их на шаге выбора города, через кнопку «Несколько / другой город»."
)


def _has_phone_like_contact(text: str) -> bool:
    """Detect phone-like numeric contacts while avoiding short numbers, years and prices."""
    for match in re.finditer(r"(?<!\w)(?:\+?\d[\s().-]*){9,}(?!\w)", text):
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) >= 9:
            return True
    return False


def validate_description_text(text: str) -> tuple[bool, str | None]:
    stripped = str(text or "").strip()

    if len(stripped) > 4000:
        return False, (
            "Отзыв слишком длинный. Лимит для текстового отзыва — до 4000 символов. "
            "Сократите текст и отправьте его заново."
        )

    if re.search(r"(https?://|www\.|t\.me/|telegram\.me/|wa\.me/|mailto:|tel:)", text, re.I):
        return False, "В описании допускается только текст. Ссылки можно будет добавить на следующих шагах."

    if re.search(r"[\U00010000-\U0010ffff\u2600-\u27BF\u2B00-\u2BFF\uFE0F]", text):
        return False, "В описании допускается только текст. Эмодзи использовать нельзя."

    if re.search(r"\[.*?\]\(.*?\)|<a\s+href=", text, re.I):
        return False, PLAIN_TEXT_ERROR

    if re.search(r"<\s*(b|strong)\b", text, re.I):
        return False, PLAIN_TEXT_ERROR

    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
        return False, PLAIN_TEXT_ERROR

    if re.search(r"@[A-Za-z0-9_]{5,32}\b", text):
        return False, PLAIN_TEXT_ERROR

    if _has_phone_like_contact(text):
        return False, PLAIN_TEXT_ERROR

    if re.search(r"(?<!\w)#[A-Za-zÀ-ÖØ-öø-ÿА-Яа-яЁё0-9_]{2,}", text):
        return False, CITY_HASHTAG_ERROR

    return True, None
