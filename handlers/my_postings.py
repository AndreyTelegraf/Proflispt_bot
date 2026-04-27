"""Handlers for 'My Postings' section."""

import json
from datetime import datetime
from typing import Optional

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from config import Config
from utils import get_first_words, escape_markdown, format_posting_card

router = Router()


class DeletePostingStates(StatesGroup):
    """States for deleting posting."""
    confirm_delete = State()


class EditPostingStates(StatesGroup):
    """States for editing posting."""
    select_field = State()
    edit_description = State()
    edit_cities = State()
    edit_phone_whatsapp = State()
    edit_social_media = State()




def get_posting_menu_keyboard(posting_id: int) -> InlineKeyboardMarkup:
    """Create keyboard for posting menu."""
    keyboard = [
        [InlineKeyboardButton(
            text="🔍 Показать",
            callback_data=f"show_posting_{posting_id}"
        )],
        [InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=f"edit_posting_{posting_id}"
        )],
        [InlineKeyboardButton(
            text="📊 Статистика",
            callback_data=f"stats_posting_{posting_id}"
        )],
        [InlineKeyboardButton(
            text="🗑️ Удалить",
            callback_data=f"delete_posting_{posting_id}"
        )],
        [InlineKeyboardButton(
            text="← Назад",
            callback_data="back_to_my_postings"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_delete_confirmation_keyboard(posting_id: int) -> InlineKeyboardMarkup:
    """Create keyboard for delete confirmation."""
    keyboard = [
        [InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"confirm_delete_{posting_id}"
        )],
        [InlineKeyboardButton(
            text="🚫 Отмена",
            callback_data=f"cancel_delete_{posting_id}"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(F.data == "my_postings")
async def show_my_postings(callback: CallbackQuery):
    """Show user's postings."""
    user_id = callback.from_user.id
    
    # Get user from database
    user = db.get_user(user_id)
    if not user:
        await callback.message.edit_text(
            "🚫 Пользователь не найден в базе данных.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← Назад", callback_data="go:main")
            ]])
        )
        await callback.answer()
        return
    
    user_id_db = user['id']
    postings = db.get_user_active_postings(user_id_db)
    restaurant_posts = db.get_user_published_restaurant_premium_posts(user_id_db)

    if not postings and not restaurant_posts:
        await callback.message.edit_text(
            "📋 Мои объявления\n\n"
            "У вас пока нет активных объявлений.\n"
            "Подайте первое объявление нажав кнопку \"Опубликовать\" в главном меню:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← Назад", callback_data="go:main")
            ]])
        )
        try:
            await callback.answer()
        except:
            pass
        return

    # Create posting cards
    cards = []
    for posting in postings[:3]:
        card_content = format_posting_card(posting)
        cards.append(card_content)

    # Join cards with separators
    cards_text = "\n\n_____________\n\n".join(cards)

    # Create keyboard with management buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for i, posting in enumerate(postings[:3], 1):
        keyboard.inline_keyboard.append([InlineKeyboardButton(
            text=f"Управлять объявлением {i}",
            callback_data=f"posting_{posting['id']}"
        )])

    if not restaurant_posts:
        keyboard.inline_keyboard.append([InlineKeyboardButton(
            text="← Назад",
            callback_data="go:main"
        )])

    await callback.message.edit_text(
        f"📋 Мои объявления\n\n"
        f"{cards_text}",
        reply_markup=keyboard,
    )

    for post in restaurant_posts:
        cities = post['cities']
        if isinstance(cities, list):
            cities_str = ", ".join(str(c) for c in cities)
        else:
            cities_str = str(cities)

        desc = post.get('description') or ""
        desc = desc.strip().replace("\n", " ")

        if len(desc) > 100:
            desc_preview = desc[:100].rstrip() + "…"
        else:
            desc_preview = desc

        await callback.message.answer(
            f"🍽 {post['name']} ({cities_str})\n\n{desc_preview}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Переопубликовать — 10 €",
                    callback_data=f"repost_premium_{post['id']}",
                )],
                [InlineKeyboardButton(
                    text="Закрепить — 5 €",
                    callback_data=f"pin_premium_{post['id']}",
                )],
            ]),
        )

    if restaurant_posts:
        await callback.message.answer(
            "─",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← Назад", callback_data="go:main")
            ]]),
        )

    try:
        await callback.answer()
    except:
        pass


