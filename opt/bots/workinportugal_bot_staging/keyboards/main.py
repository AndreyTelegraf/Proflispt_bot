# BACK_ARROW_AND_RESIDENCY_FIX_APPLIED
"""Main keyboards for Work in Portugal Bot."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu() -> InlineKeyboardMarkup:
    """Get main menu keyboard."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="❓ Помощь",
            callback_data="help"
        ),
        InlineKeyboardButton(
            text="📋 Мои объявления",
            callback_data="my_postings"
        ),
    )

    builder.row(
        InlineKeyboardButton(
            text="📚 Разделы",
            callback_data="catalog:groups"
        ),
    )

    return builder.as_markup()
def get_cities_keyboard() -> InlineKeyboardMarkup:
    """Get cities selection keyboard."""
    builder = InlineKeyboardBuilder()
    
    # Add city buttons
    cities = [
        ("Lisboa", "city:lisboa"),
        ("Porto", "city:porto"),
        ("Algarve", "city:algarve"),
        ("Coimbra", "city:coimbra"),
        ("Braga", "city:braga"),
        ("Faro", "city:faro"),
        ("Sintra", "city:sintra"),
        ("Cascais", "city:cascais"),
        ("Leiria", "city:leiria"),
        ("Madeira", "city:madeira"),
        ("Онлайн", "city:online"),
        ("Другой город", "city:custom")
    ]
    
    for text, callback_data in cities:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    builder.add(InlineKeyboardButton(
        text="← Назад",
        callback_data="go:main"
    ))
    
    builder.adjust(3)  # 3 buttons per row
    return builder.as_markup()


def get_back_button(back_to: str = "go:main") -> InlineKeyboardMarkup:
    """Get back button keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="← Назад",
        callback_data=back_to
    ))
    
    return builder.as_markup()


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Get confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Опубликовать",
        callback_data="confirm:publish"
    ))
    
    builder.add(InlineKeyboardButton(
        text="✏️ Редактировать",
        callback_data="edit:draft"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="go:main"
    ))
    
    builder.adjust(2, 1)  # 2 buttons in first row, 1 in second
    return builder.as_markup()


def get_my_postings_keyboard() -> InlineKeyboardMarkup:
    """Get my postings keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✏️ Редактировать",
        callback_data="edit:posting"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🗑️ Удалить",
        callback_data="delete:posting"
    ))
    
    builder.add(InlineKeyboardButton(
        text="← Назад",
        callback_data="go:main"
    ))
    
    builder.adjust(2, 1)  # 2 buttons in first row, 1 in second
    return builder.as_markup()


def get_help_keyboard() -> InlineKeyboardMarkup:
    """Get help keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📋 Правила публикации",
        callback_data="help:rules"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📞 Поддержка",
        callback_data="help:support"
    ))
    
    builder.add(InlineKeyboardButton(
        text="← Назад",
        callback_data="go:main"
    ))
    
    builder.adjust(1)  # 1 button per row
    return builder.as_markup()
