"""Reviews FSM flow — content moderation without payment."""
from __future__ import annotations

import json
import logging
import re

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import db
from keyboards.main import get_main_menu
from services.catalog_specialized_renderers import render_review_listing_html as _rv_render_html
from services.catalog_limits import TELEGRAM_MEDIA_CAPTION_LIMIT, REVIEW_TEXT_MAX_LEN, REVIEW_TEXT_WITH_MEDIA_MAX_LEN
from services.catalog_modes import REVIEWS_SECTION_NAME

logger = logging.getLogger(__name__)
router = Router()

ADMIN_CHAT_ID = 336224597

# FSM states
RV_INPUT      = "rv_input"
RV_GEO_CUSTOM = "rv_geo_custom"
RV_MEDIA      = "rv_media"
RV_CONFIRM    = "rv_confirm"

_STEP_RESIDENCY   = 0
_STEP_GEO         = 1
_STEP_CONTACTS    = 2
_STEP_DESCRIPTION = 3

_GEO_OPTIONS = [
    ("lisboa",  "Lisboa"),
    ("porto",   "Porto"),
    ("coimbra", "Coimbra"),
    ("braga",   "Braga"),
    ("faro",    "Faro"),
    ("sintra",  "Sintra"),
    ("cascais", "Cascais"),
    ("leiria",  "Leiria"),
    ("setubal", "Setúbal"),
    ("online",  "Онлайн"),
    ("custom",  "Несколько / другой город"),
]

_PROMPTS = [
    "Вы находитесь в Португалии?",
    "Выберите город или регион:",
    "Укажите @username специалиста, которому вы хотите оставить отзыв:",
    "Напишите отзыв:\n\n"
    "- Что именно делали: услуга или работа\n"
    "- Что было хорошо\n"
    "- Что было плохо, если было\n"
    "- Итог: рекомендуете или нет\n\n"
    "Важно:\n"
    "- Только текст, без ссылок и эмодзи\n"
    f"- Длинные отзывы до {REVIEW_TEXT_MAX_LEN} символов доступны без медиа\n"
    f"- С фото/видео отзыв должен быть до {REVIEW_TEXT_WITH_MEDIA_MAX_LEN} символов",
]



def _normalize_geo(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return json.dumps([], ensure_ascii=False)
    parts = [c.strip().lstrip("#").lower() for c in raw.replace(",", " ").split() if c.strip()]
    return json.dumps(parts, ensure_ascii=False)


def _validate_description_text(text: str) -> tuple[bool, str | None]:
    from services.contact_guard import validate_description_text
    return validate_description_text(text)


# ── keyboards ──────────────────────────────────────────────────────────────────

def _residency_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="Да", callback_data="rv:residency:yes"))
    b.add(InlineKeyboardButton(text="Нет", callback_data="rv:residency:no"))
    b.adjust(2)
    return b.as_markup()


def _geo_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for val, label in _GEO_OPTIONS:
        b.add(InlineKeyboardButton(text=label, callback_data=f"rv:geo:{val}"))
    b.add(InlineKeyboardButton(text="← Назад", callback_data="rv:back"))
    b.adjust(3, 3, 3, 1, 1)
    return b.as_markup()


def _back_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="← Назад", callback_data="rv:back"))
    return b.as_markup()


def _confirm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="Отправить без медиа", callback_data="rv:submit_no_media"))
    b.add(InlineKeyboardButton(text="Добавить фото/видео", callback_data="rv:add_media"))
    b.add(InlineKeyboardButton(text="← Назад", callback_data="rv:back"))
    b.adjust(1)
    return b.as_markup()


def _confirm_no_media_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="Отправить без медиа", callback_data="rv:submit_no_media"))
    b.add(InlineKeyboardButton(text="← Назад", callback_data="rv:back"))
    b.adjust(1)
    return b.as_markup()


def _media_too_long_text() -> str:
    return (
        "Этот отзыв слишком длинный для публикации с фото/видео. "
        "Telegram ограничивает подпись к медиа, а ваш текст вместе с городом, исполнителем и автором уже не помещается.\n\n"
        "Отправьте отзыв без медиа или сократите текст и попробуйте добавить фото/видео снова."
    )


