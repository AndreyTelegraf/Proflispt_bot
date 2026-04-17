from __future__ import annotations

import html
import logging

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from models.posting_context import PostingContext
from services.schema_bootstrap import build_schema_registry
from services.schema_engine import SchemaEngine
from services.sections_registry import load_sections_registry

logger = logging.getLogger(__name__)
router = Router()

STATE_INPUT = "restaurants_schema_waiting_input"
STATE_CONFIRM = "restaurants_schema_waiting_confirmation"
STATE_GEO_CUSTOM = "restaurants_schema_waiting_custom_geo"
STATE_TELEGRAM_REQUIRED = "restaurants_schema_waiting_telegram_required"


def get_back_button(back_to: str = "restaurants:back") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="← Назад", callback_data=back_to))
    return builder.as_markup()


def _choice_keyboard(step, back_to: str = "restaurants:back") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    field_name = getattr(step, "field_name", "")
    is_geo = field_name == "geo_tags"
    is_residency = field_name == "resides_in_portugal"

    for opt in getattr(step, "options", []) or []:
        value = str(opt.get("value", "")).strip()
        if not value:
            continue
        label = str(opt.get("label") or {
            "yes": "Да",
            "no": "Нет",
        }.get(value.lower(), value)).strip()
        builder.add(InlineKeyboardButton(text=label, callback_data=f"restaurants:choice:{value}"))

    if not is_residency:
        builder.add(InlineKeyboardButton(text="← Назад", callback_data=back_to))

    if is_geo:
        builder.adjust(3, 3, 3, 2, 1)
    elif is_residency:
        builder.adjust(2)
    else:
        builder.adjust(2, 1)

    return builder.as_markup()




def _social_links_fast_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Ссылок нет", callback_data="restaurants:social_none"))
    builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
    builder.adjust(1)
    return builder.as_markup()

def _whatsapp_fast_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Совпадает с основным", callback_data="restaurants:wa_same"))
    builder.add(InlineKeyboardButton(text="Нет WhatsApp", callback_data="restaurants:wa_none"))
    builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
    builder.adjust(1)
    return builder.as_markup()

def _step_reply_markup(step, *, back_to: str = "restaurants:back") -> InlineKeyboardMarkup:
    if getattr(step, "field_name", "") == "social_links":
        return _social_links_fast_keyboard()
    if getattr(step, "kind", None) == "choice":
        return _choice_keyboard(step, back_to=back_to)
    return get_back_button(back_to)



def _step_reply_markup(step, *, back_to: str = "restaurants:back") -> InlineKeyboardMarkup:
    if getattr(step, "field_name", "") == "phone_whatsapp":
        return _whatsapp_fast_keyboard()
    if getattr(step, "field_name", "") == "social_links":
        return _social_links_fast_keyboard()
    if getattr(step, "kind", None) == "choice":
        return _choice_keyboard(step, back_to=back_to)
    return get_back_button(back_to)

def _next_prompt(schema, next_index: int) -> tuple[int, str]:
    prompts = []
    idx = next_index

    while idx < len(schema.steps) and schema.steps[idx].kind == "info":
        prompts.append(schema.steps[idx].prompt)
        idx += 1

    if idx < len(schema.steps):
        prompts.append(schema.steps[idx].prompt)

    return idx, "\n\n".join([p for p in prompts if p])


def _find_step_index(schema, field_name: str):
    for idx, step in enumerate(schema.steps):
        if getattr(step, "field_name", None) == field_name:
            return idx
    return None


def _previous_interactive_index(schema, current_index: int):
    idx = current_index - 1
    while idx >= 0:
        step = schema.steps[idx]
        if getattr(step, "kind", None) == "info":
            idx -= 1
            continue
        if getattr(step, "field_name", None) == "telegram":
            idx -= 1
            continue
        return idx
    return None


