# BACK_ARROW_AND_RESIDENCY_FIX_APPLIED
# SOCIAL_LINKS_EXTRACTOR_FIX_V2_APPLIED
# RESTAURANTS_PREVIEW_PARSE_MODE_FIX_APPLIED
# RESTAURANTS_HTML_PREVIEW_FIX_APPLIED
# PREVIEW_SOCIAL_LINKS_FIX_APPLIED
# SOCIAL_LINKS_RENDER_FIX_APPLIED
# REVIEWS_STEP_V2_APPLIED
# RESTAURANTS_PREMIUM_G2_FIX
# PREMIUM_INTERNAL_USER_ID_FIX
# G1C_UX_PATCH_APPLIED
# G1B_ADMIN_DELIVERY_FIX_APPLIED
# G1_FIXPACK_V2_APPLIED
from __future__ import annotations

import html
import json
import logging
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from database import db
from models.posting_context import PostingContext
from services.schema_bootstrap import build_schema_registry
from services.schema_engine import SchemaEngine
from services.sections_registry import load_sections_registry

logger = logging.getLogger(__name__)
router = Router()

RESTAURANTS_FLOW_STATE = "restaurants_schema_waiting_input"
RESTAURANTS_GEO_CUSTOM_STATE = "restaurants_schema_waiting_custom_geo"
RESTAURANTS_PREMIUM_MEDIA_STATE = "restaurants_schema_waiting_premium_media"
RESTAURANTS_PREMIUM_CONFIRM_STATE = "restaurants_schema_waiting_premium_confirm"

CITY_TO_TAG = {
    "lisboa": "#lisboa",
    "porto": "#porto",
    "coimbra": "#coimbra",
    "braga": "#braga",
    "faro": "#faro",
    "sintra": "#sintra",
    "cascais": "#cascais",
    "leiria": "#leiria",
    "madeira": "#madeira",
    "online": "#online",
}


def get_back_button(back_to: str = "restaurants:back") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="← Назад", callback_data=back_to))
    return builder.as_markup()


def _restaurants_residency_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Да", callback_data="restaurants:residency:yes"))
    builder.add(InlineKeyboardButton(text="Нет", callback_data="restaurants:residency:no"))
    builder.adjust(2)
    return builder.as_markup()


def _restaurants_geo_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("Lisboa", "restaurants:geo:lisboa"),
        ("Porto", "restaurants:geo:porto"),
        ("Coimbra", "restaurants:geo:coimbra"),
        ("Braga", "restaurants:geo:braga"),
        ("Faro", "restaurants:geo:faro"),
        ("Sintra", "restaurants:geo:sintra"),
        ("Cascais", "restaurants:geo:cascais"),
        ("Leiria", "restaurants:geo:leiria"),
        ("Madeira", "restaurants:geo:madeira"),
        ("Онлайн", "restaurants:geo:online"),
        ("Другие города", "restaurants:geo:custom"),
        ("Назад", "restaurants:back"),
    ]
    for text, callback_data in buttons:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
    builder.adjust(3, 3, 3, 2, 1)
    return builder.as_markup()


def _whatsapp_fast_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Совпадает с основным", callback_data="restaurants:wa_same"))
    builder.add(InlineKeyboardButton(text="Нет WhatsApp", callback_data="restaurants:wa_none"))
    builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
    builder.adjust(1)
    return builder.as_markup()


def _social_links_fast_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Нет ссылок", callback_data="restaurants:social_none"))
    builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
    builder.adjust(1)
    return builder.as_markup()


def _reviews_fast_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Отзывов пока нет", callback_data="restaurants:reviews_none"))
    builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
    builder.adjust(1)
    return builder.as_markup()


def _confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Опубликовать бесплатно", callback_data="confirm:restaurants_post"))
    builder.add(InlineKeyboardButton(text="Премиум (с фото/видео)", callback_data="restaurants:premium"))
    builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
    builder.adjust(1)
    return builder.as_markup()


def _premium_media_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Завершить загрузку медиа", callback_data="restaurants:premium_submit"))
    builder.add(InlineKeyboardButton(text="Отмена", callback_data="restaurants:premium_cancel"))
    builder.adjust(1)
    return builder.as_markup()


def _media_payload_from_message(message: Message) -> dict | None:
    if message.photo:
        best = message.photo[-1]
        return {
            "type": "photo",
            "file_id": best.file_id,
        }
    if message.video:
        return {
            "type": "video",
            "file_id": message.video.file_id,
        }
    return None