@router.callback_query(F.data.startswith("posting_"))
async def show_posting_menu(callback: CallbackQuery):
    """Show menu for specific posting."""
    posting_id = int(callback.data.split("_")[1])
    
    # Get posting details
    posting = db.get_posting_by_id(posting_id)
    if not posting:
        await callback.message.edit_text(
            "🚫 Объявление не найдено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← Назад", callback_data="my_postings")
            ]])
        )
        await callback.answer()
        return
    
    # Check if user owns this posting
    user = db.get_user(callback.from_user.id)
    if not user or posting['user_id'] != user['id']:
        await callback.message.edit_text(
            "🚫 У вас нет прав для управления этим объявлением.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← Назад", callback_data="my_postings")
            ]])
        )
        await callback.answer()
        return
    
    # Get first words for title
    description = posting.get('description', '')
    title = get_first_words(description, 5) or "Объявление"
    
    # Create menu keyboard
    keyboard = get_posting_menu_keyboard(posting_id)
    
    # Escape special characters for MarkdownV2
    def escape_markdown(text):
        if not text:
            return text
        return text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
    
    await callback.message.edit_text(
        f"📋 Управление объявлением\n\n"
        f"*{escape_markdown(title)}*\n"
        f"Тип: {escape_markdown('Ищу работу' if posting['mode'] == 'seeking' else 'Предлагаю работу')}\n"
        f"Города: {escape_markdown(posting['cities'])}\n"
        f"Создано: {escape_markdown(posting['created_at'].strftime('%d.%m.%Y %H:%M') if isinstance(posting['created_at'], datetime) else str(posting['created_at']))}\n\n"
        f"Выберите действие:",
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("show_posting_"))
async def show_posting_link(callback: CallbackQuery):
    """Show posting link."""
    posting_id = int(callback.data.split("_")[2])
    
    posting = db.get_posting_by_id(posting_id)
    if not posting:
        await callback.answer("🚫 Объявление не найдено", show_alert=True)
        return
    
    # Check ownership
    user = db.get_user(callback.from_user.id)
    if not user or posting['user_id'] != user['id']:
        await callback.answer("🚫 Нет прав", show_alert=True)
        return
    
    if posting['message_id'] and posting['chat_id'] and posting['topic_id']:
        # Create link to the message in topic
        chat_username = "proflistpt"  # Remove @ for URL
        message_link = f"https://t.me/{chat_username}/{posting['topic_id']}/{posting['message_id']}"
        
        await callback.message.edit_text(
            f"🔍 Ссылка на ваше объявление:\n\n"
            f"{message_link}\n\n"
            f"Нажмите на ссылку, чтобы перейти к объявлению.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← Назад", callback_data=f"posting_{posting_id}")
            ]])
        )
    else:
        # Check if this is a posting that was never published
        if not posting.get('message_id') and not posting.get('chat_id') and not posting.get('topic_id'):
            error_text = (
                "🚫 Объявление не было опубликовано\n\n"
                "Это объявление было создано, но не удалось опубликовать его в канал. "
                "Рекомендуем удалить это объявление и создать новое."
            )
        else:
            error_text = (
                "🚫 Ссылка на объявление недоступна.\n\n"
                "Возможно, объявление было удалено или перемещено."
            )
        
        # Create keyboard with delete button for unpublished postings
        if not posting.get('message_id') and not posting.get('chat_id') and not posting.get('topic_id'):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗑️ Удалить объявление", callback_data=f"delete_posting_{posting_id}")],
                [InlineKeyboardButton(text="← Назад", callback_data=f"posting_{posting_id}")]
            ])
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← Назад", callback_data=f"posting_{posting_id}")
            ]])
        
        await callback.message.edit_text(
            error_text,
            reply_markup=keyboard
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("stats_posting_"))
async def show_posting_statistics(callback: CallbackQuery):
    """Show posting statistics."""
    posting_id = int(callback.data.split("_")[2])
    
    posting = db.get_posting_by_id(posting_id)
    if not posting:
        await callback.answer("🚫 Объявление не найдено", show_alert=True)
        return
    
    # Check ownership
    user = db.get_user(callback.from_user.id)
    if not user or posting['user_id'] != user['id']:
        await callback.answer("🚫 Нет прав", show_alert=True)
        return
    
    # Get user statistics
    stats = db.get_posting_statistics(user['id'])
    
    # Escape special characters for MarkdownV2
    def escape_markdown(text):
        if not text:
            return text
        return text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
    
    # Format statistics text
    stats_text = f"📊 Статистика публикаций\n\n"
    stats_text += f"*Текущие лимиты:*\n"
    stats_text += f"• Активных объявлений: {stats['current_count']}/{stats['max_count']}\n"
    stats_text += f"• Можно публиковать: {'✅ Да' if stats['can_post'] else '🚫 Нет'}\n"
    
    if stats['earliest_next_post_date']:
        stats_text += f"• Следующая публикация: {escape_markdown(stats['earliest_next_post_date'].strftime('%d.%m.%Y %H:%M'))}\n"
    
    stats_text += f"\n*Ваши активные объявления:*\n"
    for i, p in enumerate(stats['all_active_postings'], 1):
        created_date = p['created_at']
        if isinstance(created_date, str):
            created_date = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
        
        stats_text += f"{i}\\. {escape_markdown(p['name'])} \\({escape_markdown(p['mode'])}\\)\n"
        stats_text += f"   Создано: {escape_markdown(created_date.strftime('%d.%m.%Y %H:%M'))}\n"
        stats_text += f"   Города: {escape_markdown(p['cities'])}\n\n"
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="← Назад", callback_data=f"posting_{posting_id}")
        ]]),
        parse_mode="MarkdownV2"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_posting_"))
