"""Start handler for Work in Portugal Bot."""

import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import db
from keyboards.main import get_main_menu

logger = logging.getLogger(__name__)
router = Router()


def _main_menu_text() -> str:
    return (
        "Здравствуйте!\n\n"
        "Этот бот поможет вам опубликовать объявления в разделы Справочника.\n\n"
        "Выберите действие:"
    )


def _help_keyboard(back_to: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Правила", callback_data="help:rules")],
            [InlineKeyboardButton(text="Поговорить с человеком", url="https://t.me/andreytelegraf")],
            [InlineKeyboardButton(text="← Назад", callback_data=back_to)],
        ]
    )


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    db.create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    logger.info("User %s started bot", message.from_user.id)
    await message.answer(_main_menu_text(), reply_markup=get_main_menu())


@router.callback_query(F.data == "go:main")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(_main_menu_text(), reply_markup=get_main_menu())
    await callback.answer()


@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    help_text = (
        "Удалить объявление можно через раздел \"Мои объявления\" в главном меню.\n\n"
        "В случае неполадок:"
    )
    await callback.message.edit_text(help_text, reply_markup=_help_keyboard("go:main"))
    await callback.answer()


@router.callback_query(F.data == "help:rules")
async def show_rules(callback: CallbackQuery):
    rules_text = (
        "Правила публикации\n\n"
        "Общие правила:\n"
        "- Одно объявление не чаще раза в месяц\n"
        "- Максимум 3 активных объявления на пользователя\n"
        "- Объявления автоматически удаляются через 30 дней\n\n"
        "Формат объявления:\n"
        "- Хештеги городов (#lisboa, #porto, #online)\n"
        "- Описание работы (минимум 10 символов)\n"
        "- Социальные сети (или 'нет')\n"
        "- Telegram username\n"
        "- Телефон (+35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx)\n"
        "- WhatsApp (если отличается)\n"
        "- Имя/название компании\n\n"
        "Для работодателей:\n"
        "- Несколько вакансий — одно объявление\n"
        "- Новые вакансии — редактирование существующего\n"
        "- Запрещено дублирование вакансий"
    )
    await callback.message.edit_text(rules_text, reply_markup=_help_keyboard("help"))
    await callback.answer()


@router.callback_query(F.data == "help:support")
async def show_support(callback: CallbackQuery):
    help_text = (
        "Удалить объявление можно через раздел \"Мои объявления\" в главном меню.\n\n"
        "В случае неполадок:"
    )
    await callback.message.edit_text(help_text, reply_markup=_help_keyboard("go:main"))
    await callback.answer()
