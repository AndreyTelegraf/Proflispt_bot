"""Premium publish planning helpers.

Pure service layer for deciding:
- rendered post text
- target topic id
- target chat id
- whether publication goes to Baraholka

No Telegram API calls and no database writes here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from services.catalog_listing_renderer import (
    build_catalog_listing_payload_from_premium_post,
    render_catalog_listing_html,
)
from services.catalog_modes import (
    REVIEWS_SECTION_NAME,
    get_catalog_mode_slugs,
    get_catalog_section_name,
    get_catalog_topic_id,
    get_housing_section_name,
)
from services.catalog_specialized_renderers import (
    build_housing_listing_payload_from_premium_post,
    build_review_listing_html_from_premium_post,
    render_housing_listing_html,
)


@dataclass(frozen=True)
class PremiumPublishPlan:
    post_text: str
    topic_id: int | None
    publish_chat_id: int
    is_baraholka_publish: bool = False


def build_premium_post_text(post: dict) -> str:
    mode = post.get("mode")

    if mode in ("housing_wanted", "owner_real_estate"):
        payload = build_housing_listing_payload_from_premium_post(post)
        return render_housing_listing_html(payload)

    if mode == "reviews":
        return build_review_listing_html_from_premium_post(post)

    if mode in get_catalog_mode_slugs():
        payload = build_catalog_listing_payload_from_premium_post(post)
        return render_catalog_listing_html(payload)

    raise ValueError(f"Unknown mode {mode!r} for premium post #{post.get('id')}")


def _is_baraholka_publish(post: dict) -> bool:
    try:
        notes = json.loads(post.get("admin_notes") or "{}")
        return bool(notes.get("baraholka_repost_target"))
    except Exception:
        return False


def resolve_premium_publish_topic_id(post: dict, config) -> tuple[int | None, bool]:
    mode = post.get("mode")

    if mode in ("job_seeker", "job_offer"):
        from services.sections_registry import load_sections_registry
        section_name = get_catalog_section_name(mode)
        if not section_name:
            raise ValueError(f"Unknown catalog section for mode {mode!r}")
        registry = load_sections_registry()
        return int(registry.get_topic_id(section_name)), False

    if mode in ("housing_wanted", "owner_real_estate"):
        is_baraholka_publish = _is_baraholka_publish(post)
        if is_baraholka_publish:
            return int(config.BARAHOLKA_HOUSING_TOPIC_ID), True

        from services.sections_registry import load_sections_registry
        section_name = get_housing_section_name(mode)
        if not section_name:
            raise ValueError(f"Unknown housing section for mode {mode!r}")
        registry = load_sections_registry()
        return int(registry.get_topic_id(section_name)), False

    if mode == "reviews":
        from services.sections_registry import load_sections_registry
        registry = load_sections_registry()
        return int(registry.get_topic_id(REVIEWS_SECTION_NAME)), False

    return get_catalog_topic_id(mode), False


def build_premium_publish_plan(post: dict, config) -> PremiumPublishPlan:
    post_text = build_premium_post_text(post)
    topic_id, is_baraholka_publish = resolve_premium_publish_topic_id(post, config)
    publish_chat_id = (
        int(config.BARAHOLKA_CHANNEL_ID)
        if is_baraholka_publish
        else int(config.CHANNEL_ID)
    )
    return PremiumPublishPlan(
        post_text=post_text,
        topic_id=topic_id,
        publish_chat_id=publish_chat_id,
        is_baraholka_publish=is_baraholka_publish,
    )
