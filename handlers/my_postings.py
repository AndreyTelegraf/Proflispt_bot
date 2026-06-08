"""Handlers for 'My Postings' section."""

import json
import logging
from datetime import datetime
from typing import Optional

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from config import Config
from services.directory_links import directory_message_url
from services.post_identity import build_premium_post_identity_view, format_premium_post_identity_text
from services.premium_request_labels import premium_request_label
from services.admin_moderation_notice import send_admin_moderation_notice_from_post
from services.premium_repost_request import create_premium_repost_request
from services.baraholka_repost_request import create_and_notify_baraholka_repost_request
from utils import get_first_words, escape_markdown

router = Router()
logger = logging.getLogger(__name__)


def _premium_post_status_label(post: dict) -> str:
    status = post.get("status")
    if status == "published":
        return "Опубликовано"
    if status == "deleted" and post.get("expired_notified_at"):
        return "Истёк срок публикации"
    if status == "deleted":
        return "Удалено"
    if status == "superseded":
        return "Заменено новым апом"
    if status == "pending":
        payment_status = post.get("payment_status")
        if payment_status == "approved":
            return "Оплачено, ждёт публикации"
        if payment_status == "pending":
            return "Ожидает оплаты или модерации"
        return "На модерации"
    if status == "rejected":
        return "Отклонено"
    return str(status or "Неизвестно")


def _premium_post_action_rows(post: dict, post_id: int) -> list[list[InlineKeyboardButton]]:
    status = post.get("status")
    mode = post.get("mode")
    action_type = post.get("action_type")

    if status == "deleted":
        return [
            [InlineKeyboardButton(text="Опубликовать снова — €10", callback_data=f"repost_premium_{post_id}")],
        ]

    if status != "published":
        return []

    is_housing = mode in ("housing_wanted", "owner_real_estate") and action_type == "post"
    is_housing_wanted = mode == "housing_wanted" and action_type == "post"

    if is_housing_wanted:
        return [
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_premium_{post_id}")],
        ]

    if is_housing:
        return [
            [InlineKeyboardButton(text="Платный перепост в Барахолку — €10", callback_data=f"hs:baraholka_mypostings:{post_id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_premium_{post_id}")],
        ]

    return [
        [InlineKeyboardButton(text="Поднять — €10", callback_data=f"repost_premium_{post_id}")],
        [InlineKeyboardButton(text="Удалить", callback_data=f"delete_premium_{post_id}")],
    ]


