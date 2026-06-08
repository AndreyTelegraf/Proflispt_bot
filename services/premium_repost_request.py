"""Premium repost request creation helpers."""

from __future__ import annotations

import json


def build_repost_admin_notes(source_post: dict) -> str:
    return json.dumps({
        "old_post_id": source_post["id"],
        "old_message_id": source_post.get("message_id"),
        "old_chat_id": source_post.get("chat_id"),
        "old_topic_id": source_post.get("topic_id"),
        "old_published_message_ids": source_post.get("published_message_ids") or [],
    })


def create_premium_repost_request(db, *, source_post: dict, user_id: int) -> int:
    return db.create_premium_post(
        user_id=user_id,
        mode=source_post.get("mode"),
        cities=json.dumps(source_post["cities"]),
        description=source_post["description"],
        social_media=source_post.get("social_media"),
        telegram_username=source_post.get("telegram_username"),
        phone_main=source_post.get("phone_main"),
        phone_whatsapp=source_post.get("phone_whatsapp"),
        name=source_post.get("name"),
        media_file_id=source_post.get("media_file_id"),
        media_type=source_post.get("media_type"),
        media_list=source_post.get("media_list") or [],
        payment_amount=10.00,
        action_type="repost",
        admin_notes=build_repost_admin_notes(source_post),
    )