async def _premium_notify_admin(bot, premium_post_id: int, payload: dict, media_list: list[dict]):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo

    admin_chat_id = 336224597  # @andreytelegraf

    lines = [
        "<b>Новая премиум-заявка</b>",
        "",
        f"ID: {premium_post_id}",
        "Раздел: Рестораны",
    ]

    geo_tags = str(payload.get("geo_tags") or "").strip()
    description = str(payload.get("description") or "").strip()
    social_links = str(payload.get("social_links") or "").strip()
    telegram = str(payload.get("telegram") or "").strip()
    phone_main = str(payload.get("phone_main") or "").strip()
    phone_whatsapp = str(payload.get("phone_whatsapp") or "").strip()
    contact_name = str(payload.get("contact_name") or "").strip()

    if geo_tags:
        lines.append(f"Гео: {html.escape(geo_tags)}")
    if description:
        lines.append(f"Описание: {html.escape(description)}")
    if social_links and social_links.lower() not in {"нет", "no", "none"}:
        lines.append(f"Ссылки: {html.escape(social_links)}")
    if telegram:
        lines.append(f"Telegram: {html.escape(telegram)}")
    if phone_main:
        lines.append(f"Телефон: {html.escape(phone_main)}")
    if phone_whatsapp and phone_whatsapp.lower() not in {"нет", "no", "none"}:
        lines.append(f"WhatsApp: {html.escape(phone_whatsapp)}")
    if contact_name:
        lines.append(f"Контакт: {html.escape(contact_name)}")

    lines.extend([
        "",
        f"Медиа: {len(media_list)}",
    ])

    text = "\n".join(lines)

    if media_list:
        group = []
        for idx, item in enumerate(media_list[:10]):
            media_type = item.get("type")
            file_id = item.get("file_id")
            if not file_id:
                continue
            caption = text if idx == 0 else None
            if media_type == "photo":
                group.append(InputMediaPhoto(media=file_id, caption=caption, parse_mode="HTML"))
            elif media_type == "video":
                group.append(InputMediaVideo(media=file_id, caption=caption, parse_mode="HTML"))

        if group:
            try:
                await bot.send_media_group(chat_id=admin_chat_id, media=group)
            except Exception:
                await bot.send_message(
                    chat_id=admin_chat_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
        else:
            await bot.send_message(
                chat_id=admin_chat_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    else:
        await bot.send_message(
            chat_id=admin_chat_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    admin_controls = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Одобрить", callback_data=f"admin:approve_premium:{premium_post_id}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"admin:reject_premium:{premium_post_id}"),
        ],
        [
            InlineKeyboardButton(text="Список заявок", callback_data="admin:list_premium")
        ]
    ])

    await bot.send_message(
        chat_id=admin_chat_id,
        text=f"Управление заявкой #{premium_post_id}",
        reply_markup=admin_controls,
        disable_web_page_preview=True,
    )



def _extract_valid_review_links(text: str) -> list[str]:
    if not text:
        return []
    links = re.findall(r'https?://t\.me/[^\s]+', text)
    valid = []
    for link in links:
        if re.fullmatch(r'https://t\.me/proflistpt/12860/\d+', link.strip()):
            valid.append(link.strip())
    return valid


def _extract_social_links(text: str) -> list[str]:
    if not text:
        return []

    raw = str(text).strip()
    if raw.lower() in {"нет", "no", "none"}:
        return []

    candidates = re.findall(
        r'(https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+|facebook\.com/[^\s]+|instagram\.com/[^\s]+)',
        raw,
        flags=re.IGNORECASE,
    )

    out = []
    seen = set()

    for link in candidates:
        clean = str(link).strip().rstrip('.,);]')
        if not clean:
            continue

        low = clean.lower()
        if low.startswith("www."):
            clean = "https://" + clean
        elif low.startswith("t.me/"):
            clean = "https://" + clean
        elif low.startswith("facebook.com/") or low.startswith("instagram.com/"):
            clean = "https://" + clean

        if clean not in seen:
            seen.add(clean)
            out.append(clean)

    if not out:
        candidate = raw.strip().rstrip('.,);]')
        low = candidate.lower()
        if (
            low.startswith("http://")
            or low.startswith("https://")
            or low.startswith("www.")
            or low.startswith("t.me/")
            or low.startswith("facebook.com/")
            or low.startswith("instagram.com/")
        ):
            if low.startswith("www."):
                candidate = "https://" + candidate
            elif low.startswith("t.me/"):
                candidate = "https://" + candidate
            elif low.startswith("facebook.com/") or low.startswith("instagram.com/"):
                candidate = "https://" + candidate
            out.append(candidate)

    return out


def _render_social_links_html(payload: dict) -> list[str]:
    links = _extract_social_links(payload.get("social_links"))
    result = []
    for link in links:
        label = _social_link_label(link)
        result.append(f'<a href="{html.escape(link, quote=True)}">{html.escape(label)}</a>')
    return result


def _render_social_links_preview(payload: dict) -> list[str]:
    links = _extract_social_links(payload.get("social_links"))
    result = []
    for link in links:
        label = _social_link_label(link)
        result.append(f'<a href="{html.escape(link, quote=True)}">{html.escape(label)}</a>')
    return result