def _confirmation_text(payload: dict) -> str:
    rows = [
        ("Название и адрес", payload.get("place_name_and_address")),
        ("Описание", payload.get("description")),
        ("Ссылки", payload.get("social_links")),
        ("Telegram", payload.get("telegram")),
        ("Телефон", payload.get("phone_main")),
        ("WhatsApp", payload.get("phone_whatsapp")),
        ("Контакт", payload.get("contact_name")),
    ]

    lines = ["Проверьте объявление перед публикацией:", "Раздел: Рестораны", ""]
    for label, value in rows:
        if value is None:
            continue
        clean = str(value).strip()
        if not clean:
            continue
        if clean.lower() in {"нет", "no", "none"} and label != "Описание":
            continue
        lines.append(f"{label}: {clean}")

    return "\n".join(lines).strip()


def _render_html(payload: dict) -> str:
    rows = [
        ("Название и адрес", payload.get("place_name_and_address")),
        ("Описание", payload.get("description")),
        ("Ссылки", payload.get("social_links")),
        ("Telegram", payload.get("telegram")),
        ("Телефон", payload.get("phone_main")),
        ("WhatsApp", payload.get("phone_whatsapp")),
        ("Контакт", payload.get("contact_name")),
    ]

    lines = ["<b>Рестораны</b>", ""]
    for label, value in rows:
        if value is None:
            continue
        clean = str(value).strip()
        if not clean:
            continue
        if clean.lower() in {"нет", "no", "none"} and label != "Описание":
            continue
        lines.append(f"<b>{html.escape(label)}:</b> {html.escape(clean)}")

    return "\n".join(lines).strip()


def _username_value(user):
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

def _telegram_username_required_text() -> str:
    return (
        "Для публикации в справочнике нужен Telegram username.\n\n"
        "Как создать @username в Telegram:\n"
        "1. Откройте Настройки.\n"
        "2. Зайдите в «Имя пользователя».\n"
        "3. Создайте и сохраните @username.\n\n"
        "После этого нажмите кнопку «@username создан»."
    )


def _telegram_username_required_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="@username создан", callback_data="restaurants:username_created"))
    builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
    builder.adjust(1)
    return builder.as_markup()


async def _go_after_telegram_gate(target, actor_user, state: FSMContext, schema, payload: dict, next_index: int):
    ctx = _make_ctx(payload)
    username_value = _username_value(actor_user)
    if not username_value:
        await state.set_state(STATE_TELEGRAM_REQUIRED)
        if hasattr(target, "edit_text"):
            await target.edit_text(
                _telegram_username_required_text(),
                reply_markup=_telegram_username_required_keyboard()
            )
        else:
            await target.answer(
                _telegram_username_required_text(),
                reply_markup=_telegram_username_required_keyboard()
            )
        return False, payload

    ctx.set_value("telegram", username_value)
    payload = ctx.data

    next_index, next_prompt = _next_prompt(schema, next_index + 1)

    await state.update_data(
        restaurants_schema_active=True,
        restaurants_schema_payload=payload,
        restaurants_schema_step_index=next_index,
    )

    if next_index >= len(schema.steps):
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="Опубликовать", callback_data="confirm:restaurants_post"))
        builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
        builder.adjust(1)
        if hasattr(target, "edit_text"):
            await target.edit_text(
                _confirmation_text(payload),
                reply_markup=builder.as_markup()
            )
        else:
            await target.answer(
                _confirmation_text(payload),
                reply_markup=builder.as_markup()
            )
        await state.set_state(STATE_CONFIRM)
        return False, payload

    next_step = schema.steps[next_index]
    if hasattr(target, "edit_text"):
        await target.edit_text(
            next_prompt,
            reply_markup=_step_reply_markup(next_step, back_to="restaurants:back")
        )
    else:
        await target.answer(
            next_prompt,
            reply_markup=_step_reply_markup(next_step, back_to="restaurants:back")
        )
    await state.set_state(STATE_INPUT)
    return False, payload


def _make_ctx(payload: dict) -> PostingContext:
    ctx = PostingContext(section_name="Рестораны")
    for key, value in (payload or {}).items():
        ctx.set_value(key, value)
    return ctx