async def confirm_delete_posting(callback: CallbackQuery, state: FSMContext):
    """Show delete confirmation."""
    posting_id = int(callback.data.split("_")[2])
    
    posting = db.get_posting_by_id(posting_id)
    if not posting:
        await callback.answer("🚫 Объявление не найдено", show_alert=True)
        return
    
    # Check ownership
    user = db.get_user(callback.from_user.id)
    if not user or posting['user_id'] != user['id']:
        await callback.answer("🚫 Нет прав", show_alert=True)
        return
    
    # Store posting info in state
    await state.update_data(posting_id=posting_id)
    await state.set_state(DeletePostingStates.confirm_delete)
    
    # Get first words for title
    description = posting.get('description', '')
    title = get_first_words(description, 5) or "Объявление"
    
    # Create confirmation keyboard
    keyboard = get_delete_confirmation_keyboard(posting_id)
    
    await callback.message.edit_text(
        f"🗑️ Удаление объявления\n\n"
        f"Вы действительно хотите удалить объявление:\n"
        f"{title}\n\n"
        f"Это действие нельзя отменить!",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_"))
async def delete_posting(callback: CallbackQuery, state: FSMContext):
    """Delete the posting."""
    posting_id = int(callback.data.split("_")[2])
    
    posting = db.get_posting_by_id(posting_id)
    if not posting:
        await callback.answer("🚫 Объявление не найдено", show_alert=True)
        return
    
    # Check ownership
    user = db.get_user(callback.from_user.id)
    if not user or posting['user_id'] != user['id']:
        await callback.answer("🚫 Нет прав", show_alert=True)
        return
    
    try:
        # Delete from Telegram channel if possible
        telegram_deleted = False
        telegram_edited = False
        if posting['message_id'] and posting['chat_id']:
            try:
                # First try to delete the message
                await callback.bot.delete_message(
                    chat_id=posting['chat_id'],
                    message_id=posting['message_id']
                )
                telegram_deleted = True
                print(f"Successfully deleted Telegram message {posting['message_id']} from chat {posting['chat_id']}")
            except Exception as e:
                # Log error and try to edit instead
                print(f"Failed to delete Telegram message {posting['message_id']} from chat {posting['chat_id']}: {e}")
                
                # Check if it's a permission error or message not found
                if "message to delete not found" in str(e).lower() or "chat not found" in str(e).lower():
                    print(f"Message or chat not found - likely already deleted or moved to different channel")
                elif "not enough rights" in str(e).lower() or "forbidden" in str(e).lower():
                    print(f"Insufficient permissions to delete message from chat {posting['chat_id']}")
                elif "message can't be deleted" in str(e).lower():
                    print(f"Message cannot be deleted - likely older than 48 hours, trying to edit instead")
                    
                    # Try to edit the message instead of deleting
                    try:
                        await callback.bot.edit_message_text(
                            chat_id=posting['chat_id'],
                            message_id=posting['message_id'],
                            text="🗑️ Объявление удалено пользователем"
                        )
                        telegram_edited = True
                        print(f"Successfully edited Telegram message {posting['message_id']} to show deletion")
                    except Exception as edit_error:
                        print(f"Failed to edit Telegram message {posting['message_id']}: {edit_error}")
                else:
                    print(f"Unknown error: {e}")
        
        # Delete from database
        success = db.delete_posting(posting_id)
        
        if success:
            # Prepare success message based on Telegram deletion result
            if telegram_deleted:
                success_message = "✅ Объявление успешно удалено из канала и базы данных!\n\nТеперь вы можете создать новое объявление."
            elif telegram_edited:
                success_message = "✅ Объявление удалено из базы данных!\n\n📝 Сообщение в канале отмечено как удаленное (старые сообщения нельзя удалить, но можно отредактировать).\n\nТеперь вы можете создать новое объявление."
            else:
                success_message = "✅ Объявление удалено из базы данных!\n\n⚠️ Сообщение в канале может остаться (нет доступа к каналу).\n\nТеперь вы можете создать новое объявление."
            
            await callback.message.edit_text(
                success_message,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="📋 Мои объявления", callback_data="my_postings"),
                    InlineKeyboardButton(text="← Главное меню", callback_data="go:main")
                ]])
            )
        else:
            await callback.message.edit_text(
                "�� Ошибка при удалении объявления.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ Назад", callback_data=f"posting_{posting_id}")
                ]])
            )
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        await callback.message.edit_text(
            f"🚫 Ошибка при удалении: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="← Назад", callback_data=f"posting_{posting_id}")
            ]])
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_delete_"))
async def cancel_delete_posting(callback: CallbackQuery, state: FSMContext):
    """Cancel posting deletion."""
    posting_id = int(callback.data.split("_")[2])
    
    # Get posting details to return to menu
    posting = db.get_posting_by_id(posting_id)
    if not posting:
        await callback.answer("🚫 Объявление не найдено", show_alert=True)
        await state.clear()
        return
    
    # Check ownership
    user = db.get_user(callback.from_user.id)
    if not user or posting['user_id'] != user['id']:
        await callback.answer("🚫 Нет прав", show_alert=True)
        await state.clear()
        return
    
    # Clear state
    await state.clear()
    
    # Get first words for title
    description = posting.get('description', '')
    title = get_first_words(description, 5) or "Объявление"
    
    # Create menu keyboard
    keyboard = get_posting_menu_keyboard(posting_id)
    
    await callback.message.edit_text(
        f"📋 Управление объявлением\n\n"
        f"{title}\n"
        f"Тип: {'Ищу работу' if posting['mode'] == 'seeking' else 'Предлагаю работу'}\n"
        f"Города: {posting['cities']}\n"
        f"Создано: {posting['created_at'].strftime('%d.%m.%Y %H:%M') if hasattr(posting['created_at'], 'strftime') else posting['created_at']}\n\n"
        f"Выберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_my_postings")
