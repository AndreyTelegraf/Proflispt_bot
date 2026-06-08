"""Telegram publication helpers for premium posts.

This service only sends already-rendered post content to Telegram and returns
publication message metadata. It does not write to DB and does not perform
post-publication side effects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from aiogram.types import InputMediaPhoto, InputMediaVideo


@dataclass(frozen=True)
class PremiumPublishResult:
    message: object | None
    message_ids: list[int]


def extract_premium_media_list(post: dict) -> list[dict]:
    raw_media_list = post.get("media_list")
    if isinstance(raw_media_list, list):
        return raw_media_list
    if raw_media_list:
        try:
            parsed = json.loads(raw_media_list)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


async def publish_premium_post_to_telegram(
    bot,
    post: dict,
    *,
    post_text: str,
    publish_chat_id: int,
    topic_id: int | None,
) -> PremiumPublishResult:
    media_list = extract_premium_media_list(post)

    if media_list:
        if len(media_list) > 1:
            media_group = []
            for i, media in enumerate(media_list):
                if i == 0:
                    if media["type"] == "photo":
                        media_group.append(InputMediaPhoto(
                            media=media["file_id"],
                            caption=post_text,
                            parse_mode="HTML",
                        ))
                    else:
                        media_group.append(InputMediaVideo(
                            media=media["file_id"],
                            caption=post_text,
                            parse_mode="HTML",
                        ))
                else:
                    if media["type"] == "photo":
                        media_group.append(InputMediaPhoto(media=media["file_id"]))
                    else:
                        media_group.append(InputMediaVideo(media=media["file_id"]))

            published_messages = await bot.send_media_group(
                chat_id=publish_chat_id,
                media=media_group,
                message_thread_id=topic_id,
            )
            message = published_messages[0] if published_messages else None
            return PremiumPublishResult(
                message=message,
                message_ids=[m.message_id for m in published_messages],
            )

        media = media_list[0]
        if media["type"] == "photo":
            message = await bot.send_photo(
                chat_id=publish_chat_id,
                photo=media["file_id"],
                caption=post_text,
                message_thread_id=topic_id,
                parse_mode="HTML",
            )
        else:
            message = await bot.send_video(
                chat_id=publish_chat_id,
                video=media["file_id"],
                caption=post_text,
                message_thread_id=topic_id,
                parse_mode="HTML",
            )
        return PremiumPublishResult(message=message, message_ids=[message.message_id])

    if post.get("media_type") == "photo":
        message = await bot.send_photo(
            chat_id=publish_chat_id,
            photo=post["media_file_id"],
            caption=post_text,
            message_thread_id=topic_id,
            parse_mode="HTML",
        )
        return PremiumPublishResult(message=message, message_ids=[message.message_id])

    if post.get("media_type") == "video":
        message = await bot.send_video(
            chat_id=publish_chat_id,
            video=post["media_file_id"],
            caption=post_text,
            message_thread_id=topic_id,
            parse_mode="HTML",
        )
        return PremiumPublishResult(message=message, message_ids=[message.message_id])

    if post.get("action_type") == "repost" or post.get("mode") == "reviews":
        message = await bot.send_message(
            chat_id=publish_chat_id,
            text=post_text,
            message_thread_id=topic_id,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return PremiumPublishResult(message=message, message_ids=[message.message_id])

    return PremiumPublishResult(message=None, message_ids=[])