async def _start_flow(target, state: FSMContext, is_callback: bool = False):
    schema = build_schema_registry().get_by_section("Рестораны")

    step_index = 0
    while step_index < len(schema.steps) and schema.steps[step_index].kind == "info":
        step_index += 1

    if step_index >= len(schema.steps):
        raise RuntimeError("restaurants schema has no interactive steps")

    await state.clear()
    await state.update_data(
        restaurants_schema_active=True,
        restaurants_schema_step_index=step_index,
        restaurants_schema_payload={},
    )
    await state.set_state(STATE_INPUT)

    step = schema.steps[step_index]
    prompt_text = step.prompt
    kb = _step_reply_markup(step, back_to="restaurants:back")

    if is_callback:
        await target.message.edit_text(prompt_text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(prompt_text, reply_markup=kb)


@router.message(Command("restaurants"))
async def start_restaurants_schema_command(message: Message, state: FSMContext):
    await _start_flow(message, state, is_callback=False)


@router.callback_query(F.data == "section:restaurants")
async def start_restaurants_schema_callback(callback: CallbackQuery, state: FSMContext):
    await _start_flow(callback, state, is_callback=True)



@router.callback_query(F.data == "restaurants:choice:custom")
async def restaurants_geo_custom_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("restaurants_schema_active"):
        await callback.answer()
        return

    await state.set_state(STATE_GEO_CUSTOM)
    await callback.message.edit_text(
        "Введите города вручную, например: #lisboa #setubal #algarve или #online",
        reply_markup=get_back_button("restaurants:back")
    )
    await callback.answer()

@router.callback_query(F.data == "restaurants:back")
async def restaurants_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("restaurants_schema_active"):
        await callback.answer()
        return

    schema = build_schema_registry().get_by_section("Рестораны")
    current_state = await state.get_state()
    current_index = int(data.get("restaurants_schema_step_index", 0))
    payload = data.get("restaurants_schema_payload", {})

    if current_state == STATE_GEO_CUSTOM:
        prev_index = _find_step_index(schema, "geo_tags")
    elif current_state == STATE_TELEGRAM_REQUIRED:
        prev_index = _find_step_index(schema, "social_links")
    elif current_state == STATE_CONFIRM:
        prev_index = _previous_interactive_index(schema, len(schema.steps))
    else:
        prev_index = _previous_interactive_index(schema, current_index)

    if prev_index is None:
        await callback.answer()
        return

    await state.update_data(
        restaurants_schema_payload=payload,
        restaurants_schema_step_index=prev_index,
    )
    await state.set_state(STATE_INPUT)

    step = schema.steps[prev_index]
    await callback.message.edit_text(
        step.prompt,
        reply_markup=_step_reply_markup(step, back_to="restaurants:back")
    )
    await callback.answer()


@router.message(F.text, StateFilter(STATE_GEO_CUSTOM))
async def restaurants_geo_custom_input(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != STATE_GEO_CUSTOM:
        return

    raw = str(message.text or "").strip()
    if not raw:
        await message.answer(
            "Введите хотя бы один город или тег, например: #lisboa #porto #online",
            reply_markup=get_back_button("restaurants:back")
        )
        return

    data = await state.get_data()
    payload = data.get("restaurants_schema_payload", {})
    step_index = int(data.get("restaurants_schema_step_index", 0))

    schema = build_schema_registry().get_by_section("Рестораны")
    ctx = _make_ctx(payload)
    ctx.set_value("geo_tags", raw)

    next_index, next_prompt = _next_prompt(schema, step_index + 1)

    await state.update_data(
        restaurants_schema_payload=ctx.data,
        restaurants_schema_step_index=next_index,
    )

    if next_index >= len(schema.steps):
        b = InlineKeyboardBuilder()
        b.add(InlineKeyboardButton(text="Опубликовать", callback_data="confirm:restaurants_post"))
        b.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
        b.adjust(1)
        await message.answer(
            _confirmation_text(ctx.data),
            reply_markup=b.as_markup()
        )
        await state.set_state(STATE_CONFIRM)
        return

    next_step = schema.steps[next_index]
    await message.answer(
        next_prompt,
        reply_markup=_step_reply_markup(next_step, back_to="restaurants:back")
    )
    await state.set_state(STATE_INPUT)


@router.callback_query(F.data.startswith("restaurants:choice:"))
async def restaurants_schema_choice_input(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != STATE_INPUT:
        await callback.answer()
        return

    data = await state.get_data()
    if not data.get("restaurants_schema_active"):
        await callback.answer()
        return

    payload = data.get("restaurants_schema_payload", {})
    step_index = int(data.get("restaurants_schema_step_index", 0))
    raw_value = callback.data.split(":", 2)[2]

    try:
        schema = build_schema_registry().get_by_section("Рестораны")
        engine = SchemaEngine(schema)
        ctx = _make_ctx(payload)

        step = engine.get_step(step_index)
        result = engine.process_answer(step, raw_value, ctx)

        if not result.accepted:
            await callback.answer(result.error_message or "Неверный ответ.", show_alert=True)
            return

        if result.stop_flow:
            await state.clear()
            await callback.message.edit_text(
                "Справочник работает только с резидентами Португалии.",
                reply_markup=get_back_button("go:main")
            )
            await callback.answer()
            return

        next_index, next_prompt = _next_prompt(schema, step_index + 1)

        await state.update_data(
            restaurants_schema_active=True,
            restaurants_schema_payload=ctx.data,
            restaurants_schema_step_index=next_index,
        )

        if next_index >= len(schema.steps):
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="Опубликовать", callback_data="confirm:restaurants_post"))
            builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
            builder.adjust(1)

            await callback.message.edit_text(
                _confirmation_text(ctx.data),
                reply_markup=builder.as_markup()
            )
            await state.set_state(STATE_CONFIRM)
            await callback.answer()
            return

        next_step = schema.steps[next_index]
        await callback.message.edit_text(
            next_prompt,
            reply_markup=_step_reply_markup(next_step, back_to="restaurants:back")
        )
        await state.set_state(STATE_INPUT)
        await callback.answer()

    except Exception as e:
        logger.exception("Restaurants schema choice flow failed: %s", e)
        await state.clear()
        await callback.message.edit_text(
            "Ошибка при обработке формы. Вернитесь в меню и попробуйте снова.",
            reply_markup=get_back_button("restaurants:back")
        )
        await callback.answer()




@router.callback_query(F.data == "restaurants:wa_same")
async def restaurants_wa_same(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("restaurants_schema_active"):
        await callback.answer()
        return

    payload = data.get("restaurants_schema_payload", {})
    step_index = int(data.get("restaurants_schema_step_index", 0))

    phone_main = str(payload.get("phone_main") or "").strip()
    if not _valid_pt_mobile(phone_main):
        await callback.answer("Сначала укажите корректный основной номер.", show_alert=True)
        return

    schema = build_schema_registry().get_by_section("Рестораны")
    ctx = _make_ctx(payload)
    ctx.set_value("phone_whatsapp", phone_main)

    next_index, next_prompt = _next_prompt(schema, step_index + 1)

    await state.update_data(
        restaurants_schema_payload=ctx.data,
        restaurants_schema_step_index=next_index,
    )

    if next_index >= len(schema.steps):
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="Опубликовать", callback_data="confirm:restaurants_post"))
        builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
        builder.adjust(1)
        await callback.message.edit_text(
            _confirmation_text(ctx.data),
            reply_markup=builder.as_markup()
        )
        await state.set_state(STATE_CONFIRM)
        await callback.answer()
        return

    next_step = schema.steps[next_index]
    await callback.message.edit_text(
        next_prompt,
        reply_markup=_step_reply_markup(next_step, back_to="restaurants:back")
    )
    await state.set_state(STATE_INPUT)
    await callback.answer()

