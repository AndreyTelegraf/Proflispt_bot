"""Baraholka housing repost request helpers."""

from __future__ import annotations

import json

from services.admin_moderation_notice import send_admin_moderation_notice
from services.catalog_modes import HOUSING_MODE_TO_SECTION_NAME
from services.catalog_specialized_renderers import render_housing_listing_html
from services.premium_request_labels import premium_request_label
from services.premium_repost_policy import premium_repost_denied_text, premium_repost_policy


def _baraholka_repost_payload(source_post: dict) -> dict:
    cities_raw = source_post.get("cities")
    if isinstance(cities_raw, list):
        geo_tags = " ".join(
            f"#{str(c).strip().lstrip('#').lower()}"
            for c in cities_raw
            if str(c).strip()
        )
    else:
        geo_tags = str(cities_raw or "")

    rental_term = ""
    try:
        src_notes = json.loads(source_post.get("admin_notes") or "{}")
        rental_term = src_notes.get("rental_term", "")
    except Exception:
        pass

    return {
        "geo_tags": geo_tags,
        "rental_term": rental_term,
        "description": source_post.get("description", ""),
        "social_links": source_post.get("social_media", ""),
        "telegram": source_post.get("telegram_username", ""),
        "phone_main": source_post.get("phone_main", ""),
        "phone_whatsapp": source_post.get("phone_whatsapp", ""),
        "contact_name": source_post.get("name", ""),
    }


async def notify_baraholka_repost_request(
    bot,
    *,
    post_id: int,
    source_post: dict,
    admin_chat_id: int,
) -> None:
    post_text = render_housing_listing_html(_baraholka_repost_payload(source_post))
    section_name = HOUSING_MODE_TO_SECTION_NAME.get(
        source_post.get("mode", ""),
        source_post.get("mode", ""),
    )

    await send_admin_moderation_notice(
        bot,
        admin_chat_id=admin_chat_id,
        post_id=post_id,
        preview_text=post_text,
        control_text=(
            f"[{section_name} → Барахолка] "
            f"{premium_request_label(action_type='repost', mode=source_post.get('mode'), payment_amount=10, is_baraholka=True)} "
            f"#{post_id}"
        ),
        media_list=[],
    )


async def create_and_notify_baraholka_repost_request(
    bot,
    *,
    db,
    source_post_id: int,
    user: dict,
    admin_chat_id: int,
) -> int:
    source_post = db.get_premium_post(source_post_id)
    if not source_post:
        raise ValueError(f"Source premium post #{source_post_id} not found")

    if source_post["user_id"] != user["id"]:
        raise ValueError(f"Source premium post #{source_post_id} does not belong to user #{user['id']}")

    repost_policy = premium_repost_policy(source_post)
    if not repost_policy.allowed:
        raise ValueError(premium_repost_denied_text(repost_policy))

    repost_id = db.create_baraholka_housing_repost_from_post(source_post_id, user["id"])
    await notify_baraholka_repost_request(
        bot,
        post_id=repost_id,
        source_post=source_post,
        admin_chat_id=admin_chat_id,
    )
    return repost_id