def _render_reviews_html(payload: dict) -> list[str]:
    reviews = payload.get("reviews_links") or []
    if isinstance(reviews, str):
        reviews = [reviews] if reviews.strip() else []
    result = []
    for link in reviews:
        if re.fullmatch(r'https://t\.me/proflistpt/12860/\d+', str(link).strip()):
            result.append(f'<a href="{html.escape(str(link).strip(), quote=True)}">- отзыв клиента</a>')
    return result
def _social_link_label(link: str) -> str:
    low = link.lower()
    if "instagram.com" in low:
        return "- Instagram"
    if "facebook.com" in low or "fb.com" in low:
        return "- Facebook"
    if "t.me/" in low or "telegram.me/" in low:
        return "- Telegram"
    if "google.com/maps" in low or "maps.apple.com" in low or "goo.gl/maps" in low:
        return "- Карта"
    return "- Ссылка"


def _render_social_links_html(payload: dict) -> list[str]:
    links = _extract_social_links(payload.get("social_links"))
    result = []
    for link in links:
        label = _social_link_label(link)
        result.append(f'<a href="{html.escape(link, quote=True)}">{html.escape(label)}</a>')
    return result


def _render_social_links_preview(payload: dict) -> list[str]:
    links = _extract_social_links(payload.get("social_links"))
    result = []
    for link in links:
        label = _social_link_label(link)
        result.append(f"{label}: ссылка")
    return result


def _render_reviews_html(payload: dict) -> list[str]:
    reviews = payload.get("reviews_links") or []
    if isinstance(reviews, str):
        reviews = [reviews] if reviews.strip() else []
    result = []
    for link in reviews:
        if re.fullmatch(r'https://t\.me/proflistpt/12860/\d+', str(link).strip()):
            result.append(f'<a href="{html.escape(str(link).strip(), quote=True)}">- отзыв клиента</a>')
    return result


def _normalize_geo_tags_for_db(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "[]"
    parts = [p for p in raw.split() if p.strip()]
    clean = []
    for p in parts:
        item = p.strip()
        if not item:
            continue
        if item.startswith("#"):
            item = item[1:]
        clean.append(item.lower())
    return json.dumps(clean, ensure_ascii=False)



async def _upsert_premium_media_status(message: Message, state: FSMContext, text: str):
    data = await state.get_data()
    chat_id = message.chat.id

    prompt_message_id = data.get("restaurants_premium_prompt_message_id")
    if prompt_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=prompt_message_id,
                text=text,
                reply_markup=_premium_media_keyboard(),
                disable_web_page_preview=True,
            )
            return
        except Exception:
            pass

    status_message_id = data.get("restaurants_premium_status_message_id")
    if status_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message_id,
                text=text,
                reply_markup=_premium_media_keyboard(),
                disable_web_page_preview=True,
            )
            return
        except Exception:
            pass

    sent = await message.answer(
        text,
        reply_markup=_premium_media_keyboard(),
        disable_web_page_preview=True,
    )
    await state.update_data(restaurants_premium_status_message_id=sent.message_id)


def _premium_preview_text(payload: dict, media_list: list[dict]) -> str:
    lines = [
        "Премиум-заявка для модерации.",
        "",
        f"Медиа: {len(media_list)}",
        "",
        _confirmation_text(payload),
    ]
    return "\n".join(lines).strip()


def _username_value(user) -> str | None:
    if not user:
        return None
    username = getattr(user, "username", None)
    if not username:
        return None
    username = str(username).strip()
    if not username:
        return None
    return f"@{username.lstrip('@')}"


def _valid_pt_mobile(value: str) -> bool:
    value = str(value or "").strip()
    if len(value) != 13:
        return False
    if not value.startswith("+351"):
        return False
    if not value[4:].isdigit():
        return False
    return (
        value.startswith("+35191")
        or value.startswith("+35192")
        or value.startswith("+35193")
        or value.startswith("+35196")
    )


def _next_prompt(schema, next_index: int) -> tuple[int, str]:
    prompts = []
    idx = next_index

    while idx < len(schema.steps) and schema.steps[idx].kind == "info":
        prompts.append(schema.steps[idx].prompt)
        idx += 1

    if idx < len(schema.steps):
        prompts.append(schema.steps[idx].prompt)

    return idx, "\n\n".join([p for p in prompts if p])


def _find_step_index(schema, field_name: str) -> int:
    for idx, step in enumerate(schema.steps):
        if getattr(step, "field_name", None) == field_name:
            return idx
    raise RuntimeError(f"restaurants schema missing step: {field_name}")


def _confirmation_text(payload: dict) -> str:
    body = _render_html(payload)
    return "Проверьте объявление перед публикацией.\n\n" + body