@router.callback_query(F.data == "restaurants:wa_none")
async def restaurants_wa_none(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("restaurants_schema_active"):
        await callback.answer()
        return

    payload = data.get("restaurants_schema_payload", {})
    step_index = int(data.get("restaurants_schema_step_index", 0))

    schema = build_schema_registry().get_by_section("Рестораны")
    ctx = _make_ctx(payload)
    ctx.set_value("phone_whatsapp", "нет")

    next_index, next_prompt = _next_prompt(schema, step_index + 1)

    await state.update_data(
        restaurants_schema_payload=ctx.data,
        restaurants_schema_step_index=next_index,
    )

    if next_index >= len(schema.steps):
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="Опубликовать", callback_data="confirm:restaurants_post"))
        builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
        builder.adjust(1)
        await callback.message.edit_text(
            _confirmation_text(ctx.data),
            reply_markup=builder.as_markup()
        )
        await state.set_state(STATE_CONFIRM)
        await callback.answer()
        return

    next_step = schema.steps[next_index]
    await callback.message.edit_text(
        next_prompt,
        reply_markup=_step_reply_markup(next_step, back_to="restaurants:back")
    )
    await state.set_state(STATE_INPUT)
    await callback.answer()

@router.callback_query(F.data == "restaurants:username_created")
async def restaurants_username_created(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payload = data.get("restaurants_schema_payload", {})

    schema = build_schema_registry().get_by_section("Рестораны")
    telegram_index = _find_step_index(schema, "telegram")
    if telegram_index is None:
        await callback.answer("Шаг Telegram не найден.", show_alert=True)
        return

    username_value = _username_value(callback.from_user)
    if not username_value:
        await callback.answer("Telegram username пока не найден. Сначала создайте его в настройках.", show_alert=True)
        return

    ctx = _make_ctx(payload)
    ctx.set_value("telegram", username_value)

    next_index, next_prompt = _next_prompt(schema, telegram_index + 1)

    await state.update_data(
        restaurants_schema_active=True,
        restaurants_schema_payload=ctx.data,
        restaurants_schema_step_index=next_index,
    )

    if next_index >= len(schema.steps):
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="Опубликовать", callback_data="confirm:restaurants_post"))
        builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
        builder.adjust(1)
        await callback.message.edit_text(
            _confirmation_text(ctx.data),
            reply_markup=builder.as_markup()
        )
        await state.set_state(STATE_CONFIRM)
        await callback.answer()
        return

    next_step = schema.steps[next_index]
    await callback.message.edit_text(
        next_prompt,
        reply_markup=_step_reply_markup(next_step, back_to="restaurants:back")
    )
    await state.set_state(STATE_INPUT)
    await callback.answer()


