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


def get_back_button(back_to: str = "go:main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Назад", callback_data=back_to))
    return builder.as_markup()


def _next_prompt(schema, next_index: int) -> tuple[int, str]:
    prompts = []
    idx = next_index

    while idx < len(schema.steps) and schema.steps[idx].kind == "info":
        prompts.append(schema.steps[idx].prompt)
        idx += 1

    if idx < len(schema.steps):
        prompts.append(schema.steps[idx].prompt)

    return idx, "\n\n".join([p for p in prompts if p])


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
    await state.set_state("restaurants_schema_waiting_input")

    prompt_text = schema.steps[step_index].prompt

    if is_callback:
        await target.message.edit_text(prompt_text, reply_markup=get_back_button("go:main"))
        await target.answer()
    else:
        await target.answer(prompt_text, reply_markup=get_back_button("go:main"))


@router.message(Command("restaurants"))
async def start_restaurants_schema_command(message: Message, state: FSMContext):
    await _start_flow(message, state, is_callback=False)


@router.callback_query(F.data == "section:restaurants")
async def start_restaurants_schema_callback(callback: CallbackQuery, state: FSMContext):
    await _start_flow(callback, state, is_callback=True)


@router.message(F.text)
async def restaurants_schema_text_input(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "restaurants_schema_waiting_input":
        return

    data = await state.get_data()
    payload = data.get("restaurants_schema_payload", {})
    step_index = int(data.get("restaurants_schema_step_index", 0))

    try:
        schema = build_schema_registry().get_by_section("Рестораны")
        engine = SchemaEngine(schema)
        ctx = PostingContext(section_name="Рестораны")

        for key, value in payload.items():
            ctx.set_value(key, value)

        step = engine.get_step(step_index)
        result = engine.process_answer(step, message.text, ctx)

        if not result.accepted:
            await message.answer(
                result.error_message or "Неверный ответ.",
                reply_markup=get_back_button("go:main")
            )
            return

        if result.stop_flow:
            await state.clear()
            await message.answer(
                "Мы работаем с резидентами Португалии. Возвращайтесь после переезда.",
                reply_markup=get_back_button("go:main")
            )
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
            builder.add(InlineKeyboardButton(text="Назад", callback_data="go:main"))
            builder.adjust(1)

            await message.answer(
                _confirmation_text(ctx.data),
                reply_markup=builder.as_markup()
            )
            await state.set_state("restaurants_schema_waiting_confirmation")
            return

        await message.answer(
            next_prompt,
            reply_markup=get_back_button("go:main")
        )
        await state.set_state("restaurants_schema_waiting_input")

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
