"""Unified identity/view helpers for user-manageable posts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.catalog_modes import get_catalog_section_name
from services.directory_links import directory_message_url


_HOUSING_SECTION_NAMES = {
    "housing_wanted": "Ищу жильё",
    "owner_real_estate": "Недвижимость от хозяев",
}


@dataclass(frozen=True)
class PostIdentityView:
    """Stable display identity for a user-manageable post."""

    source: str
    post_id: int
    section_name: str
    display_title: str
    canonical_post_url: str | None
    publication_status: str


def _compact_text(value: Any, *, limit: int = 100) -> str:
    text = str(value or "").strip().replace("\n", " ")
    text = " ".join(text.split())
    if len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _first_message_id(post: dict[str, Any]) -> int | None:
    published_ids = post.get("published_message_ids") or []
    if isinstance(published_ids, list) and published_ids:
        try:
            return int(published_ids[0])
        except (TypeError, ValueError):
            pass

    message_id = post.get("message_id")
    if message_id:
        try:
            return int(message_id)
        except (TypeError, ValueError):
            return None
    return None


def build_premium_post_identity_view(post: dict[str, Any]) -> PostIdentityView:
    """Build display identity for a premium_posts row."""

    post_id = int(post["id"])
    mode = str(post.get("mode") or "")
    section_name = get_catalog_section_name(mode) or _HOUSING_SECTION_NAMES.get(mode) or mode or "Объявление"

    raw_title = post.get("name") or post.get("description") or "Объявление"
    display_title = _compact_text(raw_title, limit=80) or "Объявление"

    message_id = _first_message_id(post)
    topic_id = post.get("topic_id")
    canonical_post_url = directory_message_url(message_id, topic_id) if message_id else None

    publication_status = str(post.get("status") or "unknown")

    return PostIdentityView(
        source="premium_posts",
        post_id=post_id,
        section_name=section_name,
        display_title=display_title,
        canonical_post_url=canonical_post_url,
        publication_status=publication_status,
    )


def format_premium_post_identity_text(post: dict[str, Any]) -> str:
    """Format identity block for user-facing notifications."""

    view = build_premium_post_identity_view(post)
    lines = [
        f"Раздел: {view.section_name}",
        f"Объявление: {view.display_title}",
    ]
    if view.canonical_post_url:
        lines.append(f"Ссылка: {view.canonical_post_url}")
    return "\n".join(lines)
