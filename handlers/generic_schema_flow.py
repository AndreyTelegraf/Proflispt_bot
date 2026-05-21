"""Generic schema flow handler for all catalogue sections except restaurants/jobs."""
from __future__ import annotations

import functools
import json
import logging
import re
from pathlib import Path

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
from models.posting_context import PostingContext
from services.schema_bootstrap import build_schema_registry
from services.schema_engine import SchemaEngine
from services.sections_registry import load_sections_registry
from services.geo import normalize_geo_tags_json
from services.catalog_listing_renderer import render_catalog_listing_html
from services.listing_validation import (
    STANDARD_LISTING_REQUIRED_FIELDS,
    is_valid_pt_mobile,
    validate_publish_payload,
)

logger = logging.getLogger(__name__)
router = Router()

# ── description prompt overrides ─────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _load_description_prompts() -> dict:
    path = Path(__file__).resolve().parent.parent / "config" / "generic_description_prompts.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_prompt(step, slug: str) -> str:
    """Return step prompt, substituting custom description text for known slugs."""
    if getattr(step, "field_name", "") == "description":
        return _load_description_prompts().get(slug, step.prompt)
    return step.prompt


# ── slug ↔ section name ───────────────────────────────────────────────────────

SLUG_TO_SECTION: dict[str, str] = {
    "job_seeker":           "Ищу работу",
    "job_offer":            "Предлагаю работу",
    "realtors":             "Риелторы",
    "construction_repair":  "Строительство и ремонт",
    "home_repair":          "Бытовой ремонт и обустройство",
    "device_repair":        "Ремонт техники",
    "furniture":            "Мебель изготовление",
    "cleaning":             "Клининг",
    "home_staff":           "Домашний персонал",
    "tailoring":            "Пошив одежды",
    "cooking":              "Кулинария",
    "passenger_transport":  "Пассажирские перевозки",
    "cargo_transport":      "Грузовые перевозки",
    "car_rental":           "Прокат авто",
    "auto_service":         "Автосервис",
    "translators":          "Переводчики",
    "residence_lawyers":    "ВНЖ/Юристы",
    "marketing":            "Маркетинг",
    "it_smm":               "IT/SMM",
    "money_credit":         "Деньги/кредиты",
    "insurance":            "Страхование",
    "accountants":          "Бухгалтеры",
    "printing":             "Полиграфия",
    "health":               "Здоровье",
    "medicine":             "Медицина",
    "beauty":               "Красота",
    "teaching":             "Преподавание",
    "sport":                "Спорт",
    "animals":              "Животные",
    "leisure":              "Отдых",
    "tourism":              "Туризм",
    "photo_video":          "Фото/видео",
    "art":                  "Искусство",
}

# ── FSM state names ───────────────────────────────────────────────────────────

GS_INPUT      = "gs_input"
GS_GEO_CUSTOM = "gs_geo_custom"
GS_TG_GATE    = "gs_tg_gate"
GS_CONFIRM    = "gs_confirm"
GS_MEDIA      = "gs_media"

# ── shared helpers ────────────────────────────────────────────────────────────

def _username_value(user) -> str | None:
    u = getattr(user, "username", None)
    if not u:
        return None
    u = str(u).strip().lstrip("@")
    return f"@{u}" if u else None


def _valid_pt_mobile(value: str) -> bool:
    return is_valid_pt_mobile(value)


def _norm(value) -> str:
    if value is None:
        return ""
    c = str(value).strip()
    if not c or c.lower() in {"нет", "no", "none"}:
        return ""
    return c


def _split_lines(value) -> list[str]:
    c = _norm(value)
    return [p.strip() for p in c.splitlines() if p.strip()] if c else []


def _normalize_social_links(value) -> str:
    raw = _norm(value)
    if not raw:
        return ""

    parts = []
    for chunk in re.split(r"[\n,;]+", raw):
        item = chunk.strip()
        item = item.strip(" \t\r\n,;")
        item = item.rstrip(".,;:!?)]}")
        item = item.lstrip("([{")
        item = re.sub(r"^\s*(?:[-–—*•]|\d+[.)])\s+", "", item)
        if not item:
            continue

        if item.startswith("@"):
            item = "https://t.me/" + item[1:]
        elif re.match(r"^(?:https?://|tg://)", item, re.I):
            pass
        elif re.match(r"^www\.", item, re.I):
            item = "https://" + item
        elif re.match(r"^[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}(?:/.*)?$", item):
            item = "https://" + item
        else:
            continue

        parts.append(item)

    seen = set()
    out = []
    for item in parts:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)

    return "\n".join(out)


