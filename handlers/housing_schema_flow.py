"""Housing schema flow — free publish to Справочник + Baraholka CTA."""
from __future__ import annotations

import asyncio
import html
import json
import logging
import re

_hs_media_locks: dict[str, asyncio.Lock] = {}


def _hs_media_lock(chat_id: int, user_id: int) -> asyncio.Lock:
    key = f"{chat_id}:{user_id}"
    if key not in _hs_media_locks:
        _hs_media_locks[key] = asyncio.Lock()
    return _hs_media_locks[key]

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from database import db
from keyboards.main import get_main_menu
from models.posting_context import PostingContext
from services.schema_bootstrap import build_schema_registry
from services.schema_engine import SchemaEngine
from services.sections_registry import load_sections_registry

from handlers.generic_schema_flow import (
    _normalize_geo,
    _username_value,
    _valid_pt_mobile,
    _norm,
    _split_lines,
    _normalize_social_links,
    _next_content_index,
    _previous_interactive_index,
)

logger = logging.getLogger(__name__)
router = Router()

HOUSING_SLUGS: dict[str, str] = {
    "housing_wanted":    "Ищу жильё",
    "owner_real_estate": "Недвижимость от хозяев",
}

_DESCRIPTION_PROMPTS: dict[str, str] = {
    "housing_wanted": (
        "Опишите, какое жильё вы ищете: город или район, срок аренды, бюджет, количество людей, животные, документы и важные условия.\n\n"
        "Пока не указывайте ссылки и контакты, их можно будет добавить на следующих шагах.\n\n"
        "Максимальная длина текста в этом блоке — 1.200 знаков:"
    ),
    "owner_real_estate": (
        "Опишите объект: город или район, тип жилья, цена, срок аренды или продажи, условия, мебель, коммунальные платежи и другие важные детали.\n\n"
        "Пока не указывайте ссылки и контакты, их можно будет добавить на следующих шагах.\n\n"
        "Максимальная длина текста в этом блоке — 1.200 знаков:"
    ),
}

_RENTAL_TAGS: dict[str, str] = {
    "short_term": "#короткосрок",
    "long_term":  "#долгосрок",
}

HS_INPUT      = "hs_input"
HS_GEO_CUSTOM = "hs_geo_custom"
HS_TG_GATE    = "hs_tg_gate"
HS_CONFIRM    = "hs_confirm"
HS_MEDIA      = "hs_media"


def _hs_resolve_prompt(step, slug: str) -> str:
    if getattr(step, "field_name", "") == "description":
        return _DESCRIPTION_PROMPTS.get(slug, step.prompt)
    return step.prompt


def _hs_render_html(payload: dict) -> str:
    """Housing-specific render: appends rental_term tag to geo line, omits review links."""
    lines: list[str] = []

    geo_tags = _split_lines(payload.get("geo_tags"))
    rental_tag = _RENTAL_TAGS.get(str(payload.get("rental_term", "")), "")

    if geo_tags:
        first = geo_tags[0].strip()
        if not first.startswith("#"):
            first = "#" + first.lstrip("#").lower()
        geo_line = html.escape(first)
        if rental_tag:
            geo_line += " " + html.escape(rental_tag)
        lines.append(geo_line)

    description = _norm(payload.get("description"))
    if description:
        dlines = [p.strip() for p in description.splitlines() if p.strip()]
        if dlines:
            lines.append("- " + html.escape(dlines[0]))
            for p in dlines[1:]:
                lines.append(html.escape(p))

    for link in _split_lines(payload.get("social_links")):
        lines.append(f'<a href="{html.escape(link, quote=True)}">Ссылка</a>')

    tg = _norm(payload.get("telegram"))
    if tg:
        lines.append(html.escape(tg))

    pm = _norm(payload.get("phone_main"))
    if pm:
        lines.append(html.escape(pm))

    pw = _norm(payload.get("phone_whatsapp"))
    if pw and pw != pm:
        lines.append(html.escape(pw))

    cn = _norm(payload.get("contact_name"))
    if cn:
        lines.append("- " + html.escape(cn))

    return "\n".join(lines).strip()


