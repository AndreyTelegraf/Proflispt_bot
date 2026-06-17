"""Start handler."""

import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from database import db
from keyboards.main import get_main_menu

logger = logging.getLogger(__name__)
router = Router()


def _main_menu_text() -> str:
    return (
        "Здравствуйте!\n\n"
        "Этот бот поможет вам опубликовать объявления в разделы Справочника.\n\n"
        'Перед публикацией обязательно ознакомьтесь <a href="https://t.me/Proflistpt_bot?start=rules">с правилами</a>!\n\n'
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
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    await state.clear()

    db.create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    logger.info("User %s started bot", message.from_user.id)

    if (command.args or "").strip() == "rules":
        await message.answer(
            _rules_text(),
            reply_markup=_help_keyboard("go:main"),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    await message.answer(
        _main_menu_text(),
        reply_markup=get_main_menu(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "go:main")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        _main_menu_text(),
        reply_markup=get_main_menu(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    help_text = (
        "Если сомневаетесь, куда публиковать объявление, напишите администратору."
    )
    await callback.message.edit_text(help_text, reply_markup=_help_keyboard("go:main"))
    await callback.answer()


def _rules_text() -> str:
    return (
        "📜 <b>Правила:</b>\n"
        "- Выбирайте правильный раздел, это влияет на видимость объявления.\n"
        "- Описание должно чётко объяснять, что вы предлагаете или ищете.\n"
        "- Объявления принимаются только от первого лица.\n"
        "- Город, имя, номер телефона и ссылки бот запросит отдельно, в описание их вводить не нужно.\n"
        "- Tg-username и отзывы бот подтянет автоматически.\n"
        "- Справочник предназначен только для Португалии.\n"
        "- Для недвижимости обязательно указывать цену.\n"
        "\n"
        "💰 <b>Форматы размещения:</b>\n"
        "- Стандартная публикация — без медиа, только ссылки и отзывы.\n"
        "- Пост с медиа (€20) — до 10 фото/видео.\n"
        "- Поднять (€10) — делает объявление самым свежим в разделе и заменяет старую версию.\n"
        "- Перепост в Барахолку (€10) из раздела \"Недвижимость от хозяев\".\n"
        "\n"
        "🗑 <b>Удаление:</b>\n"
        "- Для поддержания актуальности объявления удаляются автоматически через 30 или 90 дней в зависимости от раздела.\n"
        "- Перед удалением бот заранее предупреждает владельца объявления.\n"
        "- Самостоятельно удалить объявление можно через «Мои объявления» в главном меню бота.\n"
        "\n"
        "✏️ <b>Редактирование:</b>\n"
        "- В течение 6 часов после первой публикации объявление без ограничений можно редактировать через удаление и повторную публикацию.\n"
        "- Если объявление активно, создать дубликат нельзя — сначала удалите текущее объявление.\n"
        "- Через 6 часов после первой публикации повторная бесплатная публикация той же связки будет заблокирована на 30 дней.\n"
        "\n"
        "📊 <b>Лимиты:</b>\n"
        "- Посты с медиа, апы и перепосты — без ограничений.\n"
        "- Посты без медиа: до 3 объявлений в одном разделе и до 10 объявлений во всём Справочнике за 30 дней.\n"
        "- Лимиты считаются по пользователю, разделу и номеру телефона.\n"
        "- Удаление объявления не сбрасывает месячные лимиты.\n"
        "\n"
        "⚠️ <b>Модерация:</b>\n"
        "- Запрещены спам, дубли и вводящая в заблуждение информация.\n"
        "- Контакты, ссылки и тэги внутри текста объявления запрещены.\n"
        "- Посты с нарушениями удаляются, частые нарушения могут привести к блокировке пользователя или номера телефона.\n"
        "- Отзывы и платные размещения публикуются только после модераторской проверки."
    )


@router.callback_query(F.data == "help:rules")
async def show_rules(callback: CallbackQuery):
    await callback.message.edit_text(
        _rules_text(),
        reply_markup=_help_keyboard("help"),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()