async def back_to_my_postings(callback: CallbackQuery):
    """Go back to my postings list."""
    await show_my_postings(callback)
    try:
        await callback.answer()
    except:
        pass


@router.callback_query(F.data.startswith("edit_posting_"))
async def start_edit_posting(callback: CallbackQuery, state: FSMContext):
    """Start editing a posting."""
    posting_id = int(callback.data.split("_")[2])
    
    # Get posting details
    posting = db.get_posting_by_id(posting_id)
    if not posting:
        await callback.answer("🚫 Объявление не найдено", show_alert=True)
        return
    
    # Check ownership
    user = db.get_user(callback.from_user.id)
    if not user or posting['user_id'] != user['id']:
        await callback.answer("🚫 Нет прав", show_alert=True)
        return
    
    # Store posting data in state
    await state.update_data(posting_id=posting_id, posting=posting)
    await state.set_state(EditPostingStates.select_field)
    
    # Create field selection keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Описание", callback_data="edit_field_description")],
        [InlineKeyboardButton(text="🏙️ Города", callback_data="edit_field_cities")],
        [InlineKeyboardButton(text="📱 WhatsApp", callback_data="edit_field_phone_whatsapp")],
        [InlineKeyboardButton(text="📱 Соцсети", callback_data="edit_field_social_media")],
        [InlineKeyboardButton(text="← Назад", callback_data=f"posting_{posting_id}")]
    ])
    
    await callback.message.edit_text(
        "✏️ Редактирование объявления\n\n"
        "Выберите поле для редактирования:",
        reply_markup=keyboard
    )
    try:
        await callback.answer()
    except:
        pass