def _validate_description_text(text: str) -> tuple[bool, str | None]:
    if re.search(r"(https?://|www\.|t\.me/)", text, re.I):
        return False, "В описании допускается только текст. Ссылки можно будет добавить на следующих шагах."
    if re.search(r"[\U00010000-\U0010ffff\u2600-\u27BF\u2B00-\u2BFF\uFE0F]", text):
        return False, "В описании допускается только текст. Эмодзи использовать нельзя."
    if re.search(r"\[.*?\]\(.*?\)|<a\s+href=", text, re.I):
        return False, "В описании допускается только текст. Медиа, ссылки и контакты можно будет добавить на следующих шагах."
    if re.search(r"<\s*(b|strong)\b", text, re.I):
        return False, "В описании допускается только текст. Медиа, ссылки и контакты можно будет добавить на следующих шагах."
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    if emails:
        return False, "В описании допускается только текст. Медиа, ссылки и контакты можно будет добавить на следующих шагах."
    if re.search(r"@[A-Za-z0-9_]{5,32}\b", text):
        return False, "В описании допускается только текст. Медиа, ссылки и контакты можно будет добавить на следующих шагах."
    return True, None


# ── keyboards ─────────────────────────────────────────────────────────────────

def _hs_back_kb(slug: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="← Назад", callback_data=f"hs:back:{slug}"))
    return b.as_markup()


def _hs_choice_kb(step, slug: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    field = getattr(step, "field_name", "")
    label_defaults = {"yes": "Да", "no": "Нет"}
    for opt in getattr(step, "options", []) or []:
        val = str(opt.get("value", "")).strip()
        if not val:
            continue
        label = str(opt.get("label") or label_defaults.get(val.lower(), val)).strip()
        b.add(InlineKeyboardButton(text=label, callback_data=f"hs:choice:{slug}:{val}"))
    is_residency = (field == "resides_in_portugal")
    if not is_residency:
        b.add(InlineKeyboardButton(text="← Назад", callback_data=f"hs:back:{slug}"))
    if field == "geo_tags":
        b.adjust(3, 3, 3, 2, 1)
    elif is_residency:
        b.adjust(2)
    else:
        b.adjust(2, 1)
    return b.as_markup()


def _hs_step_kb(step, slug: str) -> InlineKeyboardMarkup:
    fn = getattr(step, "field_name", "")
    if fn == "social_links":
        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="Ссылок нет", callback_data=f"hs:social_none:{slug}"))
        b.add(InlineKeyboardButton(text="← Назад", callback_data=f"hs:back:{slug}"))
        b.adjust(1)
        return b.as_markup()
    if fn == "phone_whatsapp":
        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="Нет / Совпадает с основным", callback_data=f"hs:wa_skip:{slug}"))
        b.add(InlineKeyboardButton(text="← Назад", callback_data=f"hs:back:{slug}"))
        b.adjust(1)
        return b.as_markup()
    if getattr(step, "kind", None) == "choice":
        return _hs_choice_kb(step, slug)
    return _hs_back_kb(slug)


def _hs_preview_kb(slug: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="Опубликовать", callback_data=f"hs:publish_free:{slug}"))
    b.add(InlineKeyboardButton(text="← Назад", callback_data=f"hs:back:{slug}"))
    b.adjust(1)
    return b.as_markup()


def _hs_tg_gate_kb(slug: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="@username создан", callback_data=f"hs:tg_created:{slug}"))
    b.add(InlineKeyboardButton(text="← Назад", callback_data=f"hs:back:{slug}"))
    b.adjust(1)
    return b.as_markup()


