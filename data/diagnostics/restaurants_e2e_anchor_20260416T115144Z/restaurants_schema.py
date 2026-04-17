from __future__ import annotations

import html
import logging

from aiogram import Router, F
from aiogram.filters import Command
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

RESTAURANTS_FLOW_STATE = "restaurants_schema_waiting_input"
RESTAURANTS_GEO_CUSTOM_STATE = "restaurants_schema_waiting_custom_geo"

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
    builder.add(InlineKeyboardButton(text="Назад", callback_data=back_to))
    return builder.as_markup()


def _restaurants_residency_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Да", callback_data="restaurants:residency:yes"))
    builder.add(InlineKeyboardButton(text="Нет", callback_data="restaurants:residency:no"))
    builder.add(InlineKeyboardButton(text="Назад", callback_data="go:main"))
    builder.adjust(2, 1)
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
    builder.add(InlineKeyboardButton(text="Назад", callback_data="restaurants:back"))
    builder.adjust(1)
    return builder.as_markup()


def _social_links_fast_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Ссылок нет", callback_data="restaurants:social_none"))
    builder.add(InlineKeyboardButton(text="Назад", callback_data="restaurants:back"))
    builder.adjust(1)
    return builder.as_markup()


def _confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Опубликовать", callback_data="confirm:restaurants_post"))
    builder.add(InlineKeyboardButton(text="Назад", callback_data="restaurants:back"))
    builder.adjust(1)
    return builder.as_markup()


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
    geo_tags = str(payload.get("geo_tags") or "").strip()
    description = str(payload.get("description") or "").strip()
    social_links = str(payload.get("social_links") or "").strip()
    telegram = str(payload.get("telegram") or "").strip()
    phone_main = str(payload.get("phone_main") or "").strip()
    phone_whatsapp = str(payload.get("phone_whatsapp") or "").strip()
    contact_name = str(payload.get("contact_name") or "").strip()

    lines = ["Проверьте объявление перед публикацией:", ""]

    if geo_tags:
        lines.append(geo_tags)
    if description:
        lines.append(description)
    if social_links and social_links.lower() not in {"нет", "no", "none"}:
        lines.append(social_links)
    if telegram:
        lines.append(telegram)
    if phone_main:
        lines.append(phone_main)
    if phone_whatsapp and phone_whatsapp.lower() not in {"нет", "no", "none"} and phone_whatsapp != phone_main:
        lines.append(phone_whatsapp)
    if contact_name:
        lines.append(f"- {contact_name}")

    return "\n".join(lines).strip()


def _render_html(payload: dict) -> str:
    geo_tags = str(payload.get("geo_tags") or "").strip()
    description = str(payload.get("description") or "").strip()
    social_links = str(payload.get("social_links") or "").strip()
    telegram = str(payload.get("telegram") or "").strip()
    phone_main = str(payload.get("phone_main") or "").strip()
    phone_whatsapp = str(payload.get("phone_whatsapp") or "").strip()
    contact_name = str(payload.get("contact_name") or "").strip()

    lines = []

    if geo_tags:
        lines.append(html.escape(geo_tags))
    if description:
        lines.append(html.escape(description))
    if social_links and social_links.lower() not in {"нет", "no", "none"}:
        lines.append(html.escape(social_links))
    if telegram:
        lines.append(html.escape(telegram))
    if phone_main:
        lines.append(html.escape(phone_main))
    if phone_whatsapp and phone_whatsapp.lower() not in {"нет", "no", "none"} and phone_whatsapp != phone_main:
        lines.append(html.escape(phone_whatsapp))
    if contact_name:
        lines.append(html.escape(f"- {contact_name}"))

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
                disable_web_page_preview=True,
            )
        else:
            await target_message.answer(
                _confirmation_text(payload),
                reply_markup=_confirmation_keyboard(),
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

    text = "Выберите город, где работает ваш бизнес. 

Можно указать несколько городов через запятую или #online:"
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