@router.callback_query(F.data.startswith("edit_field_"))
async def select_edit_field(callback: CallbackQuery, state: FSMContext):
    """Select field to edit."""
    field = callback.data.split("_")[2]
    data = await state.get_data()
    posting = data['posting']
    
    # Set appropriate state and show current value
    if field == "description":
        await state.set_state(EditPostingStates.edit_description)
        current_value = posting.get('description', '')
        prompt = "📝 Введите новое описание объявления:"
    elif field == "cities":
        await state.set_state(EditPostingStates.edit_cities)
        current_value = posting.get('cities', '')
        prompt = "🏙️ Введите новые города (через запятую):"
    elif field == "phone_whatsapp":
        await state.set_state(EditPostingStates.edit_phone_whatsapp)
        current_value = posting.get('phone_whatsapp', '')
        prompt = "📱 Введите новый номер WhatsApp в формате +35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx:"
    elif field == "social_media":
        await state.set_state(EditPostingStates.edit_social_media)
        current_value = posting.get('social_media', '')
        prompt = "📱 Введите новые социальные сети (через запятую):"
    else:
        await callback.answer("🚫 Неизвестное поле", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="← Назад", callback_data=f"edit_posting_{data['posting_id']}")
    ]])
    
    await callback.message.edit_text(
        f"{prompt}\n\n"
        f"Текущее значение:\n{current_value}",
        reply_markup=keyboard
    )
    try:
        await callback.answer()
    except:
        pass


