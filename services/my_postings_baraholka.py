"""My Postings Baraholka repost helper."""

from __future__ import annotations

import logging

from services.baraholka_repost_request import create_and_notify_baraholka_repost_request

logger = logging.getLogger(__name__)


async def create_and_notify_my_postings_baraholka_repost(
    bot,
    *,
    db,
    source_post_id: int,
    user: dict,
    admin_chat_id: int,
) -> bool:
    try:
        await create_and_notify_baraholka_repost_request(
            bot,
            db=db,
            source_post_id=source_post_id,
            user=user,
            admin_chat_id=admin_chat_id,
        )
        return True
    except Exception as e:
        logger.exception("Baraholka my_postings repost failed: %s", e)
        return False

async def handle_my_postings_baraholka_request(
    callback,
    *,
    db,
    source_post_id: int,
    user: dict,
    admin_chat_id: int,
) -> None:
    ok = await create_and_notify_my_postings_baraholka_repost(
        callback.bot,
        db=db,
        source_post_id=source_post_id,
        user=user,
        admin_chat_id=admin_chat_id,
    )
    if not ok:
        await callback.answer(
            "Не удалось отправить заявку. Вернитесь в «Мои объявления» и попробуйте ещё раз.",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "Заявка на перепост в Барахолку отправлена на модерацию. Администратор проверит и свяжется с вами."
    )
    await callback.answer()