@router.callback_query(F.data == "my_postings")
async def show_my_postings(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    if not user:
        await callback.message.edit_text(
            "🚫 Пользователь не найден в базе данных.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← Назад", callback_data="go:main")
            ]])
        )
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
        await callback.message.edit_text(
            "📋 Мои объявления\n\n"
            "У вас пока нет активных объявлений.\n"
            "Подайте первое объявление нажав на кнопку «Опубликовать» в главном меню:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← Назад", callback_data="go:main")
            ]])
        )
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
        await callback.message.edit_text(
            "У вас нет объявлений.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← Назад", callback_data="go:main")
            ]])
        )
        return

    index = max(0, min(index, len(ids) - 1))
    await state.update_data(my_postings_index=index)

    item_key = ids[index]
    post_type, post_id_str = item_key.split(":", 1)
    post_id = int(post_id_str)
    counter = f"({index + 1}/{len(ids)})"

    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton(text="←", callback_data="myprev"))
    if index < len(ids) - 1:
        nav_row.append(InlineKeyboardButton(text="→", callback_data="mynext"))

    post = db.get_premium_post(post_id)
    if not post:
        new_ids = [x for x in ids if x != item_key]
        new_index = max(0, min(index, len(new_ids) - 1)) if new_ids else 0
        await state.update_data(my_postings_ids=new_ids, my_postings_index=new_index)
        if not new_ids:
            await callback.message.edit_text(
                "У вас нет объявлений.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← Назад", callback_data="go:main")
                ]])
            )
            return
        return await render_my_posting(callback, state)

    status_label = _premium_post_status_label(post)
    identity = format_premium_post_identity_text(post)
    text = (
        f"📋 Мои объявления {counter}\n\n"
        f"{identity}\n"
        f"Статус: {status_label}"
    )

    action_rows = _premium_post_action_rows(post, post_id)

    inline_keyboard = []
    if nav_row:
        inline_keyboard.append(nav_row)
    inline_keyboard.extend(action_rows)
    inline_keyboard.append([InlineKeyboardButton(text="← Назад", callback_data="go:main")])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    )


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

    post = db.get_premium_post(post_id)
    if not post:
        await callback.answer("Объявление не найдено.", show_alert=True)
        return

    user = db.get_user(callback.from_user.id)
    if not user or post['user_id'] != user['id']:
        await callback.answer("Это объявление недоступно для вашего аккаунта.", show_alert=True)
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

    post = db.get_premium_post(post_id)
    if not post:
        await callback.answer("Объявление не найдено.", show_alert=True)
        return

    user = db.get_user(callback.from_user.id)
    if not user or post['user_id'] != user['id']:
        await callback.answer("Это объявление недоступно для вашего аккаунта.", show_alert=True)
        return

    view = build_premium_post_identity_view(post)
    identity = format_premium_post_identity_text(post)

    await callback.message.edit_text(
        "Удалить объявление? Это действие нельзя отменить.\n\n"
        f"{identity}\n"
        f"Статус: {view.publication_status}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"do_delete_premium_{post_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_my_postings"),
            ],
        ]),
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("do_delete_premium_"))
async def execute_delete_premium(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split("_")[3])

    post = db.get_premium_post(post_id)
    if not post:
        await callback.answer("Объявление не найдено.", show_alert=True)
        return

    user = db.get_user(callback.from_user.id)
    if not user or post['user_id'] != user['id']:
        await callback.answer("Это объявление недоступно для вашего аккаунта.", show_alert=True)
        return

    message_ids = post.get('published_message_ids') or []
    if not message_ids and post.get('message_id'):
        message_ids = [post['message_id']]

    chat_id = post.get('chat_id')
    channel_cleanup_done = not bool(chat_id and message_ids)
    undeletable_seen = False

    if chat_id:
        for mid in message_ids:
            try:
                await callback.bot.delete_message(chat_id=int(chat_id), message_id=int(mid))
                channel_cleanup_done = True
            except Exception as e:
                err = str(e).lower()
                if (
                    "message to delete not found" in err
                    or "message_id_invalid" in err
                    or "chat not found" in err
                    or "message not found" in err
                ):
                    channel_cleanup_done = True
                    continue

                if "message can't be deleted" in err:
                    undeletable_seen = True
                    logger.warning(f"Premium post message {mid} cannot be deleted, will try to mark it deleted: {e}")
                    continue

                logger.warning(f"Could not delete premium post message {mid}: {e}")

        if undeletable_seen and not channel_cleanup_done and message_ids:
            first_mid = int(message_ids[0])
            marker_text = "Объявление удалено пользователем."
            try:
                await callback.bot.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=first_mid,
                    text=marker_text,
                )
                channel_cleanup_done = True
            except Exception as text_error:
                try:
                    await callback.bot.edit_message_caption(
                        chat_id=int(chat_id),
                        message_id=first_mid,
                        caption=marker_text,
                    )
                    channel_cleanup_done = True
                except Exception as caption_error:
                    logger.warning(
                        "Could not mark premium post %s as deleted after Telegram refused deletion: text_error=%s caption_error=%s",
                        post_id,
                        text_error,
                        caption_error,
                    )

    if not channel_cleanup_done:
        await callback.answer(
            "Не удалось удалить объявление из канала. Обратитесь к администратору.",
            show_alert=True,
        )
        return

    identity = format_premium_post_identity_text(post)
    db.delete_premium_post(post_id)

    _del_data = await state.get_data()
    _del_ids = _del_data.get("my_postings_ids", [])
    _del_key = f"premium:{post_id}"
    _del_new_ids = [x for x in _del_ids if x != _del_key]
    _del_new_idx = min(_del_data.get("my_postings_index", 0), max(0, len(_del_new_ids) - 1))
    await state.update_data(my_postings_ids=_del_new_ids, my_postings_index=_del_new_idx)

    if _del_new_ids:
        await render_my_posting(callback, state)
    else:
        await callback.message.edit_text(
            "Объявление удалено.\n\n"
            f"{identity}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="В главное меню", callback_data="go:main")],
            ]),
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

    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    post = db.get_premium_post(post_id)
    if not post or post["user_id"] != user["id"]:
        await callback.answer("Объявление не найдено.", show_alert=True)
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
