"""Delete action helper for My Postings handlers."""

from services.my_postings_identity import build_premium_post_key
from services.my_postings_session import remove_my_postings_key
from services.my_postings_render import build_premium_delete_done_screen
from services.premium_post_delete import delete_premium_post_publication


async def handle_my_postings_delete_request(
    callback,
    state,
    *,
    db,
    post: dict,
    post_id: int,
    render_next,
) -> None:
    deleted = await delete_premium_post_publication(
        callback.bot,
        db=db,
        post=post,
        post_id=post_id,
    )
    if not deleted:
        await callback.answer(
            "Не удалось удалить объявление из канала. Обратитесь к администратору.",
            show_alert=True,
        )
        return

    post_key = build_premium_post_key(post_id)
    new_ids, _new_index = await remove_my_postings_key(state, post_key)

    if new_ids:
        await render_next(callback, state)
    else:
        screen_text, reply_markup = build_premium_delete_done_screen(post=post)
        await callback.message.edit_text(
            screen_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    await callback.answer()
