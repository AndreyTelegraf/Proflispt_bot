"""Shared listing validation helpers.

This module is intentionally handler-neutral. It should not import aiogram,
database, handlers, or section-specific flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


SKIP_VALUES = {"", "нет", "no", "none", "-", "—"}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    message: str = ""


def norm_text(value: object) -> str:
    if value is None:
        return ""
    clean = str(value).strip()
    if clean.lower() in SKIP_VALUES:
        return ""
    return clean


def is_valid_pt_mobile(value: object) -> bool:
    phone = norm_text(value)
    if len(phone) != 13:
        return False
    if not phone.startswith("+351"):
        return False
    if not phone[4:].isdigit():
        return False
    return phone[4:6] in {"91", "92", "93", "96"}


def validate_required_payload(
    payload: Mapping[str, object],
    required_fields: Mapping[str, str],
) -> ValidationResult:
    missing = [
        label
        for key, label in required_fields.items()
        if not norm_text(payload.get(key))
    ]
    if missing:
        return ValidationResult(
            ok=False,
            message="Сессия повреждена: не заполнено поле " + ", ".join(missing) + ".",
        )
    return ValidationResult(ok=True)


def validate_publish_payload(
    payload: Mapping[str, object],
    required_fields: Mapping[str, str],
    *,
    require_pt_mobile: bool = True,
) -> ValidationResult:
    if require_pt_mobile and not is_valid_pt_mobile(payload.get("phone_main")):
        return ValidationResult(
            ok=False,
            message="Сессия повреждена: не указан корректный телефон.",
        )

    return validate_required_payload(payload, required_fields)


STANDARD_LISTING_REQUIRED_FIELDS = {
    "geo_tags": "город",
    "description": "описание",
    "telegram": "Telegram",
    "contact_name": "контактное имя",
}
