"""My Postings normal repost request helper."""

from __future__ import annotations

from services.admin_moderation_notice import send_admin_moderation_notice_from_post
from services.premium_repost_request import create_premium_repost_request
from services.premium_request_labels import premium_request_label
from services.premium_repost_policy import (
    REPUBLISH_KIND,
    premium_repost_denied_text,
    premium_repost_policy,
)


async def create_and_notify_my_postings_repost(
    bot,
    *,
    db,
    source_post: dict,
    user: dict,
    requester,
    admin_chat_id: int,
    repost_kind: str,
) -> int:
    new_post_id = create_premium_repost_request(
        db,
        source_post=source_post,
        user_id=user["id"],
        repost_kind=repost_kind,
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
            repost_kind=repost_kind,
        ),
        admin_chat_id=admin_chat_id,
        include_old_post_link=True,
    )
    return new_post_id

async def handle_my_postings_repost_request(
    callback,
    *,
    db,
    post: dict,
    user: dict,
    admin_chat_id: int,
) -> None:
    policy = premium_repost_policy(post)
    if not policy.allowed:
        await callback.answer(premium_repost_denied_text(policy), show_alert=True)
        return

    await create_and_notify_my_postings_repost(
        callback.bot,
        db=db,
        source_post=post,
        user=user,
        requester=callback.from_user,
        admin_chat_id=admin_chat_id,
        repost_kind=policy.kind,
    )

    if policy.kind == REPUBLISH_KIND:
        text = "Заявка на повторную публикацию отправлена"
    else:
        text = "Заявка на ап объявления отправлена"
    await callback.answer(text, show_alert=True)
