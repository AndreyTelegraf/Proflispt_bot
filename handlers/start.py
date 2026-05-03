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
        "Если сомневаетесь, куда публиковать объявление, напишите администратору."
    )
    await callback.message.edit_text(help_text, reply_markup=_help_keyboard("go:main"))
    await callback.answer()


@router.callback_query(F.data == "help:rules")
async def show_rules(callback: CallbackQuery):
    rules_text = (
        "📜 <b>Правила:</b>\n"
        "- Выбирайте правильный раздел, это влияет на видимость объявления.\n"
        "- Описание должно чётко объяснять, что вы предлагаете или ищете.\n"
        "- Контакты в описании указывать не нужно, бот запросит их отдельно.\n"
        "\n"
        "💰 <b>Форматы размещения:</b>\n"
        "- Стандартная публикация — без медиа, только ссылки и отзывы.\n"
        "- Пост с медиа (€20) — до 10 фото/видео.\n"
        "- Поднять (€10) — делает объявление самым свежим в разделе и заменяет старую версию.\n"
        "- Закреп (€5) — фиксирует объявление в шапке раздела на 24 часа и уведомляет всех пользователей Справочника.\n"
        "\n"
        "🗑 <b>Удаление:</b>\n"
        "- Для поддержания актуальности объявления удаляются автоматически через 30 или 90 дней в зависимости от раздела.\n"
        "- Бот дважды предупреждает подателей о необходимости бесплатного подъёма или новой публикации.\n"
        "- Самостоятельно удалить объявление можно через раздел «Мои объявления».\n"
        "\n"
        "✏️ <b>Редактирование:</b>\n"
        "- В течение 6 часов после первой публикации объявление можно редактировать через удаление и повторную публикацию без ограничений.\n"
        "- Если объявление активно, создать дубликат нельзя — сначала удалите текущее объявление.\n"
        "- Через 6 часов после первой публикации повторная бесплатная публикация той же связки будет заблокирована на 30 дней.\n"
        "\n"
        "📊 <b>Лимиты:</b>\n"
        "- Посты с медиа, подъёмы и закрепы — без ограничений.\n"
        "- Посты без медиа: до 5 объявлений в одном разделе и до 10 объявлений во всём Справочнике за 30 дней.\n"
        "- Лимиты считаются по пользователю, разделу и номеру телефона.\n"
        "- Удаление объявления не сбрасывает месячные лимиты.\n"
        "\n"
        "⚠️ <b>Модерация:</b>\n"
        "- Запрещён спам, дубли и вводящая в заблуждение информация.\n"
        "- Посты с нарушениями удаляются, частые нарушения могут привести к бану."
    )
    await callback.message.edit_text(rules_text, reply_markup=_help_keyboard("help"), parse_mode="HTML")
    await callback.answer()