@router.message(F.text)
async def handle_edit_text_input(message: Message, state: FSMContext):
    """Handle text input for editing posting fields."""
    current_state = await state.get_state()
    data = await state.get_data()
    posting_id = data.get('posting_id')
    
    if not posting_id:
        return
    
    if current_state == EditPostingStates.edit_description:
        # Validate description
        description = message.text.strip()
        
        if len(description) < 10:
            await message.answer(
                "🚫 Описание слишком короткое. Пожалуйста, напишите более подробное описание (минимум 10 символов).",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← Назад", callback_data=f"edit_posting_{posting_id}")
                ]])
            )
            return
        
        # Update posting
        success = db.update_posting(posting_id, description=description)
        if success:
            await message.answer(
                "✅ Описание успешно обновлено!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← К управлению", callback_data=f"posting_{posting_id}")
                ]])
            )
        else:
            await message.answer(
                "🚫 Ошибка при обновлении описания.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← Назад", callback_data=f"edit_posting_{posting_id}")
                ]])
            )
        await state.clear()
        
    elif current_state == EditPostingStates.edit_cities:
        # Validate cities
        cities_input = message.text.strip()
        cities = [city.strip() for city in cities_input.split(",") if city.strip()]
        
        if not cities:
            await message.answer(
                "🚫 Необходимо указать хотя бы один город.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← Назад", callback_data=f"edit_posting_{posting_id}")
                ]])
            )
            return
        
        # Update posting
        success = db.update_posting(posting_id, cities=", ".join(cities))
        if success:
            await message.answer(
                "✅ Города успешно обновлены!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← К управлению", callback_data=f"posting_{posting_id}")
                ]])
            )
        else:
            await message.answer(
                "🚫 Ошибка при обновлении городов.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← Назад", callback_data=f"edit_posting_{posting_id}")
                ]])
            )
        await state.clear()
        
    elif current_state == EditPostingStates.edit_phone_whatsapp:
        # Validate WhatsApp phone
        phone = message.text.strip()
        
        if phone.lower() != 'нет' and (not phone.startswith('+351') or len(phone) != 13):
            await message.answer(
                "🚫 Неверный формат номера WhatsApp. Укажите в формате +35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx или напишите 'нет'",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← Назад", callback_data=f"edit_posting_{posting_id}")
                ]])
            )
            return
        
        # Update posting
        success = db.update_posting(posting_id, phone_whatsapp=phone)
        if success:
            await message.answer(
                "✅ WhatsApp успешно обновлен!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← К управлению", callback_data=f"posting_{posting_id}")
                ]])
            )
        else:
            await message.answer(
                "🚫 Ошибка при обновлении WhatsApp.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← Назад", callback_data=f"edit_posting_{posting_id}")
                ]])
            )
        await state.clear()
        
    elif current_state == EditPostingStates.edit_social_media:
        # Validate social media
        social_media = message.text.strip()
        
        if social_media.lower() == 'нет':
            social_media = ''
        
        # Update posting
        success = db.update_posting(posting_id, social_media=social_media)
        if success:
            await message.answer(
                "✅ Социальные сети успешно обновлены!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← К управлению", callback_data=f"posting_{posting_id}")
                ]])
            )
        else:
            await message.answer(
                "🚫 Ошибка при обновлении социальных сетей.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="← Назад", callback_data=f"edit_posting_{posting_id}")
                ]])
            )
        await state.clear()


@router.callback_query(F.data.startswith("repost_premium_"))
async def request_repost_premium(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[2])

    post = db.get_premium_post(post_id)
    if not post:
        await callback.answer("Объявление не найдено.", show_alert=True)
        return

    user = db.get_user(callback.from_user.id)
    if not user or post['user_id'] != user['id']:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    if post.get('status') != 'published':
        await callback.answer("Объявление уже не активно.", show_alert=True)
        return

    review_links = ""
    try:
        source_notes = json.loads(post.get("admin_notes") or "{}")
        review_links = source_notes.get("review_links", "")
    except Exception:
        review_links = ""

    new_post_id = db.create_premium_post(
        user_id=user['id'],
        mode='restaurants',
        cities=json.dumps(post['cities']),
        description=post['description'],
        social_media=post.get('social_media'),
        telegram_username=post.get('telegram_username'),
        phone_main=post.get('phone_main'),
        phone_whatsapp=post.get('phone_whatsapp'),
        name=post.get('name'),
        media_file_id=post.get('media_file_id'),
        media_type=post.get('media_type'),
        media_list=post.get('media_list') or [],
        payment_amount=10.00,
        action_type='repost',
        admin_notes=json.dumps({
            "old_post_id": post['id'],
            "old_message_id": post.get('message_id'),
            "old_chat_id": post.get('chat_id'),
            "old_topic_id": post.get('topic_id'),
            "review_links": review_links,
            "old_published_message_ids": post.get('published_message_ids') or [],
        }),
    )

    try:
        cities = post.get('cities') or []
        if isinstance(cities, list):
            cities_str = ", ".join(str(c) for c in cities)
        else:
            cities_str = str(cities)

        old_link = ""
        if post.get('message_id'):
            if post.get('topic_id'):
                old_link = f"\nСтарый пост: https://t.me/proflistpt/{post['topic_id']}/{post['message_id']}"
            else:
                old_link = f"\nСтарый пост: https://t.me/proflistpt/{post['message_id']}"

        import html
        desc = html.escape((post.get('description') or "").strip().replace("\n", " "))
        name = html.escape(str(post.get('name') or ""))
        cities_safe = html.escape(cities_str)

        if len(desc) > 120:
            desc = desc[:120].rstrip() + "…"

        if callback.from_user.username:
            user_ref = f'<a href="https://t.me/{callback.from_user.username}">@{callback.from_user.username}</a>'
        else:
            user_ref = f'<a href="tg://user?id={callback.from_user.id}">{html.escape(callback.from_user.first_name or str(callback.from_user.id))}</a>'

        admin_text = (
            f"🔁 <b>Repost #{new_post_id}</b> — 10 €\n\n"
            f"<b>{name}</b> ({cities_safe})\n"
            f"{desc}"
            f"{old_link}\n\n"
            f"Пользователь: {user_ref}"
        )

        await callback.bot.send_message(
            Config.ADMIN_IDS[0],
            admin_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Одобрить",
                        callback_data=f"admin:approve_premium:{new_post_id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"admin:reject_premium:{new_post_id}",
                    ),
                ],
                [InlineKeyboardButton(text="📋 Список заявок", callback_data="admin:list_premium")],
            ]),
        )
    except Exception:
        pass

    await callback.answer("Заявка на переопубликацию отправлена", show_alert=True)


