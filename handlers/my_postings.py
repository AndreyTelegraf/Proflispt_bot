"""Handlers for 'My Postings' section."""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from database import db
from config import Config
from services.my_postings_repost import create_and_notify_my_postings_repost
from services.my_postings_baraholka import create_and_notify_my_postings_baraholka_repost
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
from services.my_postings_state import build_user_post_keys
from services.my_postings_identity import build_premium_post_key, parse_post_key
from services.my_postings_callbacks import (
    parse_baraholka_mypostings_callback_id,
    parse_delete_premium_callback_id,
    parse_do_delete_premium_callback_id,
    parse_repost_premium_callback_id,
)
from services.my_postings_session import (
    get_my_postings_session,
    move_my_postings_index,
    remove_my_postings_key,
    set_my_postings_session,
    set_my_postings_index,
)

router = Router()


@router.callback_query(F.data == "my_postings")
async def show_my_postings(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    if not user:
        screen_text, reply_markup = build_my_postings_missing_user_screen()
        await callback.message.edit_text(screen_text, reply_markup=reply_markup)
        await callback.answer()
        return

    ids = build_user_post_keys(db, user["id"])

    if not ids:
        screen_text, reply_markup = build_my_postings_empty_screen()
        await callback.message.edit_text(screen_text, reply_markup=reply_markup)
        try:
            await callback.answer()
        except Exception:
            pass
        return

    await set_my_postings_session(state, ids, 0)
    await render_my_posting(callback, state)
    try:
        await callback.answer()
    except Exception:
        pass


async def render_my_posting(callback: CallbackQuery, state: FSMContext):
    ids, index = await get_my_postings_session(state)

    if not ids:
        screen_text, reply_markup = build_my_postings_no_items_screen()
        await callback.message.edit_text(screen_text, reply_markup=reply_markup)
        return

    index = await set_my_postings_index(state, index)

    item_key = ids[index]
    post_type, post_id = parse_post_key(item_key)
    counter = f"({index + 1}/{len(ids)})"

    nav_row = build_my_postings_nav_row(index=index, total=len(ids))

    post = db.get_premium_post(post_id)
    if not post:
        new_ids, new_index = await remove_my_postings_key(state, item_key)
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
    await move_my_postings_index(state, -1)
    await render_my_posting(callback, state)
    await callback.answer()


@router.callback_query(F.data == "mynext")
async def my_postings_next(callback: CallbackQuery, state: FSMContext):
    await move_my_postings_index(state, 1)
    await render_my_posting(callback, state)
    await callback.answer()


@router.callback_query(F.data.startswith("repost_premium_"))
async def request_repost_premium(callback: CallbackQuery):
    post_id = parse_repost_premium_callback_id(callback.data)

    post, user, error = load_owned_premium_post(db, post_id=post_id, telegram_user_id=callback.from_user.id)
    if error:
        await callback.answer(error, show_alert=True)
        return

    if post.get('status') not in ('published', 'deleted'):
        await callback.answer("Это объявление нельзя переопубликовать.", show_alert=True)
        return

    await create_and_notify_my_postings_repost(
        callback.bot,
        db=db,
        source_post=post,
        user=user,
        requester=callback.from_user,
        admin_chat_id=Config.ADMIN_IDS[0],
    )

    await callback.answer("Заявка на переопубликацию отправлена", show_alert=True)


@router.callback_query(F.data.startswith("pin_premium_"))
async def request_pin_premium(callback: CallbackQuery):
    """Reject stale pin requests after pin product removal."""
    await callback.answer("Закрепление больше недоступно.", show_alert=True)


@router.callback_query(F.data.startswith("delete_premium_"))
async def confirm_delete_premium(callback: CallbackQuery):
    post_id = parse_delete_premium_callback_id(callback.data)

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
    post_id = parse_do_delete_premium_callback_id(callback.data)

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

    _del_key = build_premium_post_key(post_id)
    _del_new_ids, _del_new_idx = await remove_my_postings_key(state, _del_key)

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
    try:
        post_id = parse_baraholka_mypostings_callback_id(callback.data)
    except ValueError:
        await callback.answer("Не удалось обработать действие. Вернитесь в «Мои объявления» и попробуйте ещё раз.", show_alert=True)
        return

    post, user, error = load_owned_premium_post(db, post_id=post_id, telegram_user_id=callback.from_user.id)
    if error:
        await callback.answer(error, show_alert=True)
        return

    ok = await create_and_notify_my_postings_baraholka_repost(
        callback.bot,
        db=db,
        source_post_id=post_id,
        user=user,
        admin_chat_id=Config.ADMIN_IDS[0],
    )
    if not ok:
        await callback.answer("Не удалось отправить заявку. Вернитесь в «Мои объявления» и попробуйте ещё раз.", show_alert=True)
        return

    await callback.message.edit_text(
        "Заявка на перепост в Барахолку отправлена на модерацию. Администратор проверит и свяжется с вами."
    )
    await callback.answer()
