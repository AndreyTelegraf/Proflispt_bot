# SECTION_CATALOG_BUTTON_DATA_FIX_V2_APPLIED
from __future__ import annotations

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.section_catalog import load_section_catalog
from services.catalog_modes import MODE_TO_SECTION_NAME
from handlers.reviews_schema_flow import rv_entry

logger = logging.getLogger(__name__)
router = Router()

ACTIVE_SECTION_CALLBACKS = {
    **{
        section_name: f"section:generic:{slug}"
        for slug, section_name in MODE_TO_SECTION_NAME.items()
    },
    "Ищу жильё": "section:housing:housing_wanted",
    "Недвижимость от хозяев": "section:housing:owner_real_estate",
    "Отзывы": "section:reviews",
}


def _groups_keyboard() -> InlineKeyboardMarkup:
    catalog = load_section_catalog()
    builder = InlineKeyboardBuilder()

    for group in catalog.list_groups():
        builder.add(
            InlineKeyboardButton(
                text=f"{group.title} ›",
                callback_data=f"catalog:group:{group.key}",
            )
        )

    builder.add(InlineKeyboardButton(text="← Назад", callback_data="go:main"))
    builder.adjust(1)
    return builder.as_markup()


def _sections_keyboard(group_key: str) -> InlineKeyboardMarkup:
    catalog = load_section_catalog()
    group = catalog.get_group(group_key)
    builder = InlineKeyboardBuilder()

    for section_name in group.sections:
        active_callback = ACTIVE_SECTION_CALLBACKS.get(section_name)
        if active_callback:
            builder.add(
                InlineKeyboardButton(
                    text=section_name,
                    callback_data=active_callback,
                )
            )
        else:
            builder.add(
                InlineKeyboardButton(
                    text=f"{section_name} [скоро]",
                    callback_data="catalog:inactive",
                )
            )

    for btn in group.extra_buttons:
        builder.add(InlineKeyboardButton(text=btn["title"], url=btn["url"]))

    builder.add(InlineKeyboardButton(text="← Назад", callback_data="catalog:groups"))
    builder.adjust(1)
    return builder.as_markup()


CATALOG_INTRO_TEXT = (
    "Сначала выберите группу, в которой находится нужный вам раздел:"
)


@router.message(Command("sections"))
async def cmd_sections(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(CATALOG_INTRO_TEXT, reply_markup=_groups_keyboard())


@router.callback_query(F.data == "catalog:groups")
async def cb_catalog_groups(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(CATALOG_INTRO_TEXT, reply_markup=_groups_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("catalog:group:"))
async def cb_catalog_group(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    group_key = callback.data.split(":", 2)[2]

    if group_key == "reviews":
        await rv_entry(callback, state)
        return

    catalog = load_section_catalog()
    group = catalog.get_group(group_key)

    text = f"Группа: {group.title}\n\nТеперь выберите подходящий вам раздел:"
    await callback.message.edit_text(text, reply_markup=_sections_keyboard(group_key))
    await callback.answer()


@router.callback_query(F.data == "catalog:inactive")
async def cb_catalog_inactive(callback: CallbackQuery):
    await callback.answer("Этот раздел пока подключается.", show_alert=True)