def _media_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="Готово, отправить на модерацию", callback_data="rv:media_submit"))
    b.add(InlineKeyboardButton(text="← Назад к превью", callback_data="rv:media_cancel"))
    b.adjust(1)
    return b.as_markup()


# ── state helpers ──────────────────────────────────────────────────────────────

async def _get_rv(state: FSMContext) -> tuple[int, dict, list]:
    d = await state.get_data()
    return (
        int(d.get("rv_step", 0)),
        dict(d.get("rv_payload", {})),
        list(d.get("rv_media", [])),
    )


async def _save_rv(state: FSMContext, *, step: int, payload: dict) -> None:
    await state.update_data(rv_step=step, rv_payload=payload)


# ── admin notify ───────────────────────────────────────────────────────────────

async def _rv_notify_admin(bot, post_id: int, payload: dict, media_list: list) -> None:
    from aiogram.types import InputMediaPhoto, InputMediaVideo

    post_text = _rv_render_html(payload)
    group = []
    for idx, item in enumerate(media_list[:10]):
        fid = item.get("file_id")
        if not fid:
            continue
        caption = post_text if idx == 0 else None
        if item.get("type") == "photo":
            group.append(InputMediaPhoto(media=fid, caption=caption, parse_mode="HTML"))
        elif item.get("type") == "video":
            group.append(InputMediaVideo(media=fid, caption=caption, parse_mode="HTML"))

    if group:
        try:
            await bot.send_media_group(chat_id=ADMIN_CHAT_ID, media=group)
        except Exception:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=post_text, parse_mode="HTML",
                                   disable_web_page_preview=True)
    else:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=post_text, parse_mode="HTML",
                               disable_web_page_preview=True)

    controls = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin:approve_premium:{post_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin:reject_premium:{post_id}"),
        ],
        [InlineKeyboardButton(text="📋 Список заявок", callback_data="admin:list_premium")],
    ])
    await bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"[{REVIEWS_SECTION_NAME}] Управление заявкой #{post_id}",
        reply_markup=controls,
        disable_web_page_preview=True,
    )


# ── submit helper ──────────────────────────────────────────────────────────────

async def _rv_do_submit(callback: CallbackQuery, state: FSMContext, payload: dict, media_list: list) -> None:
    author_username = callback.from_user.username or ""
    if not author_username:
        await callback.answer("Нужен Telegram username автора отзыва.", show_alert=True)
        await callback.message.edit_text(
            "Чтобы отправить отзыв, у вас должен быть Telegram username.\n\n"
            "Создайте username в настройках Telegram и вернитесь к отправке отзыва.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="@username создан", callback_data="rv:author_username_ready")],
                [InlineKeyboardButton(text="← Назад", callback_data="rv:back")],
            ]),
        )
        return

    payload["author_telegram"] = author_username
    first = media_list[0] if media_list else None
    try:
        user_db_id = db.create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        post_id = db.create_premium_post(
            user_id=user_db_id,
            mode="reviews",
            cities=_normalize_geo(payload.get("geo_tags", "")),
            description=payload.get("description", ""),
            social_media=payload.get("performer_contacts", ""),
            telegram_username=author_username,
            phone_main="",
            phone_whatsapp="",
            name="",
            media_file_id=first.get("file_id") if first else None,
            media_type=first.get("type") if first else None,
            media_list=media_list,
            action_type="post",
            payment_amount=0.00,
            admin_notes="reviews_moderation",
        )
        await _rv_notify_admin(callback.bot, post_id, payload, media_list)
        await state.clear()

        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="← Главное меню", callback_data="go:main"))
        await callback.message.edit_text(
            f"Ваш отзыв отправлен на модерацию. Администратор проверит его и опубликует в разделе {REVIEWS_SECTION_NAME}.",
            reply_markup=b.as_markup(),
        )
    except Exception as e:
        logger.exception("Reviews submit failed: %s", e)
        await callback.answer("Не удалось отправить отзыв на модерацию. Вернитесь к превью и попробуйте ещё раз.", show_alert=True)
        return
    await callback.answer()