def _hs_media_kb(slug: str, count: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if count > 0:
        b.add(InlineKeyboardButton(
            text=f"Продолжить ({count} файлов)",
            callback_data=f"hs:media_done:{slug}",
        ))
    b.add(InlineKeyboardButton(text="Продолжить без медиа", callback_data=f"hs:media_skip:{slug}"))
    b.add(InlineKeyboardButton(text="← Назад", callback_data=f"hs:media_preview_back:{slug}"))
    b.adjust(1)
    return b.as_markup()


# ── state data helpers ────────────────────────────────────────────────────────

async def _get_hs(state: FSMContext) -> tuple[str, str, int, dict, list]:
    d = await state.get_data()
    return (
        d.get("hs_section_name", ""),
        d.get("hs_slug", ""),
        int(d.get("hs_step_idx", 0)),
        dict(d.get("hs_payload", {})),
        list(d.get("hs_media", [])),
    )


async def _save_hs(state: FSMContext, *, step_idx: int, payload: dict) -> None:
    await state.update_data(hs_step_idx=step_idx, hs_payload=payload)


# ── advance helper ────────────────────────────────────────────────────────────

async def _hs_advance(
    target,
    from_user,
    state: FSMContext,
    schema,
    payload: dict,
    next_raw_index: int,
    slug: str,
    *,
    is_message: bool,
) -> None:
    next_index = _next_content_index(schema, next_raw_index)

    if next_index < len(schema.steps):
        upcoming_field = getattr(schema.steps[next_index], "field_name", None)
        if upcoming_field == "phone_main" and not payload.get("telegram"):
            uname = _username_value(from_user)
            if not uname:
                await _save_hs(state, step_idx=next_index, payload=payload)
                await state.set_state(HS_TG_GATE)
                text = (
                    "Для публикации в справочнике нужен Telegram username.\n\n"
                    "Как создать @username в Telegram:\n"
                    "1. Откройте Настройки.\n"
                    "2. Зайдите в «Имя пользователя».\n"
                    "3. Создайте и сохраните @username.\n\n"
                    "После этого нажмите кнопку «@username создан»."
                )
                if is_message:
                    await target.answer(text, reply_markup=_hs_tg_gate_kb(slug))
                else:
                    await target.edit_text(text, reply_markup=_hs_tg_gate_kb(slug))
                return
            payload = dict(payload)
            payload["telegram"] = uname

    await _save_hs(state, step_idx=next_index, payload=payload)

    if next_index >= len(schema.steps):
        await state.set_state(HS_MEDIA)
        await state.update_data(hs_media=[], hs_media_status_id=None)
        media_prompt = (
            "Добавьте фото или видео (до 10 файлов).\n"
            "Если хотите опубликовать без медиа — нажмите «Продолжить без медиа»."
        )
        if is_message:
            await target.answer(media_prompt, reply_markup=_hs_media_kb(slug, 0))
        else:
            await target.edit_text(media_prompt, reply_markup=_hs_media_kb(slug, 0))
        return

    step = schema.steps[next_index]
    await state.set_state(HS_INPUT)
    if is_message:
        await target.answer(_hs_resolve_prompt(step, slug), reply_markup=_hs_step_kb(step, slug))
    else:
        await target.edit_text(_hs_resolve_prompt(step, slug), reply_markup=_hs_step_kb(step, slug))


# ── entry ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("section:housing:"))
async def hs_entry(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 2)[2]
    section_name = HOUSING_SLUGS.get(slug)
    if not section_name:
        await callback.answer("Раздел не найден.", show_alert=True)
        return

    try:
        schema = build_schema_registry().get_by_section(section_name)
    except Exception:
        await callback.answer("Схема раздела не найдена.", show_alert=True)
        return

    await state.clear()

    payload = {}
    step_idx = 0
    if db.is_residency_confirmed(callback.from_user.id):
        payload["resides_in_portugal"] = "yes"
        step_idx = _next_content_index(schema, 1)

    await state.update_data(
        hs_active=True,
        hs_section_name=section_name,
        hs_slug=slug,
        hs_step_idx=step_idx,
        hs_payload=payload,
        hs_media=[],
    )
    await state.set_state(HS_INPUT)
    step = schema.steps[step_idx]
    await callback.message.edit_text(_hs_resolve_prompt(step, slug), reply_markup=_hs_step_kb(step, slug))
    await callback.answer()


# ── choice input ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("hs:choice:"))
async def hs_choice(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != HS_INPUT:
        await callback.answer()
        return

    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer()
        return
    slug, raw_value = parts[2], parts[3]

    section_name, _, step_idx, payload, _ = await _get_hs(state)
    if not section_name:
        await callback.answer()
        return

    schema = build_schema_registry().get_by_section(section_name)
    step = schema.steps[step_idx]

    if getattr(step, "field_name", "") == "geo_tags" and raw_value == "custom":
        await state.set_state(HS_GEO_CUSTOM)
        await callback.message.edit_text(
            "Введите города вручную, например: #lisboa #setubal #algarve или #online",
            reply_markup=_hs_back_kb(slug),
        )
        await callback.answer()
        return

    engine = SchemaEngine(schema)
    ctx = PostingContext(section_name=section_name)
    for k, v in payload.items():
        ctx.set_value(k, v)

    result = engine.process_answer(step, raw_value, ctx)
    if not result.accepted:
        await callback.answer(result.error_message or "Неверный ответ.", show_alert=True)
        return

    if getattr(step, "field_name", "") == "resides_in_portugal" and raw_value == "yes":
        db.mark_residency_confirmed(callback.from_user.id)

    if result.stop_flow:
        await state.clear()
        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="← Главное меню", callback_data="go:main"))
        await callback.message.edit_text(
            "Справочник работает только с резидентами Португалии.",
            reply_markup=b.as_markup(),
        )
        await callback.answer()
        return

    await _hs_advance(callback.message, callback.from_user, state, schema, ctx.data,
                      step_idx + 1, slug, is_message=False)
    await callback.answer()


