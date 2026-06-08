"""My Postings normal repost request helper."""

from __future__ import annotations

from services.admin_moderation_notice import send_admin_moderation_notice_from_post
from services.premium_repost_request import create_premium_repost_request
from services.premium_request_labels import premium_request_label


async def create_and_notify_my_postings_repost(
    bot,
    *,
    db,
    source_post: dict,
    user: dict,
    requester,
    admin_chat_id: int,
) -> int:
    new_post_id = create_premium_repost_request(
        db,
        source_post=source_post,
        user_id=user["id"],
    )

    await send_admin_moderation_notice_from_post(
        bot,
        post_id=new_post_id,
        source_post=source_post,
        requester=requester,
        label=premium_request_label(
            action_type="repost",
            mode=source_post.get("mode"),
            payment_amount=10,
        ),
        admin_chat_id=admin_chat_id,
        include_old_post_link=True,
    )
    return new_post_id