# ── entry ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "section:reviews")
async def rv_entry(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    if db.is_residency_confirmed(callback.from_user.id):
        payload = {"resides_in_portugal": "yes"}
        await state.update_data(rv_step=_STEP_GEO, rv_payload=payload, rv_media=[])
        await state.set_state(RV_INPUT)
        await callback.message.edit_text(_PROMPTS[_STEP_GEO], reply_markup=_geo_kb())
        await callback.answer()
        return

    await state.update_data(rv_step=_STEP_RESIDENCY, rv_payload={}, rv_media=[])
    await state.set_state(RV_INPUT)
    await callback.message.edit_text(_PROMPTS[_STEP_RESIDENCY], reply_markup=_residency_kb())
    await callback.answer()


# ── residency choice ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rv:residency:"))
async def rv_residency(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RV_INPUT:
        await callback.answer()
        return
    value = callback.data.split(":", 2)[2]
    if value == "no":
        await state.clear()
        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="← Главное меню", callback_data="go:main"))
        await callback.message.edit_text(
            f"Раздел {REVIEWS_SECTION_NAME} доступен только для резидентов Португалии.",
            reply_markup=b.as_markup(),
        )
        await callback.answer()
        return
    _, payload, _ = await _get_rv(state)
    payload["resides_in_portugal"] = "yes"
    db.mark_residency_confirmed(callback.from_user.id)
    await _save_rv(state, step=_STEP_GEO, payload=payload)
    await callback.message.edit_text(_PROMPTS[_STEP_GEO], reply_markup=_geo_kb())
    await callback.answer()