@router.callback_query(F.data == "restaurants:social_none")
async def restaurants_social_none(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("restaurants_schema_active"):
        await callback.answer()
        return

    payload = data.get("restaurants_schema_payload", {})
    step_index = int(data.get("restaurants_schema_step_index", 0))

    schema = build_schema_registry().get_by_section("Рестораны")
    ctx = _make_ctx(payload)
    ctx.set_value("social_links", "нет")
    payload = ctx.data

    next_index, next_prompt = _next_prompt(schema, step_index + 1)

    if next_index < len(schema.steps):
        next_step = schema.steps[next_index]
        if getattr(next_step, "field_name", None) == "telegram":
            await _go_after_telegram_gate(callback.message, callback.from_user, state, schema, payload, next_index)
            await callback.answer()
            return

    await state.update_data(
        restaurants_schema_payload=payload,
        restaurants_schema_step_index=next_index,
    )

    if next_index >= len(schema.steps):
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="Опубликовать", callback_data="confirm:restaurants_post"))
        builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
        builder.adjust(1)
        await callback.message.edit_text(
            _confirmation_text(payload),
            reply_markup=builder.as_markup()
        )
        await state.set_state(STATE_CONFIRM)
        await callback.answer()
        return

    next_step = schema.steps[next_index]
    await callback.message.edit_text(
        next_prompt,
        reply_markup=_step_reply_markup(next_step, back_to="restaurants:back")
    )
    await state.set_state(STATE_INPUT)
    await callback.answer()