def _validate_description_text(text: str) -> tuple[bool, str | None]:
    from services.contact_guard import validate_description_text
    return validate_description_text(text)



def _normalize_geo(value) -> str:
    return normalize_geo_tags_json(value)


def _extract_review_links(raw: str) -> list[str]:
    matches = re.findall(r"https://t\.me/proflistpt/12860/\d+", raw or "")
    seen: set[str] = set()
    result = []
    for lnk in matches:
        if lnk not in seen:
            seen.add(lnk)
            result.append(lnk)
    return result


def _normalize_review_links(raw: str) -> str:
    links = _extract_review_links(raw)
    links = links[:3]  # limit to 3 reviews
    return "\n".join(links)

# ── keyboards ─────────────────────────────────────────────────────────────────

def _back_kb(slug: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="← Назад", callback_data=f"gs:back:{slug}"))
    return b.as_markup()


def _choice_kb(step, slug: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    field = getattr(step, "field_name", "")
    label_defaults = {"yes": "Да", "no": "Нет"}

    for opt in getattr(step, "options", []) or []:
        val = str(opt.get("value", "")).strip()
        if not val:
            continue
        label = str(opt.get("label") or label_defaults.get(val.lower(), val)).strip()
        b.add(InlineKeyboardButton(text=label, callback_data=f"gs:choice:{slug}:{val}"))

    is_residency = (field == "resides_in_portugal")
    if not is_residency:
        b.add(InlineKeyboardButton(text="← Назад", callback_data=f"gs:back:{slug}"))

    if field == "geo_tags":
        b.adjust(3, 3, 3, 1, 1)
    elif is_residency:
        b.adjust(2)
    else:
        b.adjust(2, 1)
    return b.as_markup()


def _step_kb(step, slug: str) -> InlineKeyboardMarkup:
    fn = getattr(step, "field_name", "")
    if fn == "social_links":
        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="Ссылок нет", callback_data=f"gs:social_none:{slug}"))
        b.add(InlineKeyboardButton(text="← Назад", callback_data=f"gs:back:{slug}"))
        b.adjust(1)
        return b.as_markup()
    if fn == "review_links":
        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="Отзывов пока нет", callback_data=f"gs:reviews_none:{slug}"))
        b.add(InlineKeyboardButton(text="Отзывы", url="https://t.me/proflistpt/12860"))
        b.add(InlineKeyboardButton(text="← Назад", callback_data=f"gs:back:{slug}"))
        b.adjust(1)
        return b.as_markup()
    if fn == "phone_whatsapp":
        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="Нет / Совпадает с основным", callback_data=f"gs:wa_skip:{slug}"))
        b.add(InlineKeyboardButton(text="← Назад", callback_data=f"gs:back:{slug}"))
        b.adjust(1)
        return b.as_markup()
    if getattr(step, "kind", None) == "choice":
        return _choice_kb(step, slug)
    return _back_kb(slug)


def _preview_kb(slug: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="Опубликовать", callback_data=f"gs:confirm:{slug}"))
    b.add(InlineKeyboardButton(text="Опубликовать с фото/видео — €20", callback_data=f"gs:premium:{slug}"))
    b.add(InlineKeyboardButton(text="← Назад", callback_data=f"gs:back:{slug}"))
    b.adjust(1)
    return b.as_markup()


def _tg_gate_kb(slug: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="@username создан", callback_data=f"gs:tg_created:{slug}"))
    b.add(InlineKeyboardButton(text="← Назад", callback_data=f"gs:back:{slug}"))
    b.adjust(1)
    return b.as_markup()


def _media_kb(slug: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="Готово, отправить на модерацию", callback_data=f"gs:media_submit:{slug}"))
    b.add(InlineKeyboardButton(text="← Назад к превью", callback_data=f"gs:media_cancel:{slug}"))
    b.adjust(1)
    return b.as_markup()

# ── state data helpers ────────────────────────────────────────────────────────

