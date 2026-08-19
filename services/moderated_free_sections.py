"""Shared rules for free sections that publish only after moderation."""

from __future__ import annotations

import re
from typing import Mapping

from services.catalog_modes import TALK_TO_ME_MODE
from services.listing_validation import ValidationResult, norm_text


MODERATED_FREE_MODES = frozenset({"reviews", TALK_TO_ME_MODE})


def is_moderated_free_mode(mode: object) -> bool:
    return str(mode or "") in MODERATED_FREE_MODES


def build_talk_to_me_listing_payload(payload: Mapping[str, object]) -> dict[str, str]:
    """Convert the talk questionnaire fields to the canonical listing payload."""
    profile = norm_text(payload.get("profile_description"))
    availability = norm_text(payload.get("availability"))

    description_parts: list[str] = []
    if profile:
        description_parts.append(f"О себе: {profile}")
    if availability:
        description_parts.append(f"Общение: {availability}")

    telegram = norm_text(payload.get("telegram"))
    if telegram and not telegram.startswith("@"):
        telegram = "@" + telegram.lstrip("@")

    return {
        "geo_tags": "",
        "description": "\n\n".join(description_parts),
        "social_links": "",
        "telegram": telegram,
        "phone_main": norm_text(payload.get("phone_main")),
        "phone_whatsapp": norm_text(payload.get("phone_whatsapp")),
        "contact_name": norm_text(payload.get("name")),
    }


def validate_talk_to_me_payload(payload: Mapping[str, object]) -> ValidationResult:
    canonical = build_talk_to_me_listing_payload(payload)

    if not norm_text(payload.get("availability")):
        return ValidationResult(False, "Сессия повреждена: не заполнены условия общения.")

    telegram = canonical["telegram"]
    if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", telegram):
        return ValidationResult(False, "Сессия повреждена: не указан корректный Telegram username.")

    if not canonical["description"]:
        return ValidationResult(False, "Сессия повреждена: не заполнено описание.")

    return ValidationResult(True)
