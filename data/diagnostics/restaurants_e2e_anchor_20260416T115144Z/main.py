"""Main entry point for Work in Portugal Bot."""

import asyncio
import logging
import sys
import os
import signal
import fcntl
import subprocess
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import ExceptionTypeFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ErrorEvent, Update
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.dispatcher.event.bases import UNHANDLED

from config import Config
from database import db
from handlers.posting import router as posting_router
from handlers.my_postings import router as my_postings_router
from handlers.admin import router as admin_router
from handlers.premium_posting import router as premium_posting_router
from handlers.premium_admin import router as premium_admin_router
from handlers.restaurants_schema import router as restaurants_schema_router
from handlers.section_catalog import router as section_catalog_router
from services.scheduler import start_scheduler, stop_scheduler
from middleware.ban_check import BanCheckMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Lock file for preventing multiple instances
LOCK_FILE = "bot.lock"

def cleanup_stale_processes():
    """Clean up only stale local lock artifacts.

    Do not kill processes here: systemd already manages the service lifecycle.
    """
    logger.info("Cleaning up stale lock artifacts...")
    
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
            logger.info("Removed stale lock file")
        except Exception as e:
            logger.warning(f"Error removing lock file: {e}")

class SingleInstance:
    """Ensure only one instance of the bot is running."""
    
    def __init__(self, lockfile):
        self.lockfile = lockfile
        self.fd = None
        
    def __enter__(self):
        """Acquire lock."""
        try:
            self.fd = open(self.lockfile, 'w')
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info(f"Lock acquired: {self.lockfile}")
            return self
        except IOError:
            logger.error(f"Another bot instance is already running")
            if self.fd:
                self.fd.close()
            sys.exit(1)
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock."""
        if self.fd:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                self.fd.close()
                os.remove(self.lockfile)
                logger.info("Lock released")
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")

def signal_handler(signum, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Create router
router = Router()


from keyboards.main import get_main_menu, get_back_button


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    if message.is_topic_message:
        logger.warning("TOPIC_DEBUG thread_id=%s chat_id=%s", message.message_thread_id, message.chat.id)
    await state.clear()
    
    logger.info(f"User {message.from_user.id} started bot")
    
    welcome_text = "Здравствуйте! 

Этот бот поможет вам опубликовать объявления в разделы Справочника.

Выберите действие:"
    
    await message.answer(welcome_text, reply_markup=get_main_menu())


@router.callback_query(F.data == "go:main")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    """Show main menu."""
    await state.clear()
    
    welcome_text = "Здравствуйте! 

Этот бот поможет вам опубликовать объявления в разделы Справочника.

Выберите действие:"
    
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu())
    await callback.answer()


@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    """Show help menu."""
    help_text = "❓ Помощь\n\nОбщие правила:\n• Одно объявление не чаще раза в месяц\n• Максимум 3 активных объявления на пользователя\n• Объявления автоматически удаляются через 30 дней\n• Объявление не опубликуется без @username и португальского номера телефона.\n\nШаги составления объявления (не вводите лишнего раньше времени):\n1. Хэштэги городов (\\#lisboa, \\#porto, \\#online)\n2. Описание работы (минимум 10 символов, без ссылок, эмоджи и контактов)\n3. Социальные сети и/или сайты (или \"нет\")\n4. Telegram @username\n5. Телефон (\\+35191xxxxxxx, \\+35192xxxxxxx, \\+35193xxxxxxx или \\+35196xxxxxxx)\n6. WhatsApp (если отличается от телефона)\n7. Имя или название компании."
    
    # Create help keyboard with "Позвать человека" button
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="👤 Позвать человека",
        url="https://t.me/andreytelegraf"
    ))
    builder.add(InlineKeyboardButton(
        text="← Назад",
        callback_data="go:main"
    ))
    builder.adjust(1)  # One button per row
    
    await callback.message.edit_text(help_text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("mode:"))
async def handle_mode_selection(callback: CallbackQuery, state: FSMContext):
    """Handle job posting mode selection."""
    mode = callback.data.split(":")[1]
    
    if mode == "seeking":
        mode_text = "Ищу работу"
        warning_text = ""
    elif mode == "offering":
        mode_text = "Предлагаю работу"
        warning_text = "\n⚠️ Внимание: Публикация одной и той же вакансии допускается не чаще раза в месяц. При наличии нескольких вакансий рекомендуется объединить их в одно объявление."
    else:
        await callback.answer("Неизвестный режим")
        return
    
    await state.update_data(mode=mode)
    
    # Check user posting limit
    from database import db
    user_id = callback.from_user.id
    
    # Get or create user
    user = db.get_user(user_id)
    if not user:
        user_id_db = db.create_user(
            telegram_id=user_id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )
    else:
        user_id_db = user['id']
    
    # Check posting limit
    can_post, earliest_next_post_date = db.check_user_posting_limit(user_id_db)
    
    if not can_post:
        # Format the date for display
        date_str = earliest_next_post_date.strftime("%d.%m.%Y")
        
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
    
    # User can post - continue with city selection
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


@router.callback_query(F.data == "back_to_mode")
async def back_to_mode_selection(callback: CallbackQuery, state: FSMContext):
    """Go back to mode selection."""
    # Clear cities from state
    await state.update_data(cities=None)
    
    # Show mode selection menu
    welcome_text = "Здравствуйте! 

Этот бот поможет вам опубликовать объявления в разделы Справочника.

Выберите действие:"
    
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("city:"))
async def handle_city_selection(callback: CallbackQuery, state: FSMContext):
    """Handle city selection."""
    city_key = callback.data.split(":")[1]
    
    # Get current mode from state
    state_data = await state.get_data()
    mode = state_data.get('mode', 'seeking')
    
    if city_key == "custom":
        await callback.message.edit_text(
            "Введите название города или городов (можно несколько через запят):",
            reply_markup=get_back_button("back_to_cities")
        )
        await state.set_state("waiting_for_custom_city")
    else:
        # Get city name from config
        city_name = Config.CITIES.get(city_key, city_key)
        
        # Save selected city
        await state.update_data(cities=[city_key])
        
        # Prepare description text based on mode
        if mode == "seeking":
            description_text = (
                f"Город: {city_name}\n\n"
                "Теперь оправьте описание работы, которую вы ищите, начинающееся например с фразы:\n\n"
                "• Ищу подработку в сфере услуг\n"
                "• Ищу парт-тайм официантом\n"
                "• Ищу работу на стройке...\n"
                "...дальше опишите свои навыки и опыт. \n\n"
                "⚠️ Контактов и ссылок в описании быть не должно, они вводятся на следующих шагах."
            )
        else:  # offering
            description_text = (
                f"Город: {city_name}\n\n"
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
        
        # Ask for description
        await callback.message.edit_text(
            description_text,
            reply_markup=get_back_button("back_to_cities")
        )
        await state.set_state("waiting_for_description")
    
    await callback.answer()


# Text input handlers are now in handlers/posting.py





@router.message(Command("cleanup"))
async def cmd_cleanup(message: Message):
    """Handle /cleanup command (admin only)."""
    # Check if user is admin (you can customize this check)
    admin_ids = Config.ADMIN_IDS
    
    if message.from_user.id not in admin_ids:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    
    await message.answer("🧹 Запуск очистки старых объявлений...")
    
    try:
        from services.scheduler import run_cleanup_now
        await run_cleanup_now(message.bot)
        await message.answer("✅ Очистка завершена!")
    except Exception as e:
        logger.error(f"Error during manual cleanup: {e}")
        await message.answer(f"🚫 Ошибка при очистке: {e}")

# Команды /ban и /unban перенесены в handlers/admin.py

@router.message(Command("unban"))
async def cmd_unban(message: Message):
    """Handle /unban command (admin only)."""
    # Check if user is admin
    admin_ids = Config.ADMIN_IDS
    
    if message.from_user.id not in admin_ids:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    
    # Формат: /unban <user_id>
    args = message.text.split()[1:]
    
    if len(args) != 1:
        await message.answer("📝 Использование: /unban <user_id>")
        return
    
    try:
        target_user_id = int(args[0])
        
        # Получаем пользователя
        target_user = db.get_user(target_user_id)
        if not target_user:
            await message.answer(f"🚫 Пользователь с ID {target_user_id} не найден в базе данных.")
            return
        
        # Проверяем, забанен ли пользователь
        is_banned, ban_info = db.is_user_banned(target_user_id)
        if not is_banned:
            await message.answer(f"ℹ️ Пользователь {target_user_id} не забанен.")
            return
        
        # Разбаниваем пользователя
        admin_user = db.get_user(message.from_user.id)
        if not admin_user:
            admin_user_id = db.create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
        else:
            admin_user_id = admin_user['id']
        
        success = db.unban_user(target_user_id, admin_user_id)
        
        if success:
            await message.answer(f"✅ Пользователь {target_user_id} разбанен.")
        else:
            await message.answer("🚫 Ошибка при разбане пользователя.")
            
    except ValueError:
        await message.answer("🚫 Неверный формат user_id. Используйте число.")


@router.message(Command("premium_posts"))
async def cmd_premium_posts(message: Message):
    """Handle /premium_posts command (admin only)."""
    # Check if user is admin
    admin_ids = Config.ADMIN_IDS
    
    if message.from_user.id not in admin_ids:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    
    # Get pending premium posts
    pending_posts = db.get_pending_premium_posts()
    
    if not pending_posts:
        await message.answer("📋 Нет ожидающих подтверждения премиум-постов.")
        return
    
    response = f"📋 Ожидающие подтверждения премиум-посты ({len(pending_posts)}):\n\n"
    
    for i, post in enumerate(pending_posts[:10], 1):  # Show first 10
        user_info = f"{post['telegram_id']} ({post['username'] or 'без username'})"
        response += f"{i}. **ID:** {post['id']}\n"
        response += f"   **Пользователь:** {user_info}\n"
        response += f"   **Тип:** {post['mode']}\n"
        response += f"   **Медиа:** {post['media_type']}\n"
        response += f"   **Создан:** {post['created_at']}\n"
        response += f"   **Стоимость:** €{post['payment_amount']}\n\n"
    
    if len(pending_posts) > 10:
        response += f"... и еще {len(pending_posts) - 10} постов"
    
    await message.answer(response, parse_mode="Markdown")


@router.message(Command("approve_payment"))
async def cmd_approve_payment(message: Message):
    """Handle /approve_payment command (admin only)."""
    # Check if user is admin
    admin_ids = Config.ADMIN_IDS
    
    if message.from_user.id not in admin_ids:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    
    # Format: /approve_payment <post_id> [notes]
    args = message.text.split()[1:]
    
    if len(args) < 1:
        await message.answer("📝 Использование: /approve_payment <post_id> [заметки]")
        return
    
    try:
        post_id = int(args[0])
        admin_notes = " ".join(args[1:]) if len(args) > 1 else None
        
        # Get premium post
        post = db.get_premium_post(post_id)
        if not post:
            await message.answer(f"🚫 Премиум-пост с ID {post_id} не найден.")
            return
        
        if post['payment_status'] != 'pending':
            await message.answer(f"🚫 Пост {post_id} уже обработан (статус: {post['payment_status']}).")
            return
        
        # Get admin user
        admin_user = db.get_user(message.from_user.id)
        if not admin_user:
            admin_user_id = db.create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
        else:
            admin_user_id = admin_user['id']
        
        # Approve payment
        success = db.approve_premium_post(post_id, admin_user_id, admin_notes)
        
        if success:
            await message.answer(
                f"✅ Оплата для поста {post_id} подтверждена!\n\n"
                f"**Пользователь:** {post['telegram_id']}\n"
                f"**Тип:** {post['mode']}\n"
                f"**Медиа:** {post['media_type']}\n"
                f"**Стоимость:** €{post['payment_amount']}\n\n"
                "Пост готов к публикации в канале.",
                parse_mode="Markdown"
            )
        else:
            await message.answer("🚫 Ошибка при подтверждении оплаты.")
            
    except ValueError:
        await message.answer("🚫 Неверный формат post_id. Используйте число.")


@router.message(Command("reject_payment"))
async def cmd_reject_payment(message: Message):
    """Handle /reject_payment command (admin only)."""
    # Check if user is admin
    admin_ids = Config.ADMIN_IDS
    
    if message.from_user.id not in admin_ids:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    
    # Format: /reject_payment <post_id> <reason>
    args = message.text.split()[1:]
    
    if len(args) < 2:
        await message.answer("📝 Использование: /reject_payment <post_id> <причина>")
        return
    
    try:
        post_id = int(args[0])
        reason = " ".join(args[1:])
        
        # Get premium post
        post = db.get_premium_post(post_id)
        if not post:
            await message.answer(f"🚫 Премиум-пост с ID {post_id} не найден.")
            return
        
        if post['payment_status'] != 'pending':
            await message.answer(f"🚫 Пост {post_id} уже обработан (статус: {post['payment_status']}).")
            return
        
        # Get admin user
        admin_user = db.get_user(message.from_user.id)
        if not admin_user:
            admin_user_id = db.create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
        else:
            admin_user_id = admin_user['id']
        
        # Reject payment
        success = db.reject_premium_post(post_id, admin_user_id, reason)
        
        if success:
            await message.answer(
                f"🚫 Оплата для поста {post_id} отклонена.\n\n"
                f"**Причина:** {reason}\n"
                f"**Пользователь:** {post['telegram_id']}\n"
                f"**Тип:** {post['mode']}",
                parse_mode="Markdown"
            )
        else:
            await message.answer("🚫 Ошибка при отклонении оплаты.")
            
    except ValueError:
        await message.answer("🚫 Неверный формат post_id. Используйте число.")


async def main():
    """Main function."""
    try:
        # Clean up any stale processes first
        cleanup_stale_processes()
        
        # Check if another instance is already running
        with SingleInstance(LOCK_FILE):
            # Validate configuration
            Config.validate()
            logger.info("Configuration validated successfully")

            # Initialize bot and dispatcher
            bot = Bot(token=Config.BOT_TOKEN)
            dp = Dispatcher(storage=MemoryStorage())

            # Register middleware
            dp.message.middleware(BanCheckMiddleware())
            dp.callback_query.middleware(BanCheckMiddleware())
            
            # Add logging middleware to track all messages
            @dp.message.middleware()
            async def log_all_messages(handler, event, data):
                if event.text and event.text.startswith('/ban'):
                    logger.info(f"[MAIN] Получена команда /ban: {event.text} от пользователя {event.from_user.id}")
                return await handler(event, data)

            # Error handler: suppress "message is not modified" (double-click, same content)
            @dp.error(ExceptionTypeFilter(TelegramBadRequest))
            async def handle_message_not_modified(event: ErrorEvent):
                if "message is not modified" in str(event.exception):
                    return  # Suppress - no action needed
                raise event.exception

            @dp.update.outer_middleware()
            async def log_unhandled_updates(handler, event: Update, data):
                result = await handler(event, data)
                if result is UNHANDLED:
                    try:
                        logger.warning(
                            "UNHANDLED_UPDATE type=%s payload=%s",
                            event.event_type,
                            event.model_dump_json(exclude_none=True)
                        )
                    except Exception as e:
                        logger.warning("UNHANDLED_UPDATE logging failed: %s", e)
                return result

            @dp.update.outer_middleware()
            async def log_unhandled_updates(handler, event: Update, data):
                result = await handler(event, data)
                if result is UNHANDLED:
                    try:
                        logger.warning(
                            "UNHANDLED_UPDATE type=%s payload=%s",
                            event.event_type,
                            event.model_dump_json(exclude_none=True)
                        )
                    except Exception as e:
                        logger.warning("UNHANDLED_UPDATE logging failed: %s", e)
                return result

            # Register routers
            # Admin router MUST be first to handle admin commands before other routers intercept them
            dp.include_router(admin_router)
            dp.include_router(router)
            dp.include_router(premium_posting_router)  # Premium posting first
            dp.include_router(premium_admin_router)  # Premium admin handlers
            dp.include_router(section_catalog_router)
            dp.include_router(restaurants_schema_router)
            dp.include_router(posting_router)
            dp.include_router(my_postings_router)

            logger.info("Work in Portugal Bot started successfully")

            # Start cleanup scheduler
            await start_scheduler(bot)
            logger.info("Cleanup scheduler started")

            # Start the dispatcher (blocks until shutdown)
            await dp.start_polling(bot, skip_updates=True)

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
