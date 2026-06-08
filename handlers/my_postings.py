"""Handlers for 'My Postings' section."""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database import db
from config import Config
from services.premium_request_labels import premium_request_label
from services.admin_moderation_notice import send_admin_moderation_notice_from_post
from services.premium_repost_request import create_premium_repost_request
from services.baraholka_repost_request import create_and_notify_baraholka_repost_request
from services.premium_post_delete import delete_premium_post_publication
from services.my_postings_render import (
    build_my_posting_screen,
    build_my_postings_empty_screen,
    build_my_postings_missing_user_screen,
    build_my_postings_nav_row,
    build_my_postings_no_items_screen,
    build_premium_delete_confirm_screen,
    build_premium_delete_done_screen,
)
from services.my_postings_access import load_owned_premium_post

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "my_postings")
async def show_my_postings(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    if not user:
        screen_text, reply_markup = build_my_postings_missing_user_screen()
        await callback.message.edit_text(screen_text, reply_markup=reply_markup)
        await callback.answer()
        return

    user_id_db = user['id']
    manageable_posts = db.get_user_manageable_premium_posts(user_id_db)
    all_posts = sorted(
        manageable_posts,
        key=lambda p: p.get('created_at') or '',
        reverse=True,
    )

    ids = [f"premium:{p['id']}" for p in all_posts]

    if not ids:
        screen_text, reply_markup = build_my_postings_empty_screen()
        await callback.message.edit_text(screen_text, reply_markup=reply_markup)
        try:
            await callback.answer()
        except Exception:
            pass
        return

    await state.update_data(my_postings_ids=ids, my_postings_index=0)
    await render_my_posting(callback, state)
    try:
        await callback.answer()
    except Exception:
        pass


async def render_my_posting(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ids = data.get("my_postings_ids", [])
    index = data.get("my_postings_index", 0)

    if not ids:
        screen_text, reply_markup = build_my_postings_no_items_screen()
        await callback.message.edit_text(screen_text, reply_markup=reply_markup)
        return

    index = max(0, min(index, len(ids) - 1))
    await state.update_data(my_postings_index=index)

    item_key = ids[index]
    post_type, post_id_str = item_key.split(":", 1)
    post_id = int(post_id_str)
    counter = f"({index + 1}/{len(ids)})"

    nav_row = build_my_postings_nav_row(index=index, total=len(ids))

    post = db.get_premium_post(post_id)
    if not post:
        new_ids = [x for x in ids if x != item_key]
        new_index = max(0, min(index, len(new_ids) - 1)) if new_ids else 0
        await state.update_data(my_postings_ids=new_ids, my_postings_index=new_index)
        if not new_ids:
            screen_text, reply_markup = build_my_postings_no_items_screen()
            await callback.message.edit_text(screen_text, reply_markup=reply_markup)
            return
        return await render_my_posting(callback, state)

    screen_text, reply_markup = build_my_posting_screen(
        post=post,
        post_id=post_id,
        counter=counter,
        nav_row=nav_row,
    )

    await callback.message.edit_text(screen_text, reply_markup=reply_markup)


@router.callback_query(F.data == "back_to_my_postings")
async def back_to_my_postings(callback: CallbackQuery, state: FSMContext):
    """Go back to my postings list."""
    await show_my_postings(callback, state)
    try:
        await callback.answer()
    except:
        pass


@router.callback_query(F.data == "myprev")
async def my_postings_prev(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = max(0, data.get("my_postings_index", 0) - 1)
    await state.update_data(my_postings_index=index)
    await render_my_posting(callback, state)
    await callback.answer()


@router.callback_query(F.data == "mynext")
async def my_postings_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ids = data.get("my_postings_ids", [])
    index = min(len(ids) - 1, data.get("my_postings_index", 0) + 1)
    await state.update_data(my_postings_index=index)
    await render_my_posting(callback, state)
    await callback.answer()


@router.callback_query(F.data.startswith("repost_premium_"))
async def request_repost_premium(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[2])

    post, user, error = load_owned_premium_post(db, post_id=post_id, telegram_user_id=callback.from_user.id)
    if error:
        await callback.answer(error, show_alert=True)
        return

    if post.get('status') not in ('published', 'deleted'):
        await callback.answer("Это объявление нельзя переопубликовать.", show_alert=True)
        return

    new_post_id = create_premium_repost_request(
        db,
        source_post=post,
        user_id=user['id'],
    )

    try:
        await send_admin_moderation_notice_from_post(
            callback.bot,
            post_id=new_post_id,
            source_post=post,
            requester=callback.from_user,
            label=premium_request_label(
                action_type='repost',
                mode=post.get('mode'),
                payment_amount=10,
            ),
            admin_chat_id=Config.ADMIN_IDS[0],
            include_old_post_link=True,
        )
    except Exception:
        pass

    await callback.answer("Заявка на переопубликацию отправлена", show_alert=True)


@router.callback_query(F.data.startswith("pin_premium_"))
async def request_pin_premium(callback: CallbackQuery):
    """Reject stale pin requests after pin product removal."""
    await callback.answer("Закрепление больше недоступно.", show_alert=True)


@router.callback_query(F.data.startswith("delete_premium_"))
async def confirm_delete_premium(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[2])

    post, user, error = load_owned_premium_post(db, post_id=post_id, telegram_user_id=callback.from_user.id)
    if error:
        await callback.answer(error, show_alert=True)
        return

    screen_text, reply_markup = build_premium_delete_confirm_screen(post=post, post_id=post_id)
    await callback.message.edit_text(
        screen_text,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("do_delete_premium_"))
async def execute_delete_premium(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split("_")[3])

    post, user, error = load_owned_premium_post(db, post_id=post_id, telegram_user_id=callback.from_user.id)
    if error:
        await callback.answer(error, show_alert=True)
        return

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

    _del_data = await state.get_data()
    _del_ids = _del_data.get("my_postings_ids", [])
    _del_key = f"premium:{post_id}"
    _del_new_ids = [x for x in _del_ids if x != _del_key]
    _del_new_idx = min(_del_data.get("my_postings_index", 0), max(0, len(_del_new_ids) - 1))
    await state.update_data(my_postings_ids=_del_new_ids, my_postings_index=_del_new_idx)

    if _del_new_ids:
        await render_my_posting(callback, state)
    else:
        screen_text, reply_markup = build_premium_delete_done_screen(post=post)
        await callback.message.edit_text(
            screen_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("hs:baraholka_mypostings:"))
async def hs_baraholka_mypostings(callback: CallbackQuery):
    import logging
    logger = logging.getLogger(__name__)

    raw_id = callback.data.split(":", 2)[2]
    try:
        post_id = int(raw_id)
    except ValueError:
        await callback.answer("Не удалось обработать действие. Вернитесь в «Мои объявления» и попробуйте ещё раз.", show_alert=True)
        return

    post, user, error = load_owned_premium_post(db, post_id=post_id, telegram_user_id=callback.from_user.id)
    if error:
        await callback.answer(error, show_alert=True)
        return

    try:
        await create_and_notify_baraholka_repost_request(
            callback.bot,
            db=db,
            source_post_id=post_id,
            user=user,
            admin_chat_id=Config.ADMIN_IDS[0],
        )
    except Exception as e:
        logger.exception("Baraholka my_postings repost failed: %s", e)
        await callback.answer("Не удалось отправить заявку. Вернитесь в «Мои объявления» и попробуйте ещё раз.", show_alert=True)
        return

    await callback.message.edit_text(
        "Заявка на перепост в Барахолку отправлена на модерацию. Администратор проверит и свяжется с вами."
    )
    await callback.answer()