# ── custom geo text ───────────────────────────────────────────────────────────

@router.message(F.text, StateFilter(HS_GEO_CUSTOM))
async def hs_geo_custom_input(message: Message, state: FSMContext):
    section_name, slug, step_idx, payload, _ = await _get_hs(state)
    if not section_name:
        return
    raw = str(message.text or "").strip()
    if not raw:
        await message.answer(
            "Введите хотя бы один город, например: #lisboa #porto #online",
            reply_markup=_hs_back_kb(slug),
        )
        return
    payload["geo_tags"] = raw
    schema = build_schema_registry().get_by_section(section_name)
    await _hs_advance(message, message.from_user, state, schema, payload,
                      step_idx + 1, slug, is_message=True)


@router.message(~F.text, StateFilter(HS_GEO_CUSTOM))
async def hs_geo_custom_nontext(message: Message, state: FSMContext):
    if message.media_group_id:
        data = await state.get_data()
        seen = list(data.get("non_text_media_group_ids") or [])
        if message.media_group_id in seen:
            return
        seen.append(message.media_group_id)
        await state.update_data(non_text_media_group_ids=seen[-20:])
    await message.answer("В описании допускается только текст. Фото, видео, ссылки и контакты можно будет добавить на следующих шагах.\n\nПовторите отправку текстового описания:")

