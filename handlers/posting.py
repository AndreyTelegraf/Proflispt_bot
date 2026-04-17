"""Posting handlers for Work in Portugal Bot."""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from database import db
from utils import validate_phone_number, validate_social_media, format_social_media, get_social_media_name, clean_user_input, format_description_for_preview, clean_user_input_advanced, clean_user_input_for_links, validate_any_link, remove_urls_from_text
from services.validation import validate_description_content, validate_geotags

logger = logging.getLogger(__name__)

router = Router()


def get_back_button(back_to: str = "go:main") -> InlineKeyboardMarkup:
    """Get back button keyboard."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="← Назад", callback_data=back_to))
    return builder.as_markup()


def get_smart_back_button(current_state: str) -> InlineKeyboardMarkup:
    """Get smart back button based on current state."""
    builder = InlineKeyboardBuilder()
    
    # Define navigation flow
    navigation_map = {
        "waiting_for_description": "back_to_cities",
        "waiting_for_social_media": "back_to_description",
        "waiting_for_telegram_username": "back_to_social_media", 
        "waiting_for_phone_main": "back_to_telegram_username",
        "waiting_for_phone_whatsapp": "back_to_phone_main",
        "waiting_for_name": "back_to_phone_whatsapp",
        "waiting_for_custom_city": "back_to_cities"
    }
    
    back_to = navigation_map.get(current_state, "go:main")
    builder.add(InlineKeyboardButton(text="← Назад", callback_data=back_to))
    return builder.as_markup()


def get_username_created_keyboard() -> InlineKeyboardMarkup:
    """Get username created keyboard."""
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(
        text="@username создан",
        callback_data="username:created"
    ))

    builder.add(InlineKeyboardButton(
        text="← Назад",
        callback_data="go:main"
    ))

    builder.adjust(1)  # 1 button per row
    return builder.as_markup()


def get_or_create_user_db_id(telegram_user) -> int:
    """Get or create user in database and return internal user_id."""
    user = db.get_user(telegram_user.id)
    if not user:
        return db.create_user(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name
        )
    return user['id']


async def handle_telegram_username_check(message: Message, state: FSMContext):
    """Handle Telegram username check from user profile."""
    user = message.from_user

    if user.username:
        # Username exists, format it and save
        telegram_username = f"@{user.username}"
        await state.update_data(telegram_username=telegram_username)

        # Check phone number from user profile
        await handle_phone_check(message, state)
    else:
        # Username doesn't exist, show instructions
        instructions_text = (
            "Не хватает вашего юзернейма в телеграме, без него мы не публикуем.\n\n"
            "Как создать @username в Телеграме:\n"
            "1. Нажмите на три черточки в правом верхнем углу;\n"
            "2. Тапните на «Настройки»;\n"
            "3. Коснитесь поля «Имя пользователя»;\n"
            "4. Введите уникальное имя начинающееся с @;\n"
            "5. Сохраните нажав на кнопку \"Ок\" в правом верхнем углу.\n"
            "6. Нажмите кнопку \"@username создан\" и продолжайте."
        )

        await message.answer(
            instructions_text,
            reply_markup=get_username_created_keyboard()
        )
        await state.set_state("waiting_for_username_creation")


async def handle_phone_check(message: Message, state: FSMContext):
    """Handle phone number check from user profile."""
    user = message.from_user

    # Check if user has phone number in profile
    if hasattr(user, 'phone_number') and user.phone_number:
        # Phone number exists in profile, save it
        phone_main = user.phone_number
        await state.update_data(phone_main=phone_main)

        # Ask for WhatsApp (optional)
        data = await state.get_data()
        await message.answer(
            f"Telegram: {data['telegram_username']}\n"
            f"Телефон: {phone_main}\n\n"
            f"Укажите номер WhatsApp (если отличается от основного) или напишите 'нет':",
            reply_markup=get_smart_back_button("waiting_for_phone_whatsapp")
        )
        await state.set_state("waiting_for_phone_whatsapp")
    else:
        # Phone number doesn't exist in profile, ask user to enter it
        data = await state.get_data()
        await message.answer(
            f"Telegram: {data['telegram_username']}\n\n"
            f"Укажите ваш основной номер телефона в формате +35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx:",
            reply_markup=get_smart_back_button("waiting_for_phone_main")
        )
        await state.set_state("waiting_for_phone_main")


@router.message(F.text)
async def handle_text_input(message: Message, state: FSMContext):
    """Handle text input for various states."""
    current_state = await state.get_state()

    if current_state == "waiting_for_custom_city":
        # Parse custom cities
        cities_input = clean_user_input_advanced(message.text)
        cities = [clean_user_input_advanced(city) for city in cities_input.split(",")]
        cities = [city for city in cities if city]  # Remove empty cities

        # Валидируем геотеги
        is_valid, invalid_tags = validate_geotags(cities)
        
        if not is_valid:
            invalid_tags_text = ", ".join(invalid_tags)
            await message.answer(
                f"Обнаружены недопустимые геотеги: {invalid_tags_text}\n\n"
                f"Допустимые геотеги:\n"
                f"• Основные города: Lisboa, Porto, Coimbra, Braga, Faro, Leiria, Sintra, Cascais\n"
                f"• Регионы: Algarve, Alentejo, Centro, Norte, Madeira, Açores\n"
                f"• Другие города: Amadora, Almada, Setúbal, Évora, Funchal, Aveiro, Guimarães\n"
                f"• Туристические города: Albufeira, Lagos, Nazaré, Óbidos, Tomar, Viana do Castelo\n"
                f"• Специальные теги: \\#online, \\#europe, \\#remote, \\#worldwide\n\n"
                f"Полный список доступен в меню выбора городов.\n"
                f"Пожалуйста, введите только допустимые геотеги:",
                reply_markup=get_smart_back_button("waiting_for_custom_city")
            )
            return

        await state.update_data(cities=cities)

        # Get current mode from state
        state_data = await state.get_data()
        mode = state_data.get('mode', 'seeking')

        # Prepare description text based on mode
        if mode == "seeking":
            description_text = (
                f"Города: {', '.join(cities)}\n\n"
                "Отправьте описание работы, которую вы ищите, например:\n"
                "• 'Ищу работу водителем с личным авто'\n"
                "• 'Ищу вакансию в разработке python'\n"
                "• 'Ищу подработку в сфере услуг'\n"
                "• 'Ищу парт-тайм официантом'\n"
                "• 'Ищу работу на стройке'\n"
                "Плюс ваше резюме или описание опыта и навыков.\n"
                "КОНТАКТЫ ПОКА НЕ НУЖНО"
            )
        else:  # offering
            description_text = (
                f"Города: {', '.join(cities)}\n\n"
                "Отправьте описание вашей вакансии.\n"
                "Если вакансий несколько, сформируйте описание так, чтобы это было понятно.\n"
                "Начните с ключевых слов, например:\n"
                "• 'Предлагаю работу водителю с личным авто'\n"
                "• 'Требуется официант в кафе-ресторан'\n"
                "• 'Ищу кто сможет починить жалюзи'\n"
                "• 'Нужны разнорабочие на стройку'\n"
                "• 'Ищем уборщицу на парт-тайм'\n"
                "КОНТАКТЫ ПОКА НЕ НУЖНО"
            )

        # Ask for description
        await message.answer(
            description_text,
            reply_markup=get_smart_back_button("waiting_for_description")
        )
        await state.set_state("waiting_for_description")

    elif current_state == "waiting_for_description":
        # Clean the description using advanced cleaning (removes emojis, formatting, media, URLs)
        description = clean_user_input_advanced(message.text)

        if len(description) < 10:
            await message.answer(
                "🚫 Описание слишком короткое. Пожалуйста, напишите более подробное описание (минимум 10 символов).",
                reply_markup=get_smart_back_button("waiting_for_description")
            )
            return

        # Проверяем описание на наличие запрещенных элементов
        is_valid, violations = validate_description_content(description)
        
        if not is_valid:
            violations_text = "\n• ".join(violations)
            await message.answer(
                f"🚫 В описании не допускаются контакты и ссылки, их нужно будет вводить на следующих шагах. Это лишнее:\n\n"
                f"• {violations_text}\n\n"
                f"Пожалуйста, переделайте описание в соответствии с правилами:\n"
                f"• Геотеги вы уже ввели\n"
                f"• Описание должно содержать только текст, без эмодзи\n"
                f"• Контакты (@username, телефоны, email) и ссылки – на следующих шагах\n\n"
                f"Отправьте исправленное описание заново:",
                reply_markup=get_smart_back_button("waiting_for_description")
            )
            return

        await state.update_data(description=description)

        # Ask for links
        preview_description = format_description_for_preview(description)
        await message.answer(
            f"Описание: {preview_description}\n\nТеперь укажите любые ссылки, имеющие отношение к делу: ваш сайт, социальные сети, портфолио и т.д.\n\nМожно указать несколько ссылок через запятую, точку с запятой или с новой строки.\nНапример:\n• https://instagram.com/username, https://linkedin.com/in/username\n• https://mycompany.com\n• Или напишите 'нет'",
            reply_markup=get_smart_back_button("waiting_for_social_media"),
            disable_web_page_preview=True
        )
        await state.set_state("waiting_for_social_media")

    elif current_state == "waiting_for_social_media":
        # Parse multiple links separated by commas, semicolons, or newlines
        raw_input = message.text
        links = []
        
        # Split by common separators (handle mixed separators)
        raw_links = []
        current_input = raw_input
        
        # First split by newlines
        if '\n' in current_input:
            parts = current_input.split('\n')
            for part in parts:
                if ',' in part:
                    raw_links.extend(part.split(','))
                elif ';' in part:
                    raw_links.extend(part.split(';'))
                else:
                    raw_links.append(part)
        elif ',' in current_input:
            raw_links = current_input.split(',')
        elif ';' in current_input:
            raw_links = current_input.split(';')
        else:
            # No separators found, treat as single link
            raw_links = [raw_input]
        
        # Clean and validate each link
        for link in raw_links:
            cleaned_link = clean_user_input_for_links(link.strip())
            if cleaned_link and cleaned_link.lower() not in ['нет', 'no', 'none', '']:
                if validate_any_link(cleaned_link):
                    links.append(cleaned_link)
                else:
                    await message.answer(
                        f"🚫 Неверный формат ссылки: {cleaned_link}\n\n"
                        "Вы можете указать:\n"
                        "• Любой веб-сайт: https://example.com\n"
                        "• Социальные сети: https://instagram.com/username, @username\n"
                        "• LinkedIn: https://linkedin.com/in/username\n"
                        "• YouTube: https://youtube.com/@channel\n"
                        "• GitHub: https://github.com/username\n"
                        "• Или любую другую ссылку\n"
                        "• Или напишите 'нет'",
                        reply_markup=get_smart_back_button("waiting_for_social_media")
                    )
                    return
        
        # Store links as JSON string
        import json
        social_media = json.dumps(links) if links else 'нет'
        await state.update_data(social_media=social_media)

        # Automatically get Telegram username from user profile
        await handle_telegram_username_check(message, state)

    elif current_state == "waiting_for_phone_main":
        phone_main = clean_user_input_advanced(message.text)

        if not validate_phone_number(phone_main):
            await message.answer(
                "🚫 Неверный формат номера телефона. Укажите в формате +35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx",
                reply_markup=get_smart_back_button("waiting_for_phone_main")
            )
            return

        await state.update_data(phone_main=phone_main)

        # Ask for WhatsApp (optional)
        data = await state.get_data()
        telegram_username = data.get('telegram_username', '')

        await message.answer(
            f"Telegram: {telegram_username}\n"
            f"Телефон: {phone_main}\n\n"
            f"Укажите номер WhatsApp (если отличается от основного) или напишите 'нет':",
            reply_markup=get_smart_back_button("waiting_for_phone_whatsapp")
        )
        await state.set_state("waiting_for_phone_whatsapp")

    elif current_state == "waiting_for_phone_whatsapp":
        phone_whatsapp = clean_user_input_advanced(message.text)

        if phone_whatsapp.lower() not in ['нет', 'no', 'none', '']:
            if not validate_phone_number(phone_whatsapp):
                await message.answer(
                    "🚫 Неверный формат номера WhatsApp. Укажите в формате +35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx или напишите 'нет':",
                    reply_markup=get_smart_back_button("waiting_for_phone_whatsapp")
                )
                return
            
        await state.update_data(phone_whatsapp=phone_whatsapp)

        # Ask for name
        await message.answer(
            "Укажите ваше имя:",
            reply_markup=get_smart_back_button("waiting_for_name")
        )
        await state.set_state("waiting_for_name")

    elif current_state == "waiting_for_name":
        name = clean_user_input_advanced(message.text)

        if len(name) < 2:
            await message.answer(
                "🚫 Имя слишком короткое. Пожалуйста, укажите полное имя.",
                reply_markup=get_smart_back_button("waiting_for_name")
            )
            return

        await state.update_data(name=name)

        # Show confirmation using proper preview function
        data = await state.get_data()
        
        # Create a temporary JobPosting object for preview
        from models.job_posting import JobPosting
        from datetime import datetime
        
        temp_posting = JobPosting(
            id=None,
            user_id=message.from_user.id,
            mode=data.get('mode', 'seeking'),
            cities=data.get('cities', []),
            description=data.get('description', ''),
            social_media=data.get('social_media', 'нет'),
            telegram_username=data.get('telegram_username', ''),
            phone_main=data.get('phone_main', ''),
            phone_whatsapp=data.get('phone_whatsapp', 'нет'),
            name=data.get('name', ''),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        from services.formatting import format_preview
        confirmation_text = format_preview(temp_posting)
        
        # Add reminder note
        reminder_note = (
            "\n\n"
            "📌 *Памятка:*\n"
            "• Публикация бесплатна, пожалуйста, будьте на связи\\.\n"
            "• Если объявление утратило актуальность – удалите его\\.\n"
            "• Игнор входящих звонков и сообщений может привести к бану\\."
        )
        confirmation_text += reminder_note

        # Create confirmation keyboard
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="✅ Опубликовать", callback_data="confirm:post"))
        builder.add(InlineKeyboardButton(text="❌ Отменить", callback_data="go:main"))
        builder.adjust(1)

        await message.answer(
            confirmation_text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        await state.set_state("waiting_for_confirmation")


@router.callback_query(F.data == "username:created")
async def handle_username_created(callback: CallbackQuery, state: FSMContext):
    """Handle username created button press."""
    # Check username again
    user = callback.from_user

    if user.username:
        # Username exists, format it and save
        telegram_username = f"@{user.username}"
        await state.update_data(telegram_username=telegram_username)

        # Check phone number from user profile
        await handle_phone_check_callback(callback, state)
    else:
        # Username still doesn't exist, show instructions again
        instructions_text = (
            "Не хватает вашего юзернейма в телеграме, без него мы не публикуем.\n\n"
            "Как создать @username в Телеграме:\n"
            "1. Нажмите на три черточки в правом верхнем углу;\n"
            "2. Тапните на «Настройки»;\n"
            "3. Коснитесь поля «Имя пользователя»;\n"
            "4. Введите уникальное имя начинающееся с @;\n"
            "5. Сохраните нажав на кнопку \"Ок\" в правом верхнем углу.\n"
            "6. Нажмите кнопку \"@username создан\" и продолжайте."
        )

        await callback.message.edit_text(
            instructions_text,
            reply_markup=get_username_created_keyboard()
        )

    await callback.answer()


async def handle_phone_check_callback(callback: CallbackQuery, state: FSMContext):
    """Handle phone number check from user profile for callback queries."""
    user = callback.from_user

    # Check if user has phone number in profile
    if hasattr(user, 'phone_number') and user.phone_number:
        # Phone number exists in profile, save it
        phone_main = user.phone_number
        await state.update_data(phone_main=phone_main)

        # Ask for WhatsApp (optional)
        data = await state.get_data()
        await callback.message.edit_text(
            f"Telegram: {data['telegram_username']}\n"
            f"Телефон: {phone_main}\n\n"
            f"Укажите номер WhatsApp (если отличается от основного) или напишите 'нет':",
            reply_markup=get_smart_back_button("waiting_for_phone_whatsapp")
        )
        await state.set_state("waiting_for_phone_whatsapp")
    else:
        # Phone number doesn't exist in profile, ask user to enter it
        data = await state.get_data()
        await callback.message.edit_text(
            f"Telegram: {data['telegram_username']}\n\n"
            f"Укажите ваш основной номер телефона в формате +35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx:",
            reply_markup=get_smart_back_button("waiting_for_phone_main")
        )
        await state.set_state("waiting_for_phone_main")


@router.callback_query(F.data == "confirm:post")
async def handle_confirmation(callback: CallbackQuery, state: FSMContext):
    """Handle publication confirmation."""
    data = await state.get_data()
    
    # Create or get user
    user_id = db.create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name
    )
    
    # Check posting limit by phone number (more reliable than user_id)
    # This prevents creating multiple posts from one phone number via different accounts
    phone_main = data.get('phone_main', '')
    phone_whatsapp = data.get('phone_whatsapp', '')
    
    if phone_main:
        can_post, earliest_next_post_date = db.check_phone_posting_limit(phone_main, phone_whatsapp)
        
        if not can_post:
            # Format the date for display
            date_str = earliest_next_post_date.strftime("%d.%m.%Y %H:%M") if earliest_next_post_date else "неизвестно"
            
            limit_message = (
                f"⚠️ Лимит публикаций превышен\n\n"
                f"С этим номером телефона уже есть 3 активных объявления за последние 30 дней.\n\n"
                f"Чтобы опубликовать ещё одно объявление, удалите минимум одно старое или подождите до {date_str}\n\n"
                f"Управляйте своими объявлениями в разделе 'Мои объявления'."
            )
            
            # Create keyboard with back button and my postings button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Мои объявления", callback_data="my_postings")],
                [InlineKeyboardButton(text="← Назад", callback_data="go:main")]
            ])
            
            await callback.message.edit_text(limit_message, reply_markup=keyboard)
            await callback.answer()
            return
    
    # Fallback: only check by user_id when there is no phone number in the draft.
    # If a phone number is present, the phone-based limit above is the source of truth.
    if not phone_main:
        can_post, earliest_next_post_date = db.check_user_posting_limit(user_id)
        
        if not can_post:
            # Format the date for display
            date_str = earliest_next_post_date.strftime("%d.%m.%Y %H:%M") if earliest_next_post_date else "неизвестно"
            
            limit_message = (
                f"⚠️ Лимит публикаций превышен\n\n"
                f"У вас уже есть 3 активных объявления за последние 30 дней.\n\n"
                f"Чтобы опубликовать ещё одно объявление, удалите минимум одно старое или подождите до {date_str}\n\n"
                f"Управляйте своими объявлениями в разделе 'Мои объявления'."
            )
            
            # Create keyboard with back button and my postings button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Мои объявления", callback_data="my_postings")],
                [InlineKeyboardButton(text="← Назад", callback_data="go:main")]
            ])
            
            await callback.message.edit_text(limit_message, reply_markup=keyboard)
            await callback.answer()
            return
    
    # Check for duplicate postings
    is_duplicate = db.check_duplicate_posting(user_id, data.get('mode'), data.get('description'))
    
    if is_duplicate:
        duplicate_message = (
            f"⚠️ Похожее объявление уже существует\n\n"
            f"У вас уже есть активное объявление с похожим описанием в режиме '{data.get('mode')}'.\n\n"
            f"Пожалуйста, отредактируйте существующее объявление или удалите его перед созданием нового.\n\n"
            f"Управляйте своими объявлениями в разделе 'Мои объявления'."
        )
        
        # Create keyboard with back button and my postings button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои объявления", callback_data="my_postings")],
            [InlineKeyboardButton(text="← Назад", callback_data="go:main")]
        ])
        
        await callback.message.edit_text(duplicate_message, reply_markup=keyboard)
        await callback.answer()
        return
    

    
    # Create job posting
    posting_id = db.create_job_posting(
        user_id=user_id,
        mode=data.get('mode'),
        cities=data.get('cities'),
        description=data.get('description'),
        social_media=data.get('social_media'),
        telegram_username=data.get('telegram_username'),
        phone_main=data.get('phone_main'),
        phone_whatsapp=data.get('phone_whatsapp'),
        name=data.get('name')
    )
    
    # Get posting from database
    posting_data = db.get_posting_by_id(posting_id)
    if not posting_data:
        await callback.message.edit_text(
            "🚫 Ошибка при создании объявления. Попробуйте еще раз.",
            reply_markup=get_back_button("go:main")
        )
        await callback.answer()
        return
    
    # Create JobPosting object
    from models.job_posting import JobPosting
    posting = JobPosting.from_dict(posting_data)
    
    # Publish to channel
    from services.publisher import Publisher
    publisher = Publisher(callback.bot)
    published_message = await publisher.publish_posting(posting, user_id)
    
    # Clear state
    await state.clear()
    
    # Prepare success message with link
    if published_message:
        # Create link to the published message
        # Get channel info to create proper link
        try:
            chat_info = await callback.bot.get_chat(Config.CHANNEL_ID)
            if chat_info.username:
                message_link = f"https://t.me/{chat_info.username}/{published_message.message_id}"
            else:
                # For private channels, we can't create a direct link
                message_link = None
        except Exception as e:
            logger.warning(f"Could not get channel info: {e}")
            message_link = None
        
        if message_link:
            success_text = (
                "✅ Объявление успешно опубликовано!\n\n"
                f"Спасибо за использование нашего бота. [Ваше объявление]({message_link}) будет доступно в канале."
            )
        else:
            success_text = (
                "✅ Объявление успешно опубликовано!\n\n"
                "Спасибо за использование нашего бота. Ваше объявление будет доступно в канале."
            )
    else:
        # Publication failed - delete the posting from database and show error
        try:
            db.delete_posting(posting_id)
            logger.warning(f"Deleted posting {posting_id} due to publication failure")
        except Exception as e:
            logger.error(f"Failed to delete posting {posting_id} after publication failure: {e}")
        
        error_text = (
            "🚫 Ошибка при публикации объявления\n\n"
            "К сожалению, не удалось опубликовать ваше объявление в канал. "
            "Пожалуйста, попробуйте еще раз позже или обратитесь к администратору."
        )
        
        await callback.message.edit_text(
            error_text,
            reply_markup=get_back_button("go:main")
        )
        await callback.answer()
        return
    
    # Send success message
    await callback.message.edit_text(
        success_text,
        reply_markup=get_back_button(),
        parse_mode="Markdown"
    )
    
    await callback.answer()


# Navigation handlers
@router.callback_query(F.data == "back_to_cities")
async def back_to_cities_selection(callback: CallbackQuery, state: FSMContext):
    """Go back to cities selection."""
    data = await state.get_data()
    mode = data.get('mode', 'seeking')
    
    if mode == "seeking":
        response_text = "Отлично, давайте найдём вам работу.\nГде вы её ищите? (можно выбрать несколько вариантов)"
    else:  # offering
        response_text = "Отлично, давайте закроем вашу вакансию.\nГде вы ищите сотрудников? (можно выбрать несколько вариантов)."
    
    # Create cities keyboard
    builder = InlineKeyboardBuilder()
    
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
        ("Другие города", "city:custom")
    ]
    
    for text, callback_data in cities:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    builder.add(InlineKeyboardButton(text="← Назад", callback_data="back_to_mode"))
    builder.adjust(3)  # 3 buttons per row
    
    await callback.message.edit_text(response_text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "back_to_description")
async def back_to_description(callback: CallbackQuery, state: FSMContext):
    """Go back to description step."""
    data = await state.get_data()
    mode = data.get('mode', 'seeking')
    cities = data.get('cities', [])
    
    # Get city names
    from config import Config
    city_names = [Config.CITIES.get(city, city) for city in cities]
    cities_text = ", ".join(city_names)
    
    # Prepare description text based on mode
    if mode == "seeking":
        description_text = (
            f"Города: {cities_text}\n\n"
            "Теперь оправьте описание работы, которую вы ищите, начинающееся например с фразы:\n\n"
            "• Ищу подработку в сфере услуг\n"
            "• Ищу парт-тайм официантом\n"
            "• Ищу работу на стройке...\n"
            "...дальше опишите свои навыки и опыт. \n\n"
            "⚠️ Контактов и ссылок в описании быть не должно, они вводятся на следующих шагах."
        )
    else:  # offering
        description_text = (
            f"Города: {cities_text}\n\n"
            "Теперь отправьте описание вашей вакансии.\n"
            "Если вакансий несколько, сформируйте описание так, чтобы это было понятно.\n"
            "Начните с ключевых слов, например:\n\n"
            "• Предлагаю работу водителю с личным авто\n"
            "• Требуется официант в кафе-ресторан\n"
            "• Ищу кто сможет починить жалюзи\n"
            "• Нужны разнорабочие на стройку\n"
            "• Ищем уборщицу на парт-тайм...\n\n"
            "⚠️ Контактов и ссылок в описании быть не должно, они вводятся в отдельные поля. Публикация одной и той же вакансии допускается не чаще раза в месяц. При наличии нескольких вакансий рекомендуется объединить их в одно объявление."
        )
    
    await callback.message.edit_text(
        description_text,
        reply_markup=get_smart_back_button("waiting_for_description")
    )
    await state.set_state("waiting_for_description")
    await callback.answer()


@router.callback_query(F.data == "back_to_social_media")
async def back_to_social_media(callback: CallbackQuery, state: FSMContext):
    """Go back to social media step."""
    data = await state.get_data()
    description = data.get('description', '')
    
    # Show description preview
    preview_text = format_description_for_preview(description)
    
    await callback.message.edit_text(
        f"Описание: {preview_text}\n\n"
        f"Теперь укажите любые ссылки, имеющие отношение к делу: ваш сайт, социальные сети, портфолио и т.д.\n\n"
        f"Можно указать несколько ссылок через запятую, точку с запятой или с новой строки.\n"
        f"Например:\n"
        f"• https://instagram.com/username, https://linkedin.com/in/username\n"
        f"• https://mycompany.com\n"
        f"• Или напишите 'нет'",
        reply_markup=get_smart_back_button("waiting_for_social_media"),
        disable_web_page_preview=True
    )
    await state.set_state("waiting_for_social_media")
    await callback.answer()


@router.callback_query(F.data == "back_to_telegram_username")
async def back_to_telegram_username(callback: CallbackQuery, state: FSMContext):
    """Go back to telegram username step."""
    # Check if user has username
    user = callback.from_user
    
    if user.username:
        # Username exists, format it and save
        telegram_username = f"@{user.username}"
        await state.update_data(telegram_username=telegram_username)
        
        # Continue to phone check
        await handle_phone_check(callback.message, state)
    else:
        # Username doesn't exist, show instructions with button
        instructions_text = (
            "Не хватает вашего юзернейма в телеграме, без него мы не публикуем.\n\n"
            "Как создать @username в Телеграме:\n"
            "1. Нажмите на три черточки в правом верхнем углу;\n"
            "2. Тапните на «Настройки»;\n"
            "3. Коснитесь поля «Имя пользователя»;\n"
            "4. Введите уникальное имя начинающееся с @;\n"
            "5. Сохраните нажав на кнопку \"Ок\" в правом верхнем углу.\n"
            "6. Нажмите кнопку \"@username создан\" и продолжайте."
        )
        
        await callback.message.edit_text(
            instructions_text,
            reply_markup=get_username_created_keyboard()
        )
        await state.set_state("waiting_for_username_creation")
    
    await callback.answer()


@router.callback_query(F.data == "back_to_phone_main")
async def back_to_phone_main(callback: CallbackQuery, state: FSMContext):
    """Go back to phone main step."""
    data = await state.get_data()
    telegram_username = data.get('telegram_username', '')
    
    await callback.message.edit_text(
        f"Telegram: {telegram_username}\n\n"
        f"Укажите ваш основной номер телефона в формате +35191xxxxxxx, +35192xxxxxxx, +35193xxxxxxx или +35196xxxxxxx:",
        reply_markup=get_smart_back_button("waiting_for_phone_main")
    )
    await state.set_state("waiting_for_phone_main")
    await callback.answer()


@router.callback_query(F.data == "back_to_phone_whatsapp")
async def back_to_phone_whatsapp(callback: CallbackQuery, state: FSMContext):
    """Go back to phone whatsapp step."""
    data = await state.get_data()
    telegram_username = data.get('telegram_username', '')
    phone_main = data.get('phone_main', '')
    
    await callback.message.edit_text(
        f"Telegram: {telegram_username}\n"
        f"Телефон: {phone_main}\n\n"
        f"Укажите номер WhatsApp (если отличается от основного) или напишите 'нет':",
        reply_markup=get_smart_back_button("waiting_for_phone_whatsapp")
    )
    await state.set_state("waiting_for_phone_whatsapp")
    await callback.answer()