@router.callback_query(F.data.startswith("pin_premium_"))
async def request_pin_premium(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[2])

    post = db.get_premium_post(post_id)
    if not post:
        await callback.answer("Объявление не найдено.", show_alert=True)
        return

    user = db.get_user(callback.from_user.id)
    if not user or post['user_id'] != user['id']:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    if post.get('status') != 'published':
        await callback.answer("Объявление уже не активно.", show_alert=True)
        return

    review_links = ""
    try:
        source_notes = json.loads(post.get("admin_notes") or "{}")
        review_links = source_notes.get("review_links", "")
    except Exception:
        review_links = ""

    new_post_id = db.create_premium_post(
        user_id=user['id'],
        mode='restaurants',
        cities=json.dumps(post['cities']),
        description=post['description'],
        social_media=post.get('social_media'),
        telegram_username=post.get('telegram_username'),
        phone_main=post.get('phone_main'),
        phone_whatsapp=post.get('phone_whatsapp'),
        name=post.get('name'),
        media_file_id=post.get('media_file_id'),
        media_type=post.get('media_type'),
        media_list=post.get('media_list') or [],
        payment_amount=5.00,
        action_type='pin',
        admin_notes=json.dumps({
            "old_post_id": post['id'],
            "old_message_id": post.get('message_id'),
            "old_chat_id": post.get('chat_id'),
            "old_topic_id": post.get('topic_id'),
            "review_links": review_links,
        }),
    )

    try:
        cities = post.get('cities') or []
        if isinstance(cities, list):
            cities_str = ", ".join(str(c) for c in cities)
        else:
            cities_str = str(cities)

        post_link = ""
        if post.get('message_id'):
            if post.get('topic_id'):
                post_link = f"\nПост: https://t.me/proflistpt/{post['topic_id']}/{post['message_id']}"
            else:
                post_link = f"\nПост: https://t.me/proflistpt/{post['message_id']}"

        import html
        desc = html.escape((post.get('description') or "").strip().replace("\n", " "))
        name = html.escape(str(post.get('name') or ""))
        cities_safe = html.escape(cities_str)

        if len(desc) > 120:
            desc = desc[:120].rstrip() + "…"

        if callback.from_user.username:
            user_ref = f'<a href="https://t.me/{callback.from_user.username}">@{callback.from_user.username}</a>'
        else:
            user_ref = f'<a href="tg://user?id={callback.from_user.id}">{html.escape(callback.from_user.first_name or str(callback.from_user.id))}</a>'

        admin_text = (
            f"📌 <b>Pin #{new_post_id}</b> — 5 €\n\n"
            f"<b>{name}</b> ({cities_safe})\n"
            f"{desc}"
            f"{post_link}\n\n"
            f"Пользователь: {user_ref}"
        )

        await callback.bot.send_message(
            Config.ADMIN_IDS[0],
            admin_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Одобрить",
                        callback_data=f"admin:approve_premium:{new_post_id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"admin:reject_premium:{new_post_id}",
                    ),
                ],
                [InlineKeyboardButton(text="📋 Список заявок", callback_data="admin:list_premium")],
            ]),
        )
    except Exception:
        pass

    await callback.answer("Заявка на закрепление отправлена", show_alert=True)