async def _get_gs(state: FSMContext) -> tuple[str, str, int, dict, list]:
    """Return (section_name, slug, step_idx, payload, media)."""
    d = await state.get_data()
    return (
        d.get("gs_section_name", ""),
        d.get("gs_slug", ""),
        int(d.get("gs_step_idx", 0)),
        dict(d.get("gs_payload", {})),
        list(d.get("gs_media", [])),
    )


async def _save_gs(state: FSMContext, *, step_idx: int, payload: dict) -> None:
    await state.update_data(gs_step_idx=step_idx, gs_payload=payload)

# ── advance helper ────────────────────────────────────────────────────────────

def _next_content_index(schema, from_index: int) -> int:
    idx = from_index
    while idx < len(schema.steps) and schema.steps[idx].kind == "info":
        idx += 1
    return idx


def _previous_interactive_index(schema, current_index: int) -> int | None:
    idx = current_index - 1
    while idx >= 0:
        if schema.steps[idx].kind != "info":
            return idx
        idx -= 1
    return None


async def _advance(
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
    """Advance to next_raw_index, firing telegram gate if needed, or show preview."""
    next_index = _next_content_index(schema, next_raw_index)

    # Telegram gate: fires before phone_main when username not yet in payload
    if next_index < len(schema.steps):
        upcoming_field = getattr(schema.steps[next_index], "field_name", None)
        if upcoming_field == "phone_main" and not payload.get("telegram"):
            uname = _username_value(from_user)
            if not uname:
                await _save_gs(state, step_idx=next_index, payload=payload)
                await state.set_state(GS_TG_GATE)
                text = (
                    "Для публикации в справочнике нужен Telegram username.\n\n"
                    "Как создать @username в Telegram:\n"
                    "1. Откройте Настройки.\n"
                    "2. Зайдите в «Имя пользователя».\n"
                    "3. Создайте и сохраните @username.\n\n"
                    "После этого нажмите кнопку «@username создан»."
                )
                if is_message:
                    await target.answer(text, reply_markup=_tg_gate_kb(slug))
                else:
                    await target.edit_text(text, reply_markup=_tg_gate_kb(slug))
                return
            payload = dict(payload)
            payload["telegram"] = uname

    await _save_gs(state, step_idx=next_index, payload=payload)

    if next_index >= len(schema.steps):
        await state.set_state(GS_CONFIRM)
        text = render_catalog_listing_html(payload)
        kb = _preview_kb(slug)
        if is_message:
            await target.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        else:
            await target.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        return

    step = schema.steps[next_index]
    await state.set_state(GS_INPUT)
    if is_message:
        await target.answer(_resolve_prompt(step, slug), reply_markup=_step_kb(step, slug))
    else:
        await target.edit_text(_resolve_prompt(step, slug), reply_markup=_step_kb(step, slug))

# ── admin notify ──────────────────────────────────────────────────────────────

async def _notify_admin(bot, post_id: int, payload: dict, media_list: list, section_name: str) -> None:
    from aiogram.types import InputMediaPhoto, InputMediaVideo

    admin_chat_id = 336224597
    post_text = render_catalog_listing_html(payload)

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
            await bot.send_media_group(chat_id=admin_chat_id, media=group)
        except Exception:
            await bot.send_message(chat_id=admin_chat_id, text=post_text, parse_mode="HTML",
                                   disable_web_page_preview=True)
    else:
        await bot.send_message(chat_id=admin_chat_id, text=post_text, parse_mode="HTML",
                               disable_web_page_preview=True)

    controls = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin:approve_premium:{post_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin:reject_premium:{post_id}"),
        ],
        [InlineKeyboardButton(text="📋 Список заявок", callback_data="admin:list_premium")],
    ])
    await bot.send_message(
        chat_id=admin_chat_id,
        text=f"[{section_name}] Управление заявкой #{post_id}",
        reply_markup=controls,
        disable_web_page_preview=True,
    )

# ── entry ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("section:generic:"))
async def gs_entry(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 2)[2]
    section_name = SLUG_TO_SECTION.get(slug)
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
        gs_active=True,
        gs_section_name=section_name,
        gs_slug=slug,
        gs_step_idx=step_idx,
        gs_payload=payload,
        gs_media=[],
    )
    await state.set_state(GS_INPUT)

    step = schema.steps[step_idx]
    await callback.message.edit_text(_resolve_prompt(step, slug), reply_markup=_step_kb(step, slug))
    await callback.answer()

