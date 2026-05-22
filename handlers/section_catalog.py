# SECTION_CATALOG_BUTTON_DATA_FIX_V2_APPLIED
from __future__ import annotations

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.section_catalog import load_section_catalog
from handlers.reviews_schema_flow import rv_entry

logger = logging.getLogger(__name__)
router = Router()

ACTIVE_SECTION_CALLBACKS = {
    "Ищу работу":                    "section:generic:job_seeker",
    "Предлагаю работу":              "section:generic:job_offer",
    "Рестораны":                     "section:generic:restaurants",
    # generic sections
    "Ищу жильё":                     "section:housing:housing_wanted",
    "Недвижимость от хозяев":        "section:housing:owner_real_estate",
    "Риелторы":                      "section:generic:realtors",
    "Строительство и ремонт":        "section:generic:construction_repair",
    "Бытовой ремонт и обустройство": "section:generic:home_repair",
    "Ремонт техники":                "section:generic:device_repair",
    "Мебель изготовление":           "section:generic:furniture",
    "Клининг":                       "section:generic:cleaning",
    "Домашний персонал":             "section:generic:home_staff",
    "Пошив одежды":                  "section:generic:tailoring",
    "Кулинария":                     "section:generic:cooking",
    "Пассажирские перевозки":        "section:generic:passenger_transport",
    "Грузовые перевозки":            "section:generic:cargo_transport",
    "Прокат авто":                   "section:generic:car_rental",
    "Автосервис":                    "section:generic:auto_service",
    "Переводчики":                   "section:generic:translators",
    "ВНЖ/Юристы":                   "section:generic:residence_lawyers",
    "Маркетинг":                     "section:generic:marketing",
    "IT/SMM":                        "section:generic:it_smm",
    "Деньги/кредиты":                "section:generic:money_credit",
    "Страхование":                   "section:generic:insurance",
    "Бухгалтеры":                    "section:generic:accountants",
    "Полиграфия":                    "section:generic:printing",
    "Здоровье":                      "section:generic:health",
    "Медицина":                      "section:generic:medicine",
    "Красота":                       "section:generic:beauty",
    "Преподавание":                  "section:generic:teaching",
    "Спорт":                         "section:generic:sport",
    "Животные":                      "section:generic:animals",
    "Отдых":                         "section:generic:leisure",
    "Туризм":                        "section:generic:tourism",
    "Фото/видео":                    "section:generic:photo_video",
    "Искусство":                     "section:generic:art",
    "Отзывы":                        "section:reviews",
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