def _render_html(payload: dict) -> str:
    geo_tags = str(payload.get("geo_tags") or "").strip()
    description = str(payload.get("description") or "").strip()
    social_links = str(payload.get("social_links") or "").strip()
    telegram = str(payload.get("telegram") or "").strip()
    phone_main = str(payload.get("phone_main") or "").strip()
    phone_whatsapp = str(payload.get("phone_whatsapp") or "").strip()
    contact_name = str(payload.get("contact_name") or "").strip()
    social_link_lines = _render_social_links_html(payload)
    reviews_lines = _render_reviews_html(payload)

    lines = []

    if geo_tags:
        lines.append(html.escape(geo_tags))
    if description:
        lines.append(html.escape(description))
    if social_link_lines:
        lines.extend(social_link_lines)
    if telegram:
        lines.append(html.escape(telegram))
    if phone_main:
        lines.append(html.escape(phone_main))
    if phone_whatsapp and phone_whatsapp.lower() not in {"нет", "no", "none"} and phone_whatsapp != phone_main:
        lines.append(html.escape(phone_whatsapp))
    if contact_name:
        lines.append(html.escape(f"- {contact_name}"))

    if reviews_lines:
        lines.append("")
        lines.append("")
        lines.extend(reviews_lines)

    return "\n".join(lines).strip()


def _make_ctx(payload: dict) -> PostingContext:
    ctx = PostingContext(section_name="Рестораны")
    for key, value in payload.items():
        ctx.set_value(key, value)
    return ctx


def _history_push(history: list, step_index: int, payload: dict) -> list:
    return history + [{"step_index": int(step_index), "payload": dict(payload or {})}]


def _schema_and_entry_index():
    schema = build_schema_registry().get_by_section("Рестораны")
    entry_index = 0
    while entry_index < len(schema.steps) and schema.steps[entry_index].kind == "info":
        entry_index += 1
    if entry_index >= len(schema.steps):
        raise RuntimeError("restaurants schema has no interactive steps")
    return schema, entry_index


