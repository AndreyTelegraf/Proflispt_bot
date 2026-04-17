"""Premium posting handlers for Work in Portugal Bot."""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import db

logger = logging.getLogger(__name__)

router = Router()

class PremiumPostingStates(StatesGroup):
    """States for premium posting."""
    waiting_for_media = State()
    waiting_for_cities = State()
    waiting_for_custom_city = State()
    waiting_for_description = State()
    waiting_for_social_media = State()
    waiting_for_username_confirmation = State()
    waiting_for_telegram_username = State()
    waiting_for_phone_main = State()
    waiting_for_phone_whatsapp = State()
    waiting_for_name = State()
    waiting_for_section_choice = State()
    waiting_for_confirmation = State()

def get_back_button(back_to: str = "go:main") -> InlineKeyboardMarkup:
    """Get back button keyboard."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="← Назад",
        callback_data=back_to
    ))
    return builder.as_markup()

@router.callback_query(F.data == "premium_posting")
async def start_premium_posting(callback: CallbackQuery, state: FSMContext):
    """Start premium posting process."""
    await state.clear()
    
    welcome_text = (
        "💎 *Премиум\\-пост с медиа*\n\n"
        "Создайте привлекательное объявление с фото или видео\\!\n\n"
        "*Стоимость:* €50\n"
        "*Что включено:*\n"
        "• Публикация с медиа в канале\n"
        "• Приоритетное размещение\n"
        "• Увеличенная видимость\n\n"
        "Выберите раздел для публикации:"
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🔍 Ищу работу",
        callback_data="premium:section_job_seeker"
    ))
    builder.add(InlineKeyboardButton(
        text="💰 Предлагаю работу",
        callback_data="premium:section_job_offer"
    ))
    builder.add(InlineKeyboardButton(
        text="← Назад",
        callback_data="go:main"
    ))
    builder.adjust(2, 1)
    
    await callback.message.edit_text(
        welcome_text,
        reply_markup=builder.as_markup(),
        parse_mode="MarkdownV2"
    )
    await state.set_state(PremiumPostingStates.waiting_for_section_choice)
    await callback.answer()

@router.message(PremiumPostingStates.waiting_for_media, F.photo | F.video)
async def handle_media_upload(message: Message, state: FSMContext):
    """Handle media upload."""
    logger.info(f"Premium media upload handler called for user {message.from_user.id}")
    
    # Get current media list or create new one
    data = await state.get_data()
    media_list = data.get('media_list', [])
    
    if message.photo:
        media_file_id = message.photo[-1].file_id
        media_type = "photo"
    else:
        media_file_id = message.video.file_id
        media_type = "video"
    
    # Add media to list
    media_list.append({
        'file_id': media_file_id,
        'type': media_type
    })
    
    await state.update_data(media_list=media_list)
    
    # Show confirmation and move to cities selection after first media
    if len(media_list) == 1:
        # Create cities keyboard
        builder = InlineKeyboardBuilder()
        
        cities = [
            ("Lisboa", "premium:city:lisboa"),
            ("Porto", "premium:city:porto"),
            ("Algarve", "premium:city:algarve"),
            ("Coimbra", "premium:city:coimbra"),
            ("Braga", "premium:city:braga"),
            ("Faro", "premium:city:faro"),
            ("Sintra", "premium:city:sintra"),
            ("Cascais", "premium:city:cascais"),
            ("Leiria", "premium:city:leiria"),
            ("Madeira", "premium:city:madeira"),
            ("Онлайн", "premium:city:online"),
            ("Другие города", "premium:city:custom")
        ]
        
        for text, callback_data in cities:
            builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
        
        builder.add(InlineKeyboardButton(text="← Назад", callback_data="premium_posting"))
        builder.adjust(3)  # 3 buttons per row
        
        await message.answer("✅ Медиа загружено\\! Теперь выберите город или города:", reply_markup=builder.as_markup())
        await state.set_state(PremiumPostingStates.waiting_for_cities)
    # НЕ меняем состояние - остаемся в waiting_for_media для дополнительных медиа
    logger.info(f"Premium media upload completed for user {message.from_user.id}, total media: {len(media_list)}")

@router.callback_query(PremiumPostingStates.waiting_for_cities, F.data.startswith("premium:city:"))
async def handle_premium_city_selection(callback: CallbackQuery, state: FSMContext):
    """Handle city selection for premium posting."""
    city_key = callback.data.split(":")[2]
    
    data = await state.get_data()
    media_list = data.get('media_list', [])
    
    if not media_list:
        await callback.answer("🚫 Сначала отправьте хотя бы одно фото или видео для вашего объявления\\.", show_alert=True)
        return
    
    if city_key == "custom":
        await callback.message.edit_text(
            "Введите название города или городов (можно несколько через запятую):",
            reply_markup=get_back_button("premium_posting")
        )
        await state.set_state(PremiumPostingStates.waiting_for_custom_city)
    else:
        # Get city name from config
        from config import Config
        city_name = Config.CITIES.get(city_key, city_key)
        
        # Save selected city
        await state.update_data(cities=[city_key])
        
        # Show cities confirmation and ask for description
        next_text = (
            f"✅ *Город выбран:* {city_name}\n\n"
            "Теперь отправьте текстовое описание \\(без ссылок, эмоджи и контактов\\):"
        )
        
        await callback.message.edit_text(next_text, parse_mode="MarkdownV2")
        await state.set_state(PremiumPostingStates.waiting_for_description)
    
    await callback.answer()

@router.message(PremiumPostingStates.waiting_for_custom_city, F.text)
async def handle_custom_city_input(message: Message, state: FSMContext):
    """Handle custom city input for premium posting."""
    logger.info(f"Premium custom city handler called for user {message.from_user.id}, text: {message.text[:50]}...")
    
    data = await state.get_data()
    media_list = data.get('media_list', [])
    
    if not media_list:
        await message.answer(
            "🚫 Сначала отправьте хотя бы одно фото или видео для вашего объявления\\.",
            reply_markup=get_back_button("go:main")
        )
        return
    
    # Parse cities input
    cities_input = message.text.strip()
    cities = [city.strip() for city in cities_input.split(',') if city.strip()]
    
    if not cities:
        await message.answer(
            "🚫 Пожалуйста, укажите хотя бы один город\\.",
            reply_markup=get_back_button("premium_posting")
        )
        return
    
    # Validate cities
    from config import Config
    valid_cities = []
    invalid_cities = []
    
    for city in cities:
        if city.lower() in ['online', 'онлайн']:
            valid_cities.append('online')
        elif city.lower() in [c.lower() for c in Config.CITIES.keys()]:
            # Find the correct case from Config.CITIES
            for config_city in Config.CITIES.keys():
                if config_city.lower() == city.lower():
                    valid_cities.append(config_city)
                    break
        else:
            invalid_cities.append(city)
    
    if invalid_cities:
        invalid_text = ", ".join(invalid_cities)
        await message.answer(
            f"🚫 Недопустимые города: {invalid_text}\n\n"
            f"Допустимые города: {', '.join(list(Config.CITIES.keys())[:10])}...\n"
            f"Или напишите 'online' для удаленной работы.",
            reply_markup=get_back_button("premium_posting")
        )
        return
    
    await state.update_data(cities=valid_cities)
    
    # Show cities confirmation and ask for description
    cities_text = ", ".join([Config.CITIES.get(city, city) for city in valid_cities])
    
    # Escape special characters for MarkdownV2
    def escape_markdown(text):
        if not text:
            return text
        return text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
    
    next_text = (
        f"✅ *Города выбраны:* {escape_markdown(cities_text)}\n\n"
        "Теперь отправьте текстовое описание \\(без ссылок, эмоджи и контактов\\):"
    )
    
    await message.answer(next_text, parse_mode="MarkdownV2")
    await state.set_state(PremiumPostingStates.waiting_for_description)

@router.message(PremiumPostingStates.waiting_for_description)
async def handle_description(message: Message, state: FSMContext):
    """Handle description input for premium posting."""
    logger.info(f"Premium description handler called for user {message.from_user.id}")
    
    description = message.text.strip()
    
    if len(description) < 10:
        await message.answer(
            "🚫 Описание должно содержать минимум 10 символов\\.\n\n"
            "Отправьте описание заново:"
        )
        return
    
    # Check for invalid content
    invalid_elements = []
    if '@' in description:
        invalid_elements.append('@username')
    if 'http' in description.lower():
        invalid_elements.append('ссылки')
    if '+' in description and any(char.isdigit() for char in description):
        invalid_elements.append('телефоны')
    
    if invalid_elements:
        error_text = (
            f"🚫 В описании не допускаются контакты и ссылки, их нужно будет вводить на следующих шагах. Это лишнее:\n"
            f"• {' • '.join(invalid_elements)}\n\n"
            f"Пожалуйста, переделайте описание в соответствии с правилами:\n"
            f"• Описание должно содержать только текст, без эмодзи\n"
            f"• Контакты (@username, телефоны, email) и ссылки – на следующих шагах.\n\n"
            f"Отправьте исправленное описание заново:"
        )
        await message.answer(error_text)
        return
    
    await state.update_data(description=description)
    
    # Show description confirmation and ask for social media
    next_text = (
        f"✅ *Описание сохранено*\n\n"
        "Теперь укажите социальные сети или сайты \\(или напишите 'нет'\\):"
    )
    
    await message.answer(next_text, parse_mode="MarkdownV2")
    await state.set_state(PremiumPostingStates.waiting_for_social_media)

@router.message(PremiumPostingStates.waiting_for_media)
async def handle_invalid_media(message: Message):
    """Handle invalid media."""
    await message.answer(
        "🚫 Пожалуйста, отправьте фото или видео для вашего объявления\\.",
        reply_markup=get_back_button("go:main")
    )



@router.message(PremiumPostingStates.waiting_for_social_media)
async def handle_social_media(message: Message, state: FSMContext):
    """Handle social media input."""
    social_media = message.text.strip()
    await state.update_data(social_media=social_media)
    
    # Get username from user profile
    username = message.from_user.username
    if username:
        username = '@' + username
        await state.update_data(telegram_username=username)
        
        next_text = (
            "✅ Социальные сети сохранены\n\n"
            f"Ваш Telegram username: {username}\n\n"
            "Это ваш username?"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да, это я", callback_data="premium:confirm_username")]
        ])
        
        await message.answer(next_text, reply_markup=keyboard)
        await state.set_state(PremiumPostingStates.waiting_for_username_confirmation)
    else:
        next_text = (
            "✅ Социальные сети сохранены\n\n"
            "У вас не указан username в профиле Telegram\\.\n"
            "Укажите ваш Telegram @username:"
        )
        
        await message.answer(next_text)
        await state.set_state(PremiumPostingStates.waiting_for_telegram_username)

@router.callback_query(PremiumPostingStates.waiting_for_username_confirmation, F.data == "premium:confirm_username")
async def confirm_username(callback: CallbackQuery, state: FSMContext):
    """Confirm username from profile."""
    await callback.message.delete()
    
    next_text = (
        "✅ Telegram username подтвержден\n\n"
        "Теперь укажите ваш основной номер телефона (+35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx):"
    )
    
    await callback.message.answer(next_text)
    await state.set_state(PremiumPostingStates.waiting_for_phone_main)
    await callback.answer()



@router.message(PremiumPostingStates.waiting_for_telegram_username)
async def handle_telegram_username(message: Message, state: FSMContext):
    """Handle Telegram username input."""
    username = message.text.strip()
    
    if not username.startswith('@'):
        username = '@' + username
    
    await state.update_data(telegram_username=username)
    
    next_text = (
        "✅ Telegram username сохранен\n\n"
        "Теперь укажите ваш основной номер телефона (+35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx):"
    )
    
    await message.answer(next_text)
    await state.set_state(PremiumPostingStates.waiting_for_phone_main)

@router.message(PremiumPostingStates.waiting_for_phone_main)
async def handle_phone_main(message: Message, state: FSMContext):
    """Handle main phone input."""
    phone = message.text.strip()
    
    # Basic validation
    if not phone.startswith('+351') or len(phone) < 12:
        await message.answer(
            "🚫 Неверный формат номера телефона\\.\n\n"
            "Используйте формат: +35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx\n"
            "Отправьте номер заново:"
        )
        return
    
    await state.update_data(phone_main=phone)
    
    next_text = (
        "✅ Основной телефон сохранен\n\n"
        "Укажите номер WhatsApp (если отличается от основного телефона, или напишите 'нет'):"
    )
    
    await message.answer(next_text)
    await state.set_state(PremiumPostingStates.waiting_for_phone_whatsapp)

@router.message(PremiumPostingStates.waiting_for_phone_whatsapp)
async def handle_phone_whatsapp(message: Message, state: FSMContext):
    """Handle WhatsApp phone input."""
    whatsapp = message.text.strip()
    
    if whatsapp.lower() != 'нет' and not whatsapp.startswith('+351'):
        await message.answer(
            "🚫 Неверный формат номера WhatsApp\\.\n\n"
            "Используйте формат: +35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx или напишите 'нет'\n"
            "Отправьте номер заново:"
        )
        return
    
    await state.update_data(phone_whatsapp=whatsapp)
    
    next_text = (
        "✅ WhatsApp сохранен\n\n"
        "Укажите ваше имя или название компании:"
    )
    
    await message.answer(next_text)
    await state.set_state(PremiumPostingStates.waiting_for_name)

@router.message(PremiumPostingStates.waiting_for_name)
async def handle_name(message: Message, state: FSMContext):
    """Handle name input."""
    name = message.text.strip()
    
    if len(name) < 2:
        await message.answer(
            "🚫 Имя должно содержать минимум 2 символа\\.\n\n"
            "Отправьте имя заново:"
        )
        return
    
    await state.update_data(name=name)
    
    # Show preview and ask for confirmation
    data = await state.get_data()
    
    # Get section with fallback
    section = data.get('section', 'job_offer')  # Default to job_offer if not set
    section_name = "Ищу работу" if section == "job_seeker" else "Предлагаю работу"
    media_list = data.get('media_list', [])
    media_count = len(media_list)
    
    # Format post in final publication format
    from services.formatting import format_premium_posting, format_premium_posting_html
    
    # Prepare data for formatting
    post_data = {
        'mode': section,
        'description': data['description'],
        'social_media': data['social_media'],
        'telegram_username': data['telegram_username'],
        'phone_main': data['phone_main'],
        'phone_whatsapp': data['phone_whatsapp'],
        'name': data['name'],
        'cities': data.get('cities', ['online'])  # Use actual cities from state
    }
    
    final_post_text = format_premium_posting_html(post_data)
    
    # Send preview info message first
    preview_info_text = (
        "📋 Предварительный просмотр премиум-поста:\n\n"
        f"Медиа: {media_count} файл(ов)\n"
        f"Стоимость: €50"
    )
    
    await message.answer(preview_info_text)
    
    # Send media with caption as one message
    if media_list:
        # Send media group if multiple media
        if len(media_list) > 1:
            from aiogram.types import InputMediaPhoto, InputMediaVideo
            
            media_group = []
            for i, media in enumerate(media_list):
                if i == 0:  # First media gets the caption
                    if media['type'] == 'photo':
                        media_group.append(InputMediaPhoto(
                            media=media['file_id'],
                            caption=final_post_text,
                            parse_mode="HTML"
                        ))
                    else:
                        media_group.append(InputMediaVideo(
                            media=media['file_id'],
                            caption=final_post_text,
                            parse_mode="HTML"
                        ))
                else:
                    if media['type'] == 'photo':
                        media_group.append(InputMediaPhoto(media=media['file_id']))
                    else:
                        media_group.append(InputMediaVideo(media=media['file_id']))
            
            # Send media group
            await message.answer_media_group(media=media_group)
            
            # Send buttons as separate message
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(
                text="Всё ок, публикуем",
                callback_data="confirm_premium_post"
            ))
            builder.add(InlineKeyboardButton(
                text="← Назад",
                callback_data="premium:go_back"
            ))
            builder.adjust(2)
            
            await message.answer("Подтвердите создание премиум поста:", reply_markup=builder.as_markup())
        else:
            # Single media
            media = media_list[0]
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(
                text="Всё ок, публикуем",
                callback_data="confirm_premium_post"
            ))
            builder.add(InlineKeyboardButton(
                text="← Назад",
                callback_data="premium:go_back"
            ))
            builder.adjust(2)
            
            if media['type'] == 'photo':
                await message.answer_photo(
                    photo=media['file_id'],
                    caption=final_post_text,
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML"
                )
            else:
                await message.answer_video(
                    video=media['file_id'],
                    caption=final_post_text,
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML"
                )
    else:
        # No media - send text only
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="Всё ок, публикуем",
            callback_data="confirm_premium_post"
        ))
        builder.add(InlineKeyboardButton(
            text="← Назад",
            callback_data="premium:go_back"
        ))
        builder.adjust(2)
        
        await message.answer(final_post_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    
    await state.set_state(PremiumPostingStates.waiting_for_confirmation)

@router.callback_query(F.data == "premium:go_back")
async def go_back_premium(callback: CallbackQuery, state: FSMContext):
    """Go back to previous step in premium posting."""
    current_state = await state.get_state()
    
    try:
        # Try to delete the message, but don't fail if it doesn't exist
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete message: {e}")
    
    next_text = (
        "Укажите ваше имя или название компании:"
    )
    
    await callback.message.answer(next_text)
    await state.set_state(PremiumPostingStates.waiting_for_name)
    await callback.answer()

@router.callback_query(PremiumPostingStates.waiting_for_section_choice, F.data == "premium:section_job_seeker")
async def choose_job_seeker_section(callback: CallbackQuery, state: FSMContext):
    """Choose job seeker section."""
    await state.update_data(section="job_seeker")
    
    media_text = (
        "✅ Раздел выбран: *Ищу работу*\n\n"
        "Теперь нажмите скрепку 📎 чтобы отправить фото или видео для вашего объявления\\. ❗️Без текстового описания \\(только медиа\\):"
    )
    
    await callback.message.edit_text(
        media_text,
        reply_markup=get_back_button("premium_posting"),
        parse_mode="MarkdownV2"
    )
    await state.set_state(PremiumPostingStates.waiting_for_media)
    await callback.answer()

@router.callback_query(PremiumPostingStates.waiting_for_section_choice, F.data == "premium:section_job_offer")
async def choose_job_offer_section(callback: CallbackQuery, state: FSMContext):
    """Choose job offer section."""
    await state.update_data(section="job_offer")
    
    media_text = (
        "✅ Раздел выбран: *Предлагаю работу*\n\n"
        "Теперь нажмите скрепку 📎 чтобы отправить фото или видео для вашего объявления\\. ❗️Без текстового описания \\(только медиа\\):"
    )
    
    await callback.message.edit_text(
        media_text,
        reply_markup=get_back_button("premium_posting"),
        parse_mode="MarkdownV2"
    )
    await state.set_state(PremiumPostingStates.waiting_for_media)
    await callback.answer()



@router.callback_query(PremiumPostingStates.waiting_for_confirmation, F.data == "confirm_premium_post")
async def confirm_premium_post(callback: CallbackQuery, state: FSMContext, bot=None):
    """Confirm premium post creation."""
    logger.info(f"Premium post confirmation handler called for user {callback.from_user.id}")
    data = await state.get_data()
    logger.info(f"Premium post data: {data}")
    
    # Get or create user
    user = db.get_user(callback.from_user.id)
    if not user:
        user_id = db.create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )
    else:
        user_id = user['id']
    
    # Prepare data for database
    db_data = data.copy()
    # Convert section to mode for database compatibility
    if 'section' in db_data:
        db_data['mode'] = db_data['section']
        del db_data['section']
    
    # Add missing required fields and convert lists to strings
    import json
    
    # Handle cities - convert list to string if needed
    cities = data.get('cities', ['online'])
    if isinstance(cities, list):
        db_data['cities'] = json.dumps(cities)
    else:
        db_data['cities'] = cities
    
    # Handle media data - use first media for compatibility
    media_list = data.get('media_list', [])
    if media_list:
        first_media = media_list[0]
        db_data['media_file_id'] = first_media['file_id']
        db_data['media_type'] = first_media['type']
        # Convert media_list to JSON string for database storage
        db_data['media_list'] = json.dumps(media_list)
    
    # Create premium post
    post_id = db.create_premium_post(user_id, **db_data)
    
    # Send to admin for approval with media and buttons
    try:
        logger.info(f"Sending premium post #{post_id} to admin {336224597}")
        
        # Format post in final publication format
        from services.formatting import format_premium_posting, format_premium_posting_html
        
        # Prepare data for formatting
        section = data.get('section', 'job_offer')  # Default to job_offer if not set
        post_data = {
            'mode': section,
            'description': data['description'],
            'social_media': data['social_media'],
            'telegram_username': data['telegram_username'],
            'phone_main': data['phone_main'],
            'phone_whatsapp': data['phone_whatsapp'],
            'name': data['name'],
            'cities': data.get('cities', ['online'])  # Use actual cities from state
        }
        
        final_post_text = format_premium_posting_html(post_data)
        
        # Add admin info header
        admin_header = (
            f"💎 <b>Новый премиум-пост #{post_id}</b>\n"
            f"<b>От:</b> {callback.from_user.first_name} (@{callback.from_user.username})\n"
            f"<b>ID:</b> {callback.from_user.id}\n\n"
        )
        
        admin_text = admin_header + final_post_text
        
        admin_builder = InlineKeyboardBuilder()
        admin_builder.add(InlineKeyboardButton(
            text="✅ Подтвердить оплату",
            callback_data=f"admin:approve_premium:{post_id}"
        ))
        admin_builder.add(InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"admin:reject_premium:{post_id}"
        ))
        admin_builder.adjust(2)
        
        # Send post with media and buttons
        media_list = data.get('media_list', [])
        if media_list:
            if len(media_list) > 1:
                # Send media group with caption and buttons
                from aiogram.types import InputMediaPhoto, InputMediaVideo
                
                media_group = []
                for i, media in enumerate(media_list):
                    if i == 0:  # First media gets the caption and buttons
                        if media['type'] == 'photo':
                            media_group.append(InputMediaPhoto(
                                media=media['file_id'],
                                caption=admin_text,
                                parse_mode="HTML"
                            ))
                        else:
                            media_group.append(InputMediaVideo(
                                media=media['file_id'],
                                caption=admin_text,
                                parse_mode="HTML"
                            ))
                    else:
                        if media['type'] == 'photo':
                            media_group.append(InputMediaPhoto(media=media['file_id']))
                        else:
                            media_group.append(InputMediaVideo(media=media['file_id']))
                
                published_messages = await callback.bot.send_media_group(
                    chat_id=336224597,
                    media=media_group
                )
                message = published_messages[0] if published_messages else None
                
                # Send buttons as separate message
                await callback.bot.send_message(
                    chat_id=336224597,
                    text="Действия с премиум-постом:",
                    reply_markup=admin_builder.as_markup()
                )
            else:
                # Single media with caption and buttons
                media = media_list[0]
                if media['type'] == 'photo':
                    message = await callback.bot.send_photo(
                        chat_id=336224597,
                        photo=media['file_id'],
                        caption=admin_text,
                        reply_markup=admin_builder.as_markup(),
                        parse_mode="HTML"
                    )
                else:
                    message = await callback.bot.send_video(
                        chat_id=336224597,
                        video=media['file_id'],
                        caption=admin_text,
                        reply_markup=admin_builder.as_markup(),
                        parse_mode="HTML"
                    )
        else:
            # No media, send text with buttons
            message = await callback.bot.send_message(
                chat_id=336224597,
                text=admin_text,
                reply_markup=admin_builder.as_markup(),
                parse_mode="HTML"
            )
        
        logger.info(f"Successfully sent premium post #{post_id} to admin, message_id: {message.message_id if message else 'N/A'}")
    except Exception as e:
        logger.error(f"Failed to send premium post to admin: {e}")
        # Don't show error to user, just log it
    
    success_text = (
        "✅ *Премиум\\-пост отправлен на подтверждение\\!*\n\n"
        f"Его стоимость: €50\n\n"
        "*Что дальше:*\n"
        "1\\. В ближайшее время с вами свяжутся для получения оплаты\\.\n"
        "2\\. После получения оплаты ваш пост будет одобрен к публикации и автоматически опубликован в Справочнике\\.\n"
        "3\\. По всем вопросам обращайтесь к [Администратору](https://t\\.me/andreytelegraf)\\."
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="go:main"
    ))
    
    await callback.message.edit_text(
        success_text,
        reply_markup=builder.as_markup(),
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )
    await state.clear()
    await callback.answer()