# ── geo choice ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rv:geo:"))
async def rv_geo_choice(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RV_INPUT:
        await callback.answer()
        return
    val = callback.data.split(":", 2)[2]
    _, payload, _ = await _get_rv(state)
    if val == "custom":
        await state.set_state(RV_GEO_CUSTOM)
        await callback.message.edit_text(
            "Введите все нужные города одним сообщением.\n\nНапример: #lisboa #sintra #cascais или #online.\n\nНе добавляйте города потом в отзыв — они попадут в публикацию отдельной строкой.",
            reply_markup=_back_kb(),
        )
        await callback.answer()
        return
    payload["geo_tags"] = val
    await _save_rv(state, step=_STEP_CONTACTS, payload=payload)
    await state.set_state(RV_INPUT)
    await callback.message.edit_text(_PROMPTS[_STEP_CONTACTS], reply_markup=_back_kb())
    await callback.answer()


# ── custom geo text ────────────────────────────────────────────────────────────

@router.message(F.text, StateFilter(RV_GEO_CUSTOM))
async def rv_geo_custom_input(message: Message, state: FSMContext):
    raw = str(message.text or "").strip()
    if not raw:
        await message.answer("Введите хотя бы один город одним сообщением, например: #lisboa #porto #online", reply_markup=_back_kb())
        return
    _, payload, _ = await _get_rv(state)
    payload["geo_tags"] = raw
    await _save_rv(state, step=_STEP_CONTACTS, payload=payload)
    await state.set_state(RV_INPUT)
    await message.answer(_PROMPTS[_STEP_CONTACTS], reply_markup=_back_kb())


@router.message(~F.text, StateFilter(RV_GEO_CUSTOM))
async def rv_geo_custom_nontext(message: Message, state: FSMContext):
    if message.media_group_id:
        data = await state.get_data()
        seen = list(data.get("non_text_media_group_ids") or [])
        if message.media_group_id in seen:
            return
        seen.append(message.media_group_id)
        await state.update_data(non_text_media_group_ids=seen[-20:])
    await message.answer("В описании допускается только текст. Фото, видео, ссылки и контакты можно будет добавить на следующих шагах.\n\nПовторите отправку текстового описания:")

# ── back ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "rv:back")
async def rv_back(callback: CallbackQuery, state: FSMContext):
    cur = await state.get_state()
    step, payload, _ = await _get_rv(state)

    if cur == RV_GEO_CUSTOM:
        await _save_rv(state, step=_STEP_GEO, payload=payload)
        await state.set_state(RV_INPUT)
        await callback.message.edit_text(_PROMPTS[_STEP_GEO], reply_markup=_geo_kb())
    elif cur == RV_CONFIRM:
        await _save_rv(state, step=_STEP_DESCRIPTION, payload=payload)
        await state.set_state(RV_INPUT)
        await callback.message.edit_text(_PROMPTS[_STEP_DESCRIPTION], reply_markup=_back_kb())
    elif cur == RV_INPUT:
        if step == _STEP_GEO:
            if db.is_residency_confirmed(callback.from_user.id):
                await state.clear()
                await callback.message.edit_text(
                    "Здравствуйте!\n\nЭтот бот поможет вам опубликовать объявления "
                    "в разделы Справочника.\n\nВыберите действие:",
                    reply_markup=get_main_menu(),
                )
                await callback.answer()
                return
            await _save_rv(state, step=_STEP_RESIDENCY, payload=payload)
            await callback.message.edit_text(_PROMPTS[_STEP_RESIDENCY], reply_markup=_residency_kb())
        elif step == _STEP_CONTACTS:
            await _save_rv(state, step=_STEP_GEO, payload=payload)
            await callback.message.edit_text(_PROMPTS[_STEP_GEO], reply_markup=_geo_kb())
        elif step == _STEP_DESCRIPTION:
            await _save_rv(state, step=_STEP_CONTACTS, payload=payload)
            await callback.message.edit_text(_PROMPTS[_STEP_CONTACTS], reply_markup=_back_kb())
    await callback.answer()


# ── text input ─────────────────────────────────────────────────────────────────

@router.message(F.text, StateFilter(RV_INPUT))
async def rv_text_input(message: Message, state: FSMContext):
    step, payload, _ = await _get_rv(state)

    if step == _STEP_CONTACTS:
        raw = str(message.text or "").strip()
        if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", raw):
            await message.answer("Укажите Telegram username специалиста в формате @username. Минимум 5 символов после @, только латиница, цифры и подчёркивание.", reply_markup=_back_kb())
            return
        payload["performer_contacts"] = raw
        await _save_rv(state, step=_STEP_DESCRIPTION, payload=payload)
        await message.answer(_PROMPTS[_STEP_DESCRIPTION], reply_markup=_back_kb())
        return

    if step == _STEP_DESCRIPTION:
        raw = str(message.text or "").strip()
        ok, err = _validate_description_text(raw)
        if not ok:
            await message.answer(
                err + "\n\nПовторите отправку текстового описания:",
                disable_web_page_preview=True,
            )
            return
        if len(raw) < 20:
            await message.answer(
                "Отзыв слишком короткий. Напишите подробнее (минимум 20 символов).",
                reply_markup=_back_kb(),
            )
            return
        if len(raw) > REVIEW_TEXT_WITH_MEDIA_MAX_LEN:
            media_hint = (
                f"\n\nТекст длиннее {REVIEW_TEXT_WITH_MEDIA_MAX_LEN} символов, поэтому фото/видео добавить не получится. "
                "Без медиа такой отзыв можно отправить."
            )
        else:
            media_hint = ""
        payload["description"] = raw
        payload["author_telegram"] = message.from_user.username or ""
        await _save_rv(state, step=_STEP_DESCRIPTION, payload=payload)
        await state.set_state(RV_CONFIRM)
        rendered_text = _rv_render_html(payload)
        if len(rendered_text) > TELEGRAM_MEDIA_CAPTION_LIMIT:
            text = _media_too_long_text()
            reply_markup = _confirm_no_media_kb()
        elif len(raw) > REVIEW_TEXT_WITH_MEDIA_MAX_LEN:
            text = rendered_text + media_hint
            reply_markup = _confirm_no_media_kb()
        else:
            text = rendered_text + "\n\nЕсли есть фото или видео — добавьте их ниже. Или отправьте отзыв как есть."
            reply_markup = _confirm_kb()
        await message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return


@router.message(~F.text, StateFilter(RV_INPUT))
async def rv_text_nontext(message: Message, state: FSMContext):
    if message.media_group_id:
        data = await state.get_data()
        seen = list(data.get("non_text_media_group_ids") or [])
        if message.media_group_id in seen:
            return
        seen.append(message.media_group_id)
        await state.update_data(non_text_media_group_ids=seen[-20:])
    await message.answer("В описании допускается только текст. Фото, видео, ссылки и контакты можно будет добавить на следующих шагах.\n\nПовторите отправку текстового описания:")

# ── no-media submit ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "rv:author_username_ready")
async def rv_author_username_ready(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RV_CONFIRM:
        await callback.answer()
        return

    if not callback.from_user.username:
        await callback.answer("Username всё ещё не найден. Проверьте настройки Telegram.", show_alert=True)
        return

    step, payload, media_list = await _get_rv(state)
    payload["author_telegram"] = callback.from_user.username
    await _save_rv(state, step=step, payload=payload)

    rendered_text = _rv_render_html(payload)
    if len(rendered_text) > TELEGRAM_MEDIA_CAPTION_LIMIT:
        text = _media_too_long_text()
        reply_markup = _confirm_no_media_kb()
    else:
        text = rendered_text + "\n\nЕсли есть фото или видео — добавьте их ниже. Или отправьте отзыв как есть."
        reply_markup = _confirm_kb()

    await callback.message.edit_text(
        text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data == "rv:submit_no_media")
async def rv_submit_no_media(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RV_CONFIRM:
        await callback.answer()
        return
    _, payload, _ = await _get_rv(state)
    await _rv_do_submit(callback, state, payload, [])


# ── media start ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "rv:add_media")
async def rv_add_media(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RV_CONFIRM:
        await callback.answer()
        return

    _, payload, _ = await _get_rv(state)
    rendered_text = _rv_render_html(payload)
    if len(rendered_text) > TELEGRAM_MEDIA_CAPTION_LIMIT:
        await callback.message.edit_text(
            _media_too_long_text(),
            reply_markup=_confirm_no_media_kb(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        await callback.answer()
        return

    await state.set_state(RV_MEDIA)
    await state.update_data(rv_media=[], rv_media_status_id=callback.message.message_id)
    await callback.message.edit_text(
        "Отправьте фото или видео (до 10 файлов). Когда все добавите — нажмите «Готово».",
        reply_markup=_media_kb(),
    )
    await callback.answer()


# ── media upload ───────────────────────────────────────────────────────────────

@router.message(StateFilter(RV_MEDIA))
async def rv_media_input(message: Message, state: FSMContext):
    _, _, media = await _get_rv(state)

    item = None
    if message.photo:
        item = {"type": "photo", "file_id": message.photo[-1].file_id}
    elif message.video:
        item = {"type": "video", "file_id": message.video.file_id}

    if not item:
        return

    if len(media) >= 10:
        await message.answer("Достигнут лимит 10 файлов.", reply_markup=_media_kb())
        return

    media = media + [item]
    await state.update_data(rv_media=media)

    data = await state.get_data()
    status_id = data.get("rv_media_status_id")
    text = f"Добавлено файлов: {len(media)}/10"

    if status_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_id,
                text=text,
                reply_markup=_media_kb(),
            )
            return
        except Exception:
            pass

    sent = await message.answer(text, reply_markup=_media_kb())
    await state.update_data(rv_media_status_id=sent.message_id)


@router.callback_query(F.data == "rv:media_submit")
async def rv_media_submit(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RV_MEDIA:
        await callback.answer()
        return
    _, payload, media = await _get_rv(state)
    await _rv_do_submit(callback, state, payload, media)


@router.callback_query(F.data == "rv:media_cancel")
async def rv_media_cancel(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RV_MEDIA:
        await callback.answer()
        return
    _, payload, _ = await _get_rv(state)
    await state.update_data(rv_media=[], rv_media_status_id=None)
    await state.set_state(RV_CONFIRM)
    rendered_text = _rv_render_html(payload)
    if len(rendered_text) > TELEGRAM_MEDIA_CAPTION_LIMIT:
        text = _media_too_long_text()
        reply_markup = _confirm_no_media_kb()
    else:
        text = rendered_text + "\n\nЕсли есть фото или видео — добавьте их ниже. Или отправьте отзыв как есть."
        reply_markup = _confirm_kb()
    await callback.message.edit_text(
        text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()