async def _render_step_message(target_message: Message, state: FSMContext, schema, step_index: int, payload: dict, *, edit: bool):
    if step_index >= len(schema.steps):
        if edit:
            await target_message.edit_text(
                _confirmation_text(payload),
                reply_markup=_confirmation_keyboard(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        else:
            await target_message.answer(
                _confirmation_text(payload),
                reply_markup=_confirmation_keyboard(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        await state.set_state("restaurants_schema_waiting_confirmation")
        return

    prompt_text = schema.steps[step_index].prompt
    next_step = schema.steps[step_index]
    field_name = getattr(next_step, "field_name", None)

    if field_name == "phone_whatsapp":
        reply_markup = _whatsapp_fast_keyboard()
    elif field_name == "social_links":
        reply_markup = _social_links_fast_keyboard()
    elif field_name == "reviews_links":
        reply_markup = _reviews_fast_keyboard()
    else:
        reply_markup = get_back_button()

    if edit:
        await target_message.edit_text(prompt_text, reply_markup=reply_markup)
    else:
        await target_message.answer(prompt_text, reply_markup=reply_markup)

    await state.set_state(RESTAURANTS_FLOW_STATE)


async def _show_geo_selector(target_message: Message, state: FSMContext, payload: dict, history: list, *, edit: bool):
    schema, _ = _schema_and_entry_index()
    geo_index = _find_step_index(schema, "geo_tags")

    await state.update_data(
        restaurants_schema_active=True,
        restaurants_schema_step_index=geo_index,
        restaurants_schema_payload=payload,
        restaurants_schema_history=history,
    )
    await state.set_state(RESTAURANTS_FLOW_STATE)

    text = "Выберите город или формат размещения для объявления:"
    if edit:
        await target_message.edit_text(text, reply_markup=_restaurants_geo_keyboard())
    else:
        await target_message.answer(text, reply_markup=_restaurants_geo_keyboard())


async def _start_flow(target, state: FSMContext, is_callback: bool = False):
    schema, entry_index = _schema_and_entry_index()

    await state.clear()
    await state.update_data(
        restaurants_schema_active=True,
        restaurants_schema_step_index=entry_index,
        restaurants_schema_payload={},
        restaurants_schema_history=[],
    )
    await state.set_state(RESTAURANTS_FLOW_STATE)

    residency_prompt = schema.steps[entry_index].prompt

    if is_callback:
        await target.message.edit_text(residency_prompt, reply_markup=_restaurants_residency_keyboard())
        await target.answer()
    else:
        await target.answer(residency_prompt, reply_markup=_restaurants_residency_keyboard())


async def _advance_after_ctx(message: Message, actor_user, state: FSMContext, schema, current_step_index: int, ctx: PostingContext, history: list):
    next_index, _ = _next_prompt(schema, current_step_index + 1)

    if next_index < len(schema.steps):
        next_step = schema.steps[next_index]
        if getattr(next_step, "field_name", None) == "telegram":
            username_value = _username_value(actor_user)
            if not username_value:
                await state.clear()
                await message.answer(
                    "Для публикации в справочнике нужен Telegram username.\n\n"
                    "Создайте @username в настройках Telegram и затем снова запустите публикацию.",
                    reply_markup=get_back_button("go:main")
                )
                return

            history = _history_push(history, next_index, ctx.data)
            ctx.set_value("telegram", username_value)
            next_index, _ = _next_prompt(schema, next_index + 1)

    await state.update_data(
        restaurants_schema_active=True,
        restaurants_schema_payload=ctx.data,
        restaurants_schema_step_index=next_index,
        restaurants_schema_history=history,
    )

    if next_index >= len(schema.steps):
        await message.answer(
            _confirmation_text(ctx.data),
            reply_markup=_confirmation_keyboard(),
                parse_mode="HTML",
            disable_web_page_preview=True,
        )
        await state.set_state("restaurants_schema_waiting_confirmation")
        return

    await _render_step_message(message, state, schema, next_index, ctx.data, edit=False)


@router.message(Command("restaurants"))
async def start_restaurants_schema_command(message: Message, state: FSMContext):
    await _start_flow(message, state, is_callback=False)


@router.callback_query(F.data == "section:restaurants")
async def start_restaurants_schema_callback(callback: CallbackQuery, state: FSMContext):
    await _start_flow(callback, state, is_callback=True)


@router.callback_query(F.data == "restaurants:residency:yes")
async def restaurants_residency_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("restaurants_schema_active"):
        await callback.answer()
        return

    schema, entry_index = _schema_and_entry_index()
    payload = dict(data.get("restaurants_schema_payload", {}))
    history = list(data.get("restaurants_schema_history", []))

    ctx = _make_ctx(payload)
    ctx.set_value("resides_in_portugal", "yes")
    history = _history_push(history, entry_index, payload)

    await _show_geo_selector(callback.message, state, ctx.data, history, edit=True)
    await callback.answer()


@router.callback_query(F.data == "restaurants:residency:no")
async def restaurants_residency_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Мы работаем с резидентами Португалии. Возвращайтесь после переезда.",
        reply_markup=get_back_button("go:main")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("restaurants:geo:"))
async def restaurants_geo_select(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("restaurants_schema_active"):
        await callback.answer()
        return

    _, _, city_key = callback.data.split(":", 2)

    if city_key == "custom":
        await state.set_state(RESTAURANTS_GEO_CUSTOM_STATE)
        await callback.message.edit_text(
            "Введите геотеги вручную, например: #lisboa #cascais #online",
            reply_markup=get_back_button("restaurants:geo_back")
        )
        await callback.answer()
        return

    geo_tag = CITY_TO_TAG.get(city_key)
    if not geo_tag:
        await callback.answer()
        return

    schema, _ = _schema_and_entry_index()
    geo_index = _find_step_index(schema, "geo_tags")
    payload = dict(data.get("restaurants_schema_payload", {}))
    history = list(data.get("restaurants_schema_history", []))

    ctx = _make_ctx(payload)
    ctx.set_value("geo_tags", geo_tag)
    history = _history_push(history, geo_index, payload)

    await _advance_after_ctx(callback.message, callback.from_user, state, schema, geo_index, ctx, history)
    await callback.answer()


@router.callback_query(F.data == "restaurants:geo_back")
async def restaurants_geo_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("restaurants_schema_active"):
        await callback.answer()
        return
    payload = dict(data.get("restaurants_schema_payload", {}))
    history = list(data.get("restaurants_schema_history", []))
    await _show_geo_selector(callback.message, state, payload, history, edit=True)
    await callback.answer()


@router.callback_query(F.data == "restaurants:back")
async def restaurants_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    history = list(data.get("restaurants_schema_history", []))

    if not data.get("restaurants_schema_active"):
        await callback.message.edit_text("Сессия публикации не найдена.", reply_markup=get_back_button("go:main"))
        await callback.answer()
        return

    if not history:
        await state.clear()
        await callback.message.edit_text(
            "Публикация отменена.",
            reply_markup=get_back_button("go:main")
        )
        await callback.answer()
        return

    schema, entry_index = _schema_and_entry_index()
    geo_index = _find_step_index(schema, "geo_tags")

    while history:
        snapshot = history.pop()
        step_index = int(snapshot["step_index"])
        payload = dict(snapshot.get("payload", {}))

        if step_index == geo_index:
            await _show_geo_selector(callback.message, state, payload, history, edit=True)
            await callback.answer()
            return

        if step_index == entry_index:
            await state.update_data(
                restaurants_schema_active=True,
                restaurants_schema_step_index=entry_index,
                restaurants_schema_payload=payload,
                restaurants_schema_history=history,
            )
            await state.set_state(RESTAURANTS_FLOW_STATE)
            await callback.message.edit_text(
                schema.steps[entry_index].prompt,
                reply_markup=_restaurants_residency_keyboard()
            )
            await callback.answer()
            return

        if step_index < len(schema.steps):
            step = schema.steps[step_index]
            if getattr(step, "field_name", None) == "telegram" and _username_value(callback.from_user):
                continue

        await state.update_data(
            restaurants_schema_active=True,
            restaurants_schema_step_index=step_index,
            restaurants_schema_payload=payload,
            restaurants_schema_history=history,
        )

        await _render_step_message(callback.message, state, schema, step_index, payload, edit=True)
        await callback.answer()
        return

    await state.clear()
    await callback.message.edit_text(
        "Публикация отменена.",
        reply_markup=get_back_button("go:main")
    )
    await callback.answer()


@router.callback_query(F.data == "restaurants:reviews_none")
async def restaurants_reviews_none(callback: CallbackQuery, state: FSMContext):
    try:
        if await state.get_state() != RESTAURANTS_FLOW_STATE:
            await callback.answer()
            return

        data = await state.get_data()
        payload = dict(data.get("restaurants_schema_payload", {}))
        history = list(data.get("restaurants_schema_history", []))
        step_index = int(data.get("restaurants_schema_step_index", 0))
        schema, _ = _schema_and_entry_index()

        if step_index >= len(schema.steps):
            await callback.answer()
            return

        step = schema.steps[step_index]
        if getattr(step, "field_name", None) != "reviews_links":
            await callback.answer()
            return

        history = _history_push(history, step_index, payload)
        ctx = _make_ctx(payload)
        ctx.set_value("reviews_links", [])

        await _advance_after_ctx(callback.message, callback.from_user, state, schema, step_index, ctx, history)
        await callback.answer()
    except Exception as e:
        logger.exception("restaurants_reviews_none failed: %s", e)
        await callback.answer("Ошибка, попробуйте ещё раз.", show_alert=True)


@router.callback_query(F.data == "restaurants:social_none")
async def restaurants_social_none(callback: CallbackQuery, state: FSMContext):
    try:
        if await state.get_state() != RESTAURANTS_FLOW_STATE:
            await callback.answer()
            return

        data = await state.get_data()
        payload = dict(data.get("restaurants_schema_payload", {}))
        history = list(data.get("restaurants_schema_history", []))
        step_index = int(data.get("restaurants_schema_step_index", 0))
        schema, _ = _schema_and_entry_index()

        if step_index >= len(schema.steps):
            await callback.answer()
            return

        step = schema.steps[step_index]
        if getattr(step, "field_name", None) != "social_links":
            await callback.answer()
            return

        history = _history_push(history, step_index, payload)
        ctx = _make_ctx(payload)
        ctx.set_value("social_links", "нет")

        await _advance_after_ctx(callback.message, callback.from_user, state, schema, step_index, ctx, history)
        await callback.answer()
    except Exception as e:
        logger.exception("restaurants_social_none failed: %s", e)
        await callback.answer("Ошибка, попробуйте ещё раз.", show_alert=True)


@router.callback_query(F.data == "restaurants:wa_same")
async def restaurants_wa_same(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RESTAURANTS_FLOW_STATE:
        await callback.answer()
        return

    data = await state.get_data()
    payload = dict(data.get("restaurants_schema_payload", {}))
    history = list(data.get("restaurants_schema_history", []))
    step_index = int(data.get("restaurants_schema_step_index", 0))
    schema, _ = _schema_and_entry_index()

    if step_index >= len(schema.steps):
        await callback.answer()
        return

    step = schema.steps[step_index]
    if getattr(step, "field_name", None) != "phone_whatsapp":
        await callback.answer()
        return

    phone_main = str(payload.get("phone_main") or "").strip()
    if not _valid_pt_mobile(phone_main):
        await callback.answer("Сначала укажите основной номер.", show_alert=True)
        return

    history = _history_push(history, step_index, payload)
    ctx = _make_ctx(payload)
    ctx.set_value("phone_whatsapp", phone_main)

    await _advance_after_ctx(callback.message, callback.from_user, state, schema, step_index, ctx, history)
    await callback.answer()


@router.callback_query(F.data == "restaurants:wa_none")
async def restaurants_wa_none(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RESTAURANTS_FLOW_STATE:
        await callback.answer()
        return

    data = await state.get_data()
    payload = dict(data.get("restaurants_schema_payload", {}))
    history = list(data.get("restaurants_schema_history", []))
    step_index = int(data.get("restaurants_schema_step_index", 0))
    schema, _ = _schema_and_entry_index()

    if step_index >= len(schema.steps):
        await callback.answer()
        return

    step = schema.steps[step_index]
    if getattr(step, "field_name", None) != "phone_whatsapp":
        await callback.answer()
        return

    history = _history_push(history, step_index, payload)
    ctx = _make_ctx(payload)
    ctx.set_value("phone_whatsapp", "нет")

    await _advance_after_ctx(callback.message, callback.from_user, state, schema, step_index, ctx, history)
    await callback.answer()


@router.message(F.text)
async def restaurants_schema_text_input(message: Message, state: FSMContext):
    current_state = await state.get_state()

    if current_state == RESTAURANTS_GEO_CUSTOM_STATE:
        raw = str(message.text or "").strip()
        if not raw.startswith("#"):
            await message.answer(
                "Введите геотеги в формате, например: #lisboa #cascais #online",
                reply_markup=get_back_button("restaurants:geo_back")
            )
            return

        data = await state.get_data()
        schema, _ = _schema_and_entry_index()
        geo_index = _find_step_index(schema, "geo_tags")
        payload = dict(data.get("restaurants_schema_payload", {}))
        history = list(data.get("restaurants_schema_history", []))

        ctx = _make_ctx(payload)
        ctx.set_value("geo_tags", raw)
        history = _history_push(history, geo_index, payload)

        await _advance_after_ctx(message, message.from_user, state, schema, geo_index, ctx, history)
        return

    if current_state != RESTAURANTS_FLOW_STATE:
        return

    data = await state.get_data()
    payload = dict(data.get("restaurants_schema_payload", {}))
    history = list(data.get("restaurants_schema_history", []))
    step_index = int(data.get("restaurants_schema_step_index", 0))

    try:
        schema, entry_index = _schema_and_entry_index()
        engine = SchemaEngine(schema)
        ctx = _make_ctx(payload)

        step = engine.get_step(step_index)
        field_name = getattr(step, "field_name", None)
        raw = str(message.text or "").strip()

        if step_index == entry_index and field_name == "resides_in_portugal":
            await message.answer(
                "Используйте кнопки «Да» или «Нет».",
                reply_markup=_restaurants_residency_keyboard()
            )
            return

        if field_name == "geo_tags":
            await _show_geo_selector(message, state, payload, history, edit=False)
            return

        if field_name == "social_links":
            if raw.lower() in {"нет", "no", "none", ""}:
                history = _history_push(history, step_index, payload)
                ctx.set_value("social_links", "нет")
                await _advance_after_ctx(message, message.from_user, state, schema, step_index, ctx, history)
                return

        if field_name == "reviews_links":
            if raw.lower() in {"нет", "no", "none", ""}:
                history = _history_push(history, step_index, payload)
                ctx.set_value("reviews_links", [])
                await _advance_after_ctx(message, message.from_user, state, schema, step_index, ctx, history)
                return

            review_links = _extract_valid_review_links(raw)
            if not review_links:
                await message.answer(
                    'Разрешены только ссылки из раздела <a href="https://t.me/proflistpt/12860/">Отзывы</a> Справочника',
                    reply_markup=_reviews_fast_keyboard(),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                return

            history = _history_push(history, step_index, payload)
            ctx.set_value("reviews_links", review_links)
            await _advance_after_ctx(message, message.from_user, state, schema, step_index, ctx, history)
            return

        if field_name == "phone_main":
            if not _valid_pt_mobile(raw):
                await message.answer(
                    "Неверный номер, перепроверьте",
                    reply_markup=get_back_button()
                )
                return

        if field_name == "phone_whatsapp":
            if raw.lower() in {"нет", "no", "none", ""}:
                history = _history_push(history, step_index, payload)
                ctx.set_value("phone_whatsapp", "нет")
                await _advance_after_ctx(message, message.from_user, state, schema, step_index, ctx, history)
                return

            if not _valid_pt_mobile(raw):
                await message.answer(
                    "Неверный номер, перепроверьте",
                    reply_markup=_whatsapp_fast_keyboard()
                )
                return

        if field_name == "telegram":
            username_value = _username_value(message.from_user)
            if not username_value:
                await state.clear()
                await message.answer(
                    "Для публикации в справочнике нужен Telegram username.\n\n"
                    "Создайте @username в настройках Telegram и затем снова запустите публикацию.",
                    reply_markup=get_back_button("go:main")
                )
                return

            history = _history_push(history, step_index, payload)
            ctx.set_value("telegram", username_value)
            await _advance_after_ctx(message, message.from_user, state, schema, step_index, ctx, history)
            return

        result = engine.process_answer(step, raw, ctx)

        if not result.accepted:
            if field_name == "phone_whatsapp":
                reply_markup = _whatsapp_fast_keyboard()
            elif field_name == "social_links":
                reply_markup = _social_links_fast_keyboard()
            else:
                reply_markup = get_back_button()
            await message.answer(
                result.error_message or "Неверный ответ.",
                reply_markup=reply_markup
            )
            return

        if result.stop_flow:
            await state.clear()
            await message.answer(
                "Мы работаем с резидентами Португалии. Возвращайтесь после переезда.",
                reply_markup=get_back_button("go:main")
            )
            return

        history = _history_push(history, step_index, payload)
        await _advance_after_ctx(message, message.from_user, state, schema, step_index, ctx, history)

    except Exception as e:
        logger.exception("Restaurants schema flow failed: %s", e)
        await state.clear()
        await message.answer(
            "Ошибка при обработке формы. Вернитесь в меню и попробуйте снова.",
            reply_markup=get_back_button("go:main")
        )


@router.callback_query(F.data == "restaurants:premium")
async def restaurants_premium_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("restaurants_schema_active"):
        await callback.answer("Сессия публикации не найдена.")
        return

    payload = dict(data.get("restaurants_schema_payload", {}))
    history = list(data.get("restaurants_schema_history", []))

    await state.update_data(
        restaurants_schema_active=True,
        restaurants_schema_payload=payload,
        restaurants_schema_history=history,
        restaurants_premium_media=[],
        restaurants_premium_status_message_id=None,
        restaurants_premium_prompt_message_id=callback.message.message_id,
    )
    await state.set_state(RESTAURANTS_PREMIUM_MEDIA_STATE)

    await callback.message.edit_text(
        "Отправьте фото или видео для премиум-публикации. Можно отправить несколько сообщений подряд. Когда закончите, нажмите «Завершить загрузку медиа».",
        reply_markup=_premium_media_keyboard(),
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.message(F.photo | F.video)
async def restaurants_premium_media_input(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != RESTAURANTS_PREMIUM_MEDIA_STATE:
        return

    media_item = _media_payload_from_message(message)
    if not media_item:
        await _upsert_premium_media_status(
            message,
            state,
            "Поддерживаются только фото или видео.",
        )
        return

    data = await state.get_data()
    media_list = list(data.get("restaurants_premium_media", []))
    media_list.append(media_item)
    await state.update_data(restaurants_premium_media=media_list)

    await _upsert_premium_media_status(
        message,
        state,
        f"Добавлено файлов: {len(media_list)}",
    )


@router.callback_query(F.data == "restaurants:premium_cancel")
async def restaurants_premium_cancel(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payload = dict(data.get("restaurants_schema_payload", {}))

    await state.update_data(
        restaurants_premium_media=[],
        restaurants_premium_status_message_id=None,
        restaurants_premium_prompt_message_id=None,
    )
    await callback.message.edit_text(
        _confirmation_text(payload),
        reply_markup=_confirmation_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await state.set_state("restaurants_schema_waiting_confirmation")
    await callback.answer()


@router.callback_query(F.data == "restaurants:premium_submit")
async def restaurants_premium_submit(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != RESTAURANTS_PREMIUM_MEDIA_STATE:
        await callback.answer()
        return

    data = await state.get_data()
    payload = dict(data.get("restaurants_schema_payload", {}))
    media_list = list(data.get("restaurants_premium_media", []))

    if not media_list:
        await callback.answer("Сначала добавьте хотя бы одно фото или видео.", show_alert=True)
        return

    media_file_id = media_list[0]["file_id"]
    media_type = media_list[0]["type"]

    user = db.get_user(callback.from_user.id)
    if not user:
        internal_user_id = db.create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
        )
    else:
        internal_user_id = user["id"]

    premium_post_id = db.create_premium_post(
        user_id=internal_user_id,
        mode="restaurants",
        cities=_normalize_geo_tags_for_db(payload.get("geo_tags")),
        description=payload.get("description", ""),
        social_media=payload.get("social_links", ""),
        telegram_username=payload.get("telegram", ""),
        phone_main=payload.get("phone_main", ""),
        phone_whatsapp=payload.get("phone_whatsapp", ""),
        name=payload.get("contact_name", ""),
        section="Рестораны",
        media_file_id=media_file_id,
        media_type=media_type,
        media_list=json.dumps(media_list, ensure_ascii=False),
    )

    await _premium_notify_admin(callback.bot, premium_post_id, payload, media_list)

    await state.clear()
    await callback.message.edit_text(
        "Премиум-заявка отправлена на модерацию. После одобрения объявление появится в справочнике.",
        reply_markup=get_back_button("go:main"),
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data == "confirm:restaurants_post")
async def handle_restaurants_schema_confirmation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if not data.get("restaurants_schema_active"):
        await callback.answer("Сессия публикации не найдена.")
        return

    payload = data.get("restaurants_schema_payload", {})

    try:
        registry = load_sections_registry()
        channel_id = int(registry.channel_id or Config.CHANNEL_ID)
        topic_id = int(registry.get_topic_id("Рестораны"))

        published_message = await callback.bot.send_message(
            chat_id=channel_id,
            text=_render_html(payload),
            message_thread_id=topic_id,
            disable_web_page_preview=True,
            parse_mode="HTML"
        )

        await state.clear()

        try:
            chat_info = await callback.bot.get_chat(channel_id)
            if chat_info.username:
                message_link = f"https://t.me/{chat_info.username}/{published_message.message_id}"
            else:
                message_link = None
        except Exception as e:
            logger.warning("Could not get channel info: %s", e)
            message_link = None

        success_text = f"Объявление опубликовано. Ссылка: {message_link}" if message_link else "Объявление опубликовано."
        await callback.message.edit_text(success_text, reply_markup=get_back_button("go:main"))
        await callback.answer()

    except Exception as e:
        logger.exception("Failed to publish restaurants schema posting: %s", e)
        await state.clear()
        await callback.message.edit_text(
            "Ошибка при публикации объявления. Попробуйте позже.",
            reply_markup=get_back_button("go:main")
        )
        await callback.answer()