# ── choice input ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("gs:choice:"))
async def gs_choice(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != GS_INPUT:
        await callback.answer()
        return

    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer()
        return
    slug, raw_value = parts[2], parts[3]

    section_name, _, step_idx, payload, _ = await _get_gs(state)
    if not section_name:
        await callback.answer()
        return

    schema = build_schema_registry().get_by_section(section_name)
    step = schema.steps[step_idx]

    # Custom geo: transition to text input state
    if getattr(step, "field_name", "") == "geo_tags" and raw_value == "custom":
        await state.set_state(GS_GEO_CUSTOM)
        await callback.message.edit_text(
            "Введите все нужные города одним сообщением.\n\nНапример: #lisboa #sintra #cascais или #online.\n\nНе добавляйте города потом в описание — они попадут в объявление отдельной строкой.",
            reply_markup=_back_kb(slug),
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

    await _advance(callback.message, callback.from_user, state, schema, ctx.data,
                   step_idx + 1, slug, is_message=False)
    await callback.answer()

# ── custom geo text ───────────────────────────────────────────────────────────

@router.message(F.text, StateFilter(GS_GEO_CUSTOM))
async def gs_geo_custom_input(message: Message, state: FSMContext):
    section_name, slug, step_idx, payload, _ = await _get_gs(state)
    if not section_name:
        return
    raw = str(message.text or "").strip()
    if not raw:
        await message.answer(
            "Введите хотя бы один город одним сообщением, например: #lisboa #porto #online",
            reply_markup=_back_kb(slug),
        )
        return
    payload["geo_tags"] = raw
    schema = build_schema_registry().get_by_section(section_name)
    await _advance(message, message.from_user, state, schema, payload,
                   step_idx + 1, slug, is_message=True)


@router.message(~F.text, StateFilter(GS_GEO_CUSTOM))
async def gs_geo_custom_nontext(message: Message, state: FSMContext):
    if message.media_group_id:
        data = await state.get_data()
        seen = list(data.get("non_text_media_group_ids") or [])
        if message.media_group_id in seen:
            return
        seen.append(message.media_group_id)
        await state.update_data(non_text_media_group_ids=seen[-20:])
    await message.answer("В описании допускается только текст. Фото, видео, ссылки и контакты можно будет добавить на следующих шагах.\n\nПовторите отправку текстового описания:")

# ── skip / fast-path callbacks ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("gs:social_none:"))
async def gs_social_none(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != GS_INPUT:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_gs(state)
    payload["social_links"] = ""
    schema = build_schema_registry().get_by_section(section_name)
    await _advance(callback.message, callback.from_user, state, schema, payload,
                   step_idx + 1, slug, is_message=False)
    await callback.answer()


@router.callback_query(F.data.startswith("gs:reviews_none:"))
async def gs_reviews_none(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != GS_INPUT:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_gs(state)
    payload["review_links"] = ""
    schema = build_schema_registry().get_by_section(section_name)
    await _advance(callback.message, callback.from_user, state, schema, payload,
                   step_idx + 1, slug, is_message=False)
    await callback.answer()


@router.callback_query(F.data.startswith("gs:wa_same:"))
async def gs_wa_same(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != GS_INPUT:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_gs(state)
    payload["phone_whatsapp"] = ""
    schema = build_schema_registry().get_by_section(section_name)
    await _advance(callback.message, callback.from_user, state, schema, payload,
                   step_idx + 1, slug, is_message=False)
    await callback.answer()


@router.callback_query(F.data.startswith("gs:wa_none:"))
async def gs_wa_none(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != GS_INPUT:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_gs(state)
    payload["phone_whatsapp"] = ""
    schema = build_schema_registry().get_by_section(section_name)
    await _advance(callback.message, callback.from_user, state, schema, payload,
                   step_idx + 1, slug, is_message=False)
    await callback.answer()


@router.callback_query(F.data.startswith("gs:wa_skip:"))
async def gs_wa_skip(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != GS_INPUT:
        await callback.answer()
        return
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_gs(state)
    payload["phone_whatsapp"] = ""
    schema = build_schema_registry().get_by_section(section_name)
    await _advance(callback.message, callback.from_user, state, schema, payload,
                   step_idx + 1, slug, is_message=False)
    await callback.answer()

# ── telegram gate ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("gs:tg_created:"))
async def gs_tg_created(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_gs(state)

    uname = _username_value(callback.from_user)
    if not uname:
        await callback.answer("Telegram username пока не найден. Создайте его в настройках.", show_alert=True)
        return

    payload["telegram"] = uname
    await _save_gs(state, step_idx=step_idx, payload=payload)
    await state.set_state(GS_INPUT)

    schema = build_schema_registry().get_by_section(section_name)
    step = schema.steps[step_idx]
    await callback.message.edit_text(_resolve_prompt(step, slug), reply_markup=_step_kb(step, slug))
    await callback.answer()

# ── back ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("gs:back:"))
async def gs_back(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 2)[2]
    section_name, _, step_idx, payload, _ = await _get_gs(state)
    if not section_name:
        await callback.answer()
        return

    schema = build_schema_registry().get_by_section(section_name)
    cur = await state.get_state()

    if cur == GS_GEO_CUSTOM:
        prev_idx = next((i for i, s in enumerate(schema.steps)
                         if getattr(s, "field_name", None) == "geo_tags"), 0)
    elif cur == GS_TG_GATE:
        prev_idx = next((i for i, s in enumerate(schema.steps)
                         if getattr(s, "field_name", None) == "review_links"), None)
    elif cur in (GS_CONFIRM, GS_MEDIA):
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
            try:
                from handlers.section_catalog import _sections_keyboard
                from services.section_catalog import load_section_catalog

                catalog = load_section_catalog()
                group_key = None
                group_title = None
                for group in catalog.list_groups():
                    if section_name in group.sections:
                        group_key = group.key
                        group_title = group.title
                        break

                if group_key:
                    await callback.message.edit_text(
                        f"Группа: {group_title}\n\nТеперь выберите подходящий вам раздел:",
                        reply_markup=_sections_keyboard(group_key),
                    )
                else:
                    await callback.message.edit_text(
                        "Здравствуйте!\n\nЭтот бот поможет вам опубликовать объявления "
                        "в разделы Справочника.\n\nВыберите действие:",
                        reply_markup=get_main_menu(),
                    )
            except Exception:
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

    await _save_gs(state, step_idx=prev_idx, payload=payload)
    await state.set_state(GS_INPUT)

    step = schema.steps[prev_idx]
    await callback.message.edit_text(_resolve_prompt(step, slug), reply_markup=_step_kb(step, slug))
    await callback.answer()

# ── text input ────────────────────────────────────────────────────────────────

@router.message(F.text, StateFilter(GS_INPUT))
async def gs_text_input(message: Message, state: FSMContext):
    section_name, slug, step_idx, payload, _ = await _get_gs(state)
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
            await message.answer("Не нашёл ссылок. Вставьте сайт или соцсети, например: https://example.com или example.com", reply_markup=_step_kb(step, slug))
            return
        else:
            payload["social_links"] = normalized
        await _advance(message, message.from_user, state, schema, payload,
                       step_idx + 1, slug, is_message=True)
        return

    # review_links: validate or skip
    if field == "review_links":
        if raw.lower() in {"нет", "no", "none", "-", "—"}:
            payload["review_links"] = ""
        else:
            normalized = _normalize_review_links(raw)
            if not normalized:
                await message.answer(
                    'Неверная ссылка. Используйте ссылки из <a href="https://t.me/proflistpt/12860">Отзывы</a>. '
                    'Формат: https://t.me/proflistpt/12860/&lt;id&gt;',
                    reply_markup=_step_kb(step, slug),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                return
            payload["review_links"] = normalized
        await _advance(message, message.from_user, state, schema, payload,
                       step_idx + 1, slug, is_message=True)
        return

    # phone_main: strict mobile validation before schema engine
    if field == "phone_main":
        if not _valid_pt_mobile(raw):
            await message.answer("Неверный номер, перепроверьте.", reply_markup=_step_kb(step, slug))
            return

        is_phone_banned, phone_ban = db.is_identity_banned("phone", raw)
        if is_phone_banned:
            await message.answer("Этот номер телефона заблокирован для публикаций.", reply_markup=_step_kb(step, slug))
            return

    # phone_whatsapp: accept skip words as empty
    if field == "phone_whatsapp":
        if raw.lower() in {"нет", "no", "none", "-", "—"}:
            payload["phone_whatsapp"] = ""
            await _advance(message, message.from_user, state, schema, payload,
                           step_idx + 1, slug, is_message=True)
            return

    # Generic schema engine validation + store
    ctx = PostingContext(section_name=section_name)
    for k, v in payload.items():
        ctx.set_value(k, v)

    result = engine.process_answer(step, raw, ctx)
    if not result.accepted:
        await message.answer(result.error_message or "Ошибка ввода.", reply_markup=_step_kb(step, slug))
        return

    await _advance(message, message.from_user, state, schema, ctx.data,
                   step_idx + 1, slug, is_message=True)


@router.message(~F.text, StateFilter(GS_INPUT))
async def gs_text_nontext(message: Message, state: FSMContext):
    if message.media_group_id:
        data = await state.get_data()
        seen = list(data.get("non_text_media_group_ids") or [])
        if message.media_group_id in seen:
            return
        seen.append(message.media_group_id)
        await state.update_data(non_text_media_group_ids=seen[-20:])
    await message.answer("В описании допускается только текст. Фото, видео, ссылки и контакты можно будет добавить на следующих шагах.\n\nПовторите отправку текстового описания:")

# ── free publish ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("gs:confirm:"))
async def gs_confirm(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != GS_CONFIRM:
        await callback.answer()
        return

    slug = callback.data.split(":", 2)[2]
    section_name, _, _, payload, _ = await _get_gs(state)

    try:
        user = db.get_user(callback.from_user.id)
        if not user:
            user_db_id = db.create_user(
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
            b.add(InlineKeyboardButton(text="← Назад", callback_data=f"catalog:group:home_life"))
            b.adjust(1)
            await callback.message.edit_text(limit_message, reply_markup=b.as_markup())
            await callback.answer()
            return

        can_post, limit_message = db.check_free_repost_guard(
            user["id"],
            slug,
            payload.get("phone_main", ""),
        )
        if not can_post:
            b = InlineKeyboardBuilder()
            b.add(InlineKeyboardButton(text="Мои объявления", callback_data="my_postings"))
            b.add(InlineKeyboardButton(text="← Назад", callback_data=f"catalog:group:home_life"))
            b.adjust(1)
            await callback.message.edit_text(limit_message, reply_markup=b.as_markup())
            await callback.answer()
            return

        if not payload.get("telegram"):
            uname = _username_value(callback.from_user)
            if uname:
                payload = dict(payload)
                payload["telegram"] = uname
                await state.update_data(gs_payload=payload)

        # Final publish-boundary validation.
        # FSM/input validation is not enough: stale or corrupted state must not publish.
        validation = validate_publish_payload(payload, STANDARD_LISTING_REQUIRED_FIELDS)
        if not validation.ok:
            await callback.answer(validation.message, show_alert=True)
            return

        registry = load_sections_registry()
        channel_id = int(registry.channel_id)
        topic_id = int(registry.get_topic_id(section_name))

        published = await callback.bot.send_message(
            chat_id=channel_id,
            text=render_catalog_listing_html(payload),
            message_thread_id=topic_id,
            disable_web_page_preview=True,
            parse_mode="HTML",
        )

        await state.clear()

        try:
            if user:
                db.publish_free_generic_post(
                    user_id=user["id"],
                    mode=slug,
                    payload=payload,
                    cities=_normalize_geo(payload.get("geo_tags")),
                    message_id=published.message_id,
                    chat_id=channel_id,
                    topic_id=topic_id,
                )
                try:
                    from services.auto_repost import maybe_auto_repost_cargo
                    await maybe_auto_repost_cargo(
                        callback.bot,
                        db,
                        chat_id=channel_id,
                        topic_id=topic_id,
                        mode=slug,
                        action_type="post",
                    )
                except Exception as auto_repost_error:
                    logger.warning("Cargo auto repost failed: %s", auto_repost_error)
        except Exception as e:
            logger.warning("Could not persist free generic post: %s", e)

        try:
            chat_info = await callback.bot.get_chat(channel_id)
            link = (f"https://t.me/{chat_info.username}/{published.message_id}"
                    if chat_info.username else None)
        except Exception:
            link = None

        success = f"Объявление опубликовано. Ссылка: {link}" if link else "Объявление опубликовано."
        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="В главное меню", callback_data="go:main"))
        await callback.message.edit_text(success, reply_markup=b.as_markup())

    except Exception as e:
        logger.exception("Generic free publish failed: %s", e)
        await state.clear()
        msg = locals().get("limit_message") or "Ошибка при публикации. Попробуйте позже."
        await callback.message.edit_text(
            msg,
            reply_markup=_back_kb(slug),
        )

    await callback.answer()

# ── premium flow ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("gs:premium:"))
async def gs_premium_start(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != GS_CONFIRM:
        await callback.answer()
        return

    slug = callback.data.split(":", 2)[2]
    await state.set_state(GS_MEDIA)

    await callback.message.edit_text(
        "Отправьте фото или видео (до 10 файлов). Когда все добавите — нажмите «Готово».",
        reply_markup=_media_kb(slug),
    )
    await state.update_data(gs_media=[], gs_media_status_id=callback.message.message_id)
    await callback.answer()


@router.message(StateFilter(GS_MEDIA))
async def gs_media_input(message: Message, state: FSMContext):
    _, slug, _, _, media = await _get_gs(state)

    item = None
    if message.photo:
        item = {"type": "photo", "file_id": message.photo[-1].file_id}
    elif message.video:
        item = {"type": "video", "file_id": message.video.file_id}

    if not item:
        return

    if len(media) >= 10:
        await message.answer("Достигнут лимит 10 файлов.", reply_markup=_media_kb(slug))
        return

    media = media + [item]
    await state.update_data(gs_media=media)

    data = await state.get_data()
    status_id = data.get("gs_media_status_id")
    text = f"Добавлено файлов: {len(media)}/10"
    kb = _media_kb(slug)

    if status_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_id,
                text=text,
                reply_markup=kb,
            )
            return
        except Exception:
            pass

    sent = await message.answer(text, reply_markup=kb)
    await state.update_data(gs_media_status_id=sent.message_id)


@router.callback_query(F.data.startswith("gs:media_submit:"))
async def gs_media_submit(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 2)[2]
    section_name, _, _, payload, media = await _get_gs(state)

    if not media:
        await callback.answer("Сначала добавьте хотя бы одно фото или видео.", show_alert=True)
        return

    first = media[0]

    if not payload.get("telegram"):
        uname = _username_value(callback.from_user)
        if uname:
            payload = dict(payload)
            payload["telegram"] = uname
            await state.update_data(gs_payload=payload)

    # Final premium-submit boundary validation.
    # FSM/input validation is not enough: stale or corrupted state must not create premium posts.
    validation = validate_publish_payload(payload, STANDARD_LISTING_REQUIRED_FIELDS)
    if not validation.ok:
        await callback.answer(validation.message, show_alert=True)
        return

    try:
        user_db_id = db.create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
        post_id = db.create_premium_post(
            user_id=user_db_id,
            mode=slug,
            cities=_normalize_geo(payload.get("geo_tags")),
            description=payload.get("description", ""),
            social_media=payload.get("social_links", ""),
            telegram_username=payload.get("telegram", ""),
            phone_main=payload.get("phone_main", ""),
            phone_whatsapp=payload.get("phone_whatsapp", ""),
            name=payload.get("contact_name", ""),
            media_file_id=first.get("file_id"),
            media_type=first.get("type"),
            media_list=media,
            action_type="post",
            payment_amount=20.00,
            review_links=payload.get("review_links", ""),
            admin_notes=None,
        )
        await _notify_admin(callback.bot, post_id, payload, media, section_name)
        await state.clear()

        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="← Мои объявления", callback_data="back_to_my_postings"))
        await callback.message.edit_text(
            "Премиум-заявка отправлена на модерацию. Администратор проверит публикацию и свяжется с вами.",
            reply_markup=b.as_markup(),
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.exception("Generic premium submit failed: %s", e)
        await callback.answer("Ошибка при отправке заявки.", show_alert=True)
        return

    await callback.answer()


@router.callback_query(F.data.startswith("gs:media_cancel:"))
async def gs_media_cancel(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 2)[2]
    _, _, _, payload, _ = await _get_gs(state)
    await state.update_data(gs_media=[], gs_media_status_id=None)
    await state.set_state(GS_CONFIRM)
    await callback.message.edit_text(
        render_catalog_listing_html(payload),
        reply_markup=_preview_kb(slug),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()