@router.message(F.text)
async def restaurants_schema_text_input(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != STATE_INPUT:
        return

    data = await state.get_data()
    payload = data.get("restaurants_schema_payload", {})
    step_index = int(data.get("restaurants_schema_step_index", 0))

    try:
        schema = build_schema_registry().get_by_section("Рестораны")
        engine = SchemaEngine(schema)
        ctx = _make_ctx(payload)

        step = engine.get_step(step_index)
        field_name = getattr(step, "field_name", None)
        raw = str(message.text or "").strip()

        if field_name == "phone_main":
            if not _valid_pt_mobile(raw):
                await message.answer(
                    "Неверный номер, перепроверьте",
                    reply_markup=get_back_button("restaurants:back")
                )
                return

        if field_name == "phone_whatsapp":
            if raw.lower() in {"нет", "no", "none", ""}:
                ctx.set_value("phone_whatsapp", "нет")
                next_index, next_prompt = _next_prompt(schema, step_index + 1)

                await state.update_data(
                    restaurants_schema_active=True,
                    restaurants_schema_payload=ctx.data,
                    restaurants_schema_step_index=next_index,
                )

                if next_index >= len(schema.steps):
                    builder = InlineKeyboardBuilder()
                    builder.add(InlineKeyboardButton(text="Опубликовать", callback_data="confirm:restaurants_post"))
                    builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
                    builder.adjust(1)
                    await message.answer(
                        _confirmation_text(ctx.data),
                        reply_markup=builder.as_markup()
                    )
                    await state.set_state(STATE_CONFIRM)
                    return

                next_step = schema.steps[next_index]
                await message.answer(
                    next_prompt,
                    reply_markup=_step_reply_markup(next_step, back_to="restaurants:back")
                )
                await state.set_state(STATE_INPUT)
                return

            if not _valid_pt_mobile(raw):
                await message.answer(
                    "Неверный номер, перепроверьте",
                    reply_markup=_whatsapp_fast_keyboard()
                )
                return

        if field_name == "telegram":
            await _go_after_telegram_gate(message, message.from_user, state, schema, payload, step_index)
            return

        if getattr(step, "kind", None) == "choice":
            await message.answer(
                "Используйте кнопки ниже.",
                reply_markup=_choice_keyboard(step, back_to="restaurants:back")
            )
            return

        result = engine.process_answer(step, raw, ctx)

        if not result.accepted:
            await message.answer(
                result.error_message or "Неверный ответ.",
                reply_markup=_step_reply_markup(step, back_to="restaurants:back")
            )
            return

        if result.stop_flow:
            await state.clear()
            await message.answer(
                "Мы работаем с резидентами Португалии. Возвращайтесь после переезда.",
                reply_markup=get_back_button("restaurants:back")
            )
            return

        payload = ctx.data
        next_index, next_prompt = _next_prompt(schema, step_index + 1)

        if next_index < len(schema.steps):
            next_step = schema.steps[next_index]
            if getattr(next_step, "field_name", None) == "telegram":
                await _go_after_telegram_gate(message, message.from_user, state, schema, payload, next_index)
                return

        await state.update_data(
            restaurants_schema_active=True,
            restaurants_schema_payload=payload,
            restaurants_schema_step_index=next_index,
        )

        if next_index >= len(schema.steps):
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="Опубликовать", callback_data="confirm:restaurants_post"))
            builder.add(InlineKeyboardButton(text="← Назад", callback_data="restaurants:back"))
            builder.adjust(1)

            await message.answer(
                _confirmation_text(payload),
                reply_markup=builder.as_markup()
            )
            await state.set_state(STATE_CONFIRM)
            return

        next_step = schema.steps[next_index]
        await message.answer(
            next_prompt,
            reply_markup=_step_reply_markup(next_step, back_to="restaurants:back")
        )
        await state.set_state(STATE_INPUT)

    except Exception as e:
        logger.exception("Restaurants schema flow failed: %s", e)
        await state.clear()
        await message.answer(
            "Ошибка при обработке формы. Вернитесь в меню и попробуйте снова.",
            reply_markup=get_back_button("restaurants:back")
        )

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
        await callback.message.edit_text(success_text, reply_markup=get_back_button("restaurants:back"))
        await callback.answer()

    except Exception as e:
        logger.exception("Failed to publish restaurants schema posting: %s", e)
        await state.clear()
        await callback.message.edit_text(
            "Ошибка при публикации объявления. Попробуйте позже.",
            reply_markup=get_back_button("restaurants:back")
        )
        await callback.answer()