# ── skip / fast-path callbacks ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("hs:social_none:"))
async def hs_social_none(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != HS_INPUT:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_hs(state)
    payload["social_links"] = ""
    schema = build_schema_registry().get_by_section(section_name)
    await _hs_advance(callback.message, callback.from_user, state, schema, payload,
                      step_idx + 1, slug, is_message=False)
    await callback.answer()


@router.callback_query(F.data.startswith("hs:wa_same:"))
async def hs_wa_same(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != HS_INPUT:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_hs(state)
    payload["phone_whatsapp"] = ""
    schema = build_schema_registry().get_by_section(section_name)
    await _hs_advance(callback.message, callback.from_user, state, schema, payload,
                      step_idx + 1, slug, is_message=False)
    await callback.answer()


@router.callback_query(F.data.startswith("hs:wa_none:"))
async def hs_wa_none(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != HS_INPUT:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_hs(state)
    payload["phone_whatsapp"] = ""
    schema = build_schema_registry().get_by_section(section_name)
    await _hs_advance(callback.message, callback.from_user, state, schema, payload,
                      step_idx + 1, slug, is_message=False)
    await callback.answer()


@router.callback_query(F.data.startswith("hs:wa_skip:"))
async def hs_wa_skip(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != HS_INPUT:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_hs(state)
    payload["phone_whatsapp"] = ""
    schema = build_schema_registry().get_by_section(section_name)
    await _hs_advance(callback.message, callback.from_user, state, schema, payload,
                      step_idx + 1, slug, is_message=False)
    await callback.answer()


# ── telegram gate ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("hs:tg_created:"))
async def hs_tg_created(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_hs(state)

    uname = _username_value(callback.from_user)
    if not uname:
        await callback.answer("Telegram username пока не найден. Создайте его в настройках.", show_alert=True)
        return

    payload["telegram"] = uname
    await _save_hs(state, step_idx=step_idx, payload=payload)
    await state.set_state(HS_INPUT)

    schema = build_schema_registry().get_by_section(section_name)
    step = schema.steps[step_idx]
    await callback.message.edit_text(_hs_resolve_prompt(step, slug), reply_markup=_hs_step_kb(step, slug))
    await callback.answer()


# ── back ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("hs:back:"))
async def hs_back(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, cur_media = await _get_hs(state)
    if not section_name:
        await callback.answer()
        return

    schema = build_schema_registry().get_by_section(section_name)
    cur = await state.get_state()

    if cur == HS_GEO_CUSTOM:
        prev_idx = next((i for i, s in enumerate(schema.steps)
                         if getattr(s, "field_name", None) == "geo_tags"), 0)
    elif cur == HS_TG_GATE:
        prev_idx = next((i for i, s in enumerate(schema.steps)
                         if getattr(s, "field_name", None) == "social_links"), None)
    elif cur == HS_CONFIRM:
        await state.set_state(HS_MEDIA)
        await callback.message.edit_text(
            "Добавьте фото или видео (до 10 файлов).\n"
            "Если хотите опубликовать без медиа — нажмите «Продолжить без медиа».",
            reply_markup=_hs_media_kb(slug, len(cur_media)),
        )
        await callback.answer()
        return
    elif cur == HS_MEDIA:
        prev_idx = _previous_interactive_index(schema, len(schema.steps))
    else:
        prev_idx = _previous_interactive_index(schema, step_idx)

    if (
        prev_idx is not None
        and getattr(schema.steps[prev_idx], "field_name", None) == "resides_in_portugal"
        and db.is_residency_confirmed(callback.from_user.id)
    ):
        prev_idx = _previous_interactive_index(schema, prev_idx)
        if prev_idx is None:
            await state.clear()
            await callback.message.edit_text(
                "Здравствуйте!\n\nЭтот бот поможет вам опубликовать объявления "
                "в разделы Справочника.\n\nВыберите действие:",
                reply_markup=get_main_menu(),
            )
            await callback.answer()
            return

    if prev_idx is None:
        await callback.answer()
        return

    await _save_hs(state, step_idx=prev_idx, payload=payload)
    await state.set_state(HS_INPUT)

    step = schema.steps[prev_idx]
    await callback.message.edit_text(_hs_resolve_prompt(step, slug), reply_markup=_hs_step_kb(step, slug))
    await callback.answer()


# ── text input ────────────────────────────────────────────────────────────────

@router.message(F.text, StateFilter(HS_INPUT))
async def hs_text_input(message: Message, state: FSMContext):
    section_name, slug, step_idx, payload, _ = await _get_hs(state)
    if not section_name:
        return

    schema = build_schema_registry().get_by_section(section_name)
    engine = SchemaEngine(schema)
    step = engine.get_step(step_idx)
    field = getattr(step, "field_name", "")
    raw = str(message.text or "").strip()

    if field == "description":
        ok, err = _validate_description_text(raw)
        if not ok:
            await message.answer(
                err + "\n\nПовторите отправку текстового описания:",
                disable_web_page_preview=True,
            )
            return

    if field == "social_links":
        normalized = _normalize_social_links(raw)
        if raw.lower() in {"нет", "no", "none", "-", "—"}:
            payload["social_links"] = ""
        elif not normalized:
            await message.answer("Не нашёл ссылок. Вставьте сайт или соцсети, например: https://example.com или example.com", reply_markup=_hs_step_kb(step, slug))
            return
        else:
            payload["social_links"] = normalized
        await _hs_advance(message, message.from_user, state, schema, payload,
                          step_idx + 1, slug, is_message=True)
        return

    if field == "phone_main":
        if not _valid_pt_mobile(raw):
            await message.answer("Неверный номер, перепроверьте.", reply_markup=_hs_step_kb(step, slug))
            return

    if field == "phone_whatsapp":
        if raw.lower() in {"нет", "no", "none", "-", "—"}:
            payload["phone_whatsapp"] = ""
            await _hs_advance(message, message.from_user, state, schema, payload,
                               step_idx + 1, slug, is_message=True)
            return

    ctx = PostingContext(section_name=section_name)
    for k, v in payload.items():
        ctx.set_value(k, v)

    result = engine.process_answer(step, raw, ctx)
    if not result.accepted:
        await message.answer(result.error_message or "Ошибка ввода.", reply_markup=_hs_step_kb(step, slug))
        return

    await _hs_advance(message, message.from_user, state, schema, ctx.data,
                      step_idx + 1, slug, is_message=True)


@router.message(~F.text, StateFilter(HS_INPUT))
async def hs_text_nontext(message: Message, state: FSMContext):
    if message.media_group_id:
        data = await state.get_data()
        seen = list(data.get("non_text_media_group_ids") or [])
        if message.media_group_id in seen:
            return
        seen.append(message.media_group_id)
        await state.update_data(non_text_media_group_ids=seen[-20:])
    await message.answer("В описании допускается только текст. Фото, видео, ссылки и контакты можно будет добавить на следующих шагах.\n\nПовторите отправку текстового описания:")

# ── media upload screen ───────────────────────────────────────────────────────

@router.message(StateFilter(HS_MEDIA))
async def hs_media_input(message: Message, state: FSMContext):
    lock = _hs_media_lock(message.chat.id, message.from_user.id)
    async with lock:
        data = await state.get_data()
        slug = data.get("hs_slug", "")
        media = list(data.get("hs_media", []))

        item = None
        if message.photo:
            item = {"type": "photo", "file_id": message.photo[-1].file_id}
        elif message.video:
            item = {"type": "video", "file_id": message.video.file_id}

        if not item:
            return

        if len(media) >= 10:
            await message.answer("Достигнут лимит 10 файлов.", reply_markup=_hs_media_kb(slug, len(media)))
            return

        media = media + [item]
        await state.update_data(hs_media=media)

        status_id = data.get("hs_media_status_id")
        text = f"Добавлено файлов: {len(media)}/10"
        kb = _hs_media_kb(slug, len(media))

        if status_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=status_id,
                    text=text,
                    reply_markup=kb,
                )
            except Exception:
                pass
            return

        sent = await message.answer(text, reply_markup=kb)
        await state.update_data(hs_media_status_id=sent.message_id)


@router.callback_query(F.data.startswith("hs:media_preview_back:"))
async def hs_media_preview_back(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 2)[2]
    section_name, _, _, payload, _ = await _get_hs(state)
    if not section_name:
        await callback.answer()
        return
    schema = build_schema_registry().get_by_section(section_name)
    prev_idx = _previous_interactive_index(schema, len(schema.steps))
    if prev_idx is None:
        await callback.answer()
        return
    await state.update_data(hs_media=[], hs_media_status_id=None)
    await _save_hs(state, step_idx=prev_idx, payload=payload)
    await state.set_state(HS_INPUT)
    step = schema.steps[prev_idx]
    await callback.message.edit_text(_hs_resolve_prompt(step, slug), reply_markup=_hs_step_kb(step, slug))
    await callback.answer()


# ── free publish helper ───────────────────────────────────────────────────────

async def _hs_free_publish(callback: CallbackQuery, state: FSMContext, slug: str, media: list) -> None:
    section_name, _, _, payload, _ = await _get_hs(state)

    user = db.get_user(callback.from_user.id)
    if not user:
        db.create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        user = db.get_user(callback.from_user.id)

    can_post, limit_message = db.check_premium_post_monthly_limit(user["id"], slug)
    if not can_post:
        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="Мои объявления", callback_data="my_postings"))
        b.add(InlineKeyboardButton(text="← Назад", callback_data="catalog:group:housing_work"))
        b.adjust(1)
        await callback.message.edit_text(limit_message, reply_markup=b.as_markup())
        await callback.answer()
        return

    registry = load_sections_registry()
    channel_id = int(registry.channel_id)
    topic_id = int(registry.get_topic_id(section_name))
    post_text = _hs_render_html(payload)

    published_message = None
    published_message_ids: list[int] = []

    if media:
        from aiogram.types import InputMediaPhoto, InputMediaVideo
        if len(media) > 1:
            group = []
            for i, item in enumerate(media[:10]):
                caption = post_text if i == 0 else None
                if item["type"] == "photo":
                    group.append(InputMediaPhoto(media=item["file_id"], caption=caption, parse_mode="HTML"))
                else:
                    group.append(InputMediaVideo(media=item["file_id"], caption=caption, parse_mode="HTML"))
            msgs = await callback.bot.send_media_group(
                chat_id=channel_id, media=group, message_thread_id=topic_id,
            )
            published_message = msgs[0] if msgs else None
            published_message_ids = [m.message_id for m in msgs]
        else:
            item = media[0]
            if item["type"] == "photo":
                published_message = await callback.bot.send_photo(
                    chat_id=channel_id, photo=item["file_id"],
                    caption=post_text, message_thread_id=topic_id, parse_mode="HTML",
                )
            else:
                published_message = await callback.bot.send_video(
                    chat_id=channel_id, video=item["file_id"],
                    caption=post_text, message_thread_id=topic_id, parse_mode="HTML",
                )
            published_message_ids = [published_message.message_id]
    else:
        published_message = await callback.bot.send_message(
            chat_id=channel_id,
            text=post_text,
            message_thread_id=topic_id,
            disable_web_page_preview=True,
            parse_mode="HTML",
        )
        published_message_ids = [published_message.message_id]

    await state.clear()

    source_post_id = None
    try:
        if user:
            source_post_id = db.publish_free_housing_post(
                user_id=user["id"],
                mode=slug,
                payload=payload,
                cities=_normalize_geo(payload.get("geo_tags")),
                message_id=published_message.message_id,
                chat_id=channel_id,
                topic_id=topic_id,
                media_list=media,
                published_message_ids=published_message_ids,
            )
    except Exception as e:
        logger.warning("Could not persist free housing post: %s", e)

    link = None
    try:
        chat_info = await callback.bot.get_chat(channel_id)
        if chat_info.username:
            link = f"https://t.me/{chat_info.username}/{published_message.message_id}"
    except Exception:
        pass

    link_line = f"Объявление опубликовано в Справочнике: {link}" if link else "Объявление опубликовано в Справочнике."
    upsell_text = (
        f"{link_line}\n\n"
        "Если хотите больше откликов и быстрее закрыть сделку, усильте объявление платным перепостом "
        "в @baraholka_pt с живой и активной аудиторией.\n\n"
        "Стоимость перепоста — €10"
    )
    b = InlineKeyboardBuilder()
    if source_post_id:
        b.add(InlineKeyboardButton(
            text="Платный перепост в Барахолку — €10",
            callback_data=f"hs:upsell_baraholka:{source_post_id}",
        ))
    b.add(InlineKeyboardButton(text="В главное меню", callback_data="go:main"))
    b.adjust(1)
    await callback.message.edit_text(upsell_text, reply_markup=b.as_markup(), disable_web_page_preview=True)


# ── free publish callbacks ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("hs:publish_free:"))
async def hs_publish_free(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != HS_CONFIRM:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    _, _, _, _, media = await _get_hs(state)
    try:
        await _hs_free_publish(callback, state, slug, media)
    except Exception as e:
        logger.exception("Housing free publish failed: %s", e)
        await state.clear()
        await callback.message.edit_text("Ошибка при публикации. Попробуйте позже.")
    await callback.answer()


@router.callback_query(F.data.startswith("hs:media_skip:"))
async def hs_media_skip(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != HS_MEDIA:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    await state.update_data(hs_media=[])
    _, _, _, payload, _ = await _get_hs(state)
    await state.set_state(HS_CONFIRM)
    await callback.message.edit_text(
        _hs_render_html(payload),
        reply_markup=_hs_preview_kb(slug),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("hs:media_done:"))
async def hs_media_done(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != HS_MEDIA:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    _, _, _, payload, media = await _get_hs(state)
    if not media:
        await callback.answer("Сначала добавьте хотя бы одно фото или видео.", show_alert=True)
        return
    await state.set_state(HS_CONFIRM)
    await callback.message.edit_text(
        _hs_render_html(payload),
        reply_markup=_hs_preview_kb(slug),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


# ── Baraholka post-publish upsell ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("hs:upsell_baraholka:"))
async def hs_upsell_baraholka(callback: CallbackQuery, state: FSMContext):
    raw_id = callback.data.split(":", 2)[2]
    try:
        source_post_id = int(raw_id)
    except ValueError:
        await callback.answer("Ошибка.", show_alert=True)
        return

    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    source_post = db.get_premium_post(source_post_id)
    if not source_post or source_post['user_id'] != user['id']:
        await callback.answer("Объявление не найдено.", show_alert=True)
        return

    try:
        repost_id = db.create_baraholka_housing_repost_from_post(source_post_id, user['id'])
        await _notify_admin_baraholka_from_post(callback.bot, repost_id, source_post)
    except Exception as e:
        logger.exception("Baraholka upsell repost failed: %s", e)
        await callback.answer("Ошибка при отправке заявки.", show_alert=True)
        return

    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="В главное меню", callback_data="go:main"))
    await callback.message.edit_text(
        "Заявка на перепост в Барахолку отправлена на модерацию. Администратор проверит и свяжется с вами.",
        reply_markup=b.as_markup(),
    )
    await callback.answer()


async def _notify_admin_baraholka_from_post(bot, post_id: int, source_post: dict) -> None:
    """Notify admin of Baraholka repost request from an already-persisted source post."""
    admin_chat_id = 336224597

    cities_raw = source_post.get("cities")
    if isinstance(cities_raw, list):
        geo_tags = " ".join(
            f"#{str(c).strip().lstrip('#').lower()}" for c in cities_raw if str(c).strip()
        )
    else:
        geo_tags = str(cities_raw or "")

    rental_term = ""
    try:
        src_notes = json.loads(source_post.get("admin_notes") or "{}")
        rental_term = src_notes.get("rental_term", "")
    except Exception:
        pass

    payload = {
        "geo_tags": geo_tags,
        "rental_term": rental_term,
        "description": source_post.get("description", ""),
        "social_links": source_post.get("social_media", ""),
        "telegram": source_post.get("telegram_username", ""),
        "phone_main": source_post.get("phone_main", ""),
        "phone_whatsapp": source_post.get("phone_whatsapp", ""),
        "contact_name": source_post.get("name", ""),
    }
    post_text = _hs_render_html(payload)
    section_name = HOUSING_SLUGS.get(source_post.get("mode", ""), source_post.get("mode", ""))

    controls = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin:approve_premium:{post_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin:reject_premium:{post_id}"),
        ],
        [InlineKeyboardButton(text="📋 Список заявок", callback_data="admin:list_premium")],
    ])
    await bot.send_message(
        chat_id=admin_chat_id,
        text=f"[{section_name} → Барахолка] Перепост #{post_id}\n\n{post_text}",
        reply_markup=controls,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
