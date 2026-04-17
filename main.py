"""Main entry point for Work in Portugal Bot."""

import asyncio
import logging
import sys
import os
import signal
import fcntl
from aiogram import Bot, Dispatcher, Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import ExceptionTypeFilter, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ErrorEvent, Update, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.dispatcher.event.bases import UNHANDLED

from config import Config
from database import db
from handlers.start import router as start_router
from handlers.posting import router as posting_router
from handlers.my_postings import router as my_postings_router
from handlers.admin import router as admin_router
from handlers.premium_posting import router as premium_posting_router
from handlers.premium_admin import router as premium_admin_router
from handlers.restaurants_schema import router as restaurants_schema_router
from handlers.section_catalog import router as section_catalog_router
from services.scheduler import start_scheduler
from middleware.ban_check import BanCheckMiddleware
from keyboards.main import get_main_menu, get_back_button

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

LOCK_FILE = "bot.lock"


def build_main_menu_text() -> str:
    return (
        "Здравствуйте!\n\n"
        "Этот бот поможет вам опубликовать объявления в разделы Справочника.\n\n"
        "Выберите действие:"
    )


def cleanup_stale_processes() -> None:
    """Clean up only stale local lock artifacts.

    Do not kill processes here: systemd already manages the service lifecycle.
    """
    logger.info("Cleaning up stale lock artifacts...")

    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
            logger.info("Removed stale lock file")
        except Exception as e:
            logger.warning("Error removing lock file: %s", e)


class SingleInstance:
    """Ensure only one instance of the bot is running."""

    def __init__(self, lockfile: str):
        self.lockfile = lockfile
        self.fd = None

    def __enter__(self):
        try:
            self.fd = open(self.lockfile, "w")
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info("Lock acquired: %s", self.lockfile)
            return self
        except IOError:
            logger.error("Another bot instance is already running")
            if self.fd:
                self.fd.close()
            sys.exit(1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                self.fd.close()
                os.remove(self.lockfile)
                logger.info("Lock released")
            except Exception as e:
                logger.warning("Error releasing lock: %s", e)


def signal_handler(signum, frame):
    logger.info("Received signal %s, shutting down...", signum)
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

router = Router()


@router.callback_query(F.data == "go:main")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    """Show main menu."""
    await state.clear()
    welcome_text = build_main_menu_text()
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu())
    await callback.answer()


@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    """Show help menu."""
    help_text = (
        "❓ Помощь\n\n"
        "Общие правила:\n"
        "• Одно объявление не чаще раза в месяц\n"
        "• Максимум 3 активных объявления на пользователя\n"
        "• Объявления автоматически удаляются через 30 дней\n"
        "• Объявление не опубликуется без @username и португальского номера телефона.\n\n"
        "Шаги составления объявления (не вводите лишнего раньше времени):\n"
        "1. Хэштэги городов (\\#lisboa, \\#porto, \\#online)\n"
        "2. Описание работы (минимум 10 символов, без ссылок, эмоджи и контактов)\n"
        "3. Социальные сети и/или сайты (или \"нет\")\n"
        "4. Telegram @username\n"
        "5. Телефон (\\+35191xxxxxxx, \\+35192xxxxxxx, \\+35193xxxxxxx или \\+35196xxxxxxx)\n"
        "6. WhatsApp (если отличается от телефона)\n"
        "7. Имя или название компании."
    )

    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="👤 Позвать человека", url="https://t.me/andreytelegraf")
    )
    builder.add(InlineKeyboardButton(text="← Назад", callback_data="go:main"))
    builder.adjust(1)

    await callback.message.edit_text(help_text, reply_markup=builder.as_markup())


@router.callback_query(F.data.in_(["mode:seeking", "mode:offering"]))
async def check_posting_limits(callback: CallbackQuery):
    """Check posting limits before starting flow."""
    user = callback.from_user
    mode = callback.data.split(":")[1]

    db_user = db.get_user(user.id)
    if not db_user:
        user_db_id = db.create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
    else:
        user_db_id = db_user["id"]

    active_postings = db.get_user_postings(user_db_id)
    recent_postings = [p for p in active_postings if p.get("status") == "active"]

    if len(recent_postings) >= 3:
        oldest_posting = min(recent_postings, key=lambda p: p["created_at"])
        from datetime import datetime, timedelta

        oldest_date = datetime.fromisoformat(oldest_posting["created_at"])
        earliest_next_post_date = oldest_date + timedelta(days=30)
        date_str = earliest_next_post_date.strftime("%d.%m.%Y")

        limit_message = (
            "⚠️ Лимит публикаций превышен\n\n"
            "У вас уже есть 3 активных объявления за последние 30 дней.\n\n"
            f"Чтобы опубликовать ещё одно объявление, удалите минимум одно старое или подождите до {date_str}\n\n"
            "Управляйте своими объявлениями в разделе 'Мои объявления'."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📋 Мои объявления", callback_data="my_postings")],
                [InlineKeyboardButton(text="← Назад", callback_data="go:main")],
            ]
        )

        await callback.message.edit_text(limit_message, reply_markup=keyboard)
        await callback.answer()
        return

    await callback.answer()


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    """Handle /ban command (admin only)."""
    admin_ids = Config.ADMIN_IDS

    logger.info("[MAIN] Команда /ban получена: %s от пользователя %s", message.text, message.from_user.id)

    if message.from_user.id not in admin_ids:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) < 2:
        await message.answer("📝 Использование: /ban <user_id> <причина>")
        return

    try:
        target_user_id = int(args[0])
        reason = " ".join(args[1:])

        target_user = db.get_user(target_user_id)
        if not target_user:
            await message.answer(f"🚫 Пользователь с ID {target_user_id} не найден в базе данных.")
            return

        is_banned, _ = db.is_user_banned(target_user_id)
        if is_banned:
            await message.answer(f"ℹ️ Пользователь {target_user_id} уже забанен.")
            return

        admin_user = db.get_user(message.from_user.id)
        if not admin_user:
            admin_user_id = db.create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
        else:
            admin_user_id = admin_user["id"]

        success = db.ban_user(target_user_id, admin_user_id, reason)

        if success:
            await message.answer(f"✅ Пользователь {target_user_id} забанен.\n\nПричина: {reason}")
        else:
            await message.answer("🚫 Ошибка при бане пользователя.")

    except ValueError:
        await message.answer("🚫 Неверный формат user_id. Используйте число.")


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    """Handle /unban command (admin only)."""
    admin_ids = Config.ADMIN_IDS

    if message.from_user.id not in admin_ids:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) != 1:
        await message.answer("📝 Использование: /unban <user_id>")
        return

    try:
        target_user_id = int(args[0])

        target_user = db.get_user(target_user_id)
        if not target_user:
            await message.answer(f"🚫 Пользователь с ID {target_user_id} не найден в базе данных.")
            return

        is_banned, _ = db.is_user_banned(target_user_id)
        if not is_banned:
            await message.answer(f"ℹ️ Пользователь {target_user_id} не забанен.")
            return

        admin_user = db.get_user(message.from_user.id)
        if not admin_user:
            admin_user_id = db.create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
        else:
            admin_user_id = admin_user["id"]

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
    admin_ids = Config.ADMIN_IDS

    if message.from_user.id not in admin_ids:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return

    pending_posts = db.get_pending_premium_posts()

    if not pending_posts:
        await message.answer("📋 Нет ожидающих подтверждения премиум-постов.")
        return

    response = f"📋 Ожидающие подтверждения премиум-посты ({len(pending_posts)}):\n\n"

    for i, post in enumerate(pending_posts[:10], 1):
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
    admin_ids = Config.ADMIN_IDS

    if message.from_user.id not in admin_ids:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) < 1:
        await message.answer("📝 Использование: /approve_payment <post_id> [заметки]")
        return

    try:
        post_id = int(args[0])
        admin_notes = " ".join(args[1:]) if len(args) > 1 else None

        post = db.get_premium_post(post_id)
        if not post:
            await message.answer(f"🚫 Премиум-пост с ID {post_id} не найден.")
            return

        if post["payment_status"] != "pending":
            await message.answer(f"🚫 Пост {post_id} уже обработан (статус: {post['payment_status']}).")
            return

        admin_user = db.get_user(message.from_user.id)
        if not admin_user:
            admin_user_id = db.create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
        else:
            admin_user_id = admin_user["id"]

        success = db.approve_premium_post(post_id, admin_user_id, admin_notes)

        if success:
            await message.answer(
                f"✅ Оплата для поста {post_id} подтверждена!\n\n"
                f"**Пользователь:** {post['telegram_id']}\n"
                f"**Тип:** {post['mode']}\n"
                f"**Медиа:** {post['media_type']}\n"
                f"**Стоимость:** €{post['payment_amount']}\n\n"
                "Пост готов к публикации в канале.",
                parse_mode="Markdown",
            )
        else:
            await message.answer("🚫 Ошибка при подтверждении оплаты.")

    except ValueError:
        await message.answer("🚫 Неверный формат post_id. Используйте число.")


@router.message(Command("reject_payment"))
async def cmd_reject_payment(message: Message):
    """Handle /reject_payment command (admin only)."""
    admin_ids = Config.ADMIN_IDS

    if message.from_user.id not in admin_ids:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) < 2:
        await message.answer("📝 Использование: /reject_payment <post_id> <причина>")
        return

    try:
        post_id = int(args[0])
        reason = " ".join(args[1:])

        post = db.get_premium_post(post_id)
        if not post:
            await message.answer(f"🚫 Премиум-пост с ID {post_id} не найден.")
            return

        if post["payment_status"] != "pending":
            await message.answer(f"🚫 Пост {post_id} уже обработан (статус: {post['payment_status']}).")
            return

        admin_user = db.get_user(message.from_user.id)
        if not admin_user:
            admin_user_id = db.create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
        else:
            admin_user_id = admin_user["id"]

        success = db.reject_premium_post(post_id, admin_user_id, reason)

        if success:
            await message.answer(
                f"🚫 Оплата для поста {post_id} отклонена.\n\n"
                f"**Причина:** {reason}\n"
                f"**Пользователь:** {post['telegram_id']}\n"
                f"**Тип:** {post['mode']}",
                parse_mode="Markdown",
            )
        else:
            await message.answer("🚫 Ошибка при отклонении оплаты.")

    except ValueError:
        await message.answer("🚫 Неверный формат post_id. Используйте число.")


async def main():
    """Main function."""
    try:
        cleanup_stale_processes()

        with SingleInstance(LOCK_FILE):
            Config.validate()
            logger.info("Configuration validated successfully")

            bot = Bot(token=Config.BOT_TOKEN)
            dp = Dispatcher(storage=MemoryStorage())

            dp.message.middleware(BanCheckMiddleware())
            dp.callback_query.middleware(BanCheckMiddleware())

            @dp.message.middleware()
            async def log_all_messages(handler, event, data):
                if event.text and event.text.startswith("/ban"):
                    logger.info("[MAIN] Получена команда /ban: %s от пользователя %s", event.text, event.from_user.id)
                return await handler(event, data)

            @dp.error(ExceptionTypeFilter(TelegramBadRequest))
            async def handle_message_not_modified(event: ErrorEvent):
                if "message is not modified" in str(event.exception):
                    return
                raise event.exception

            @dp.update.outer_middleware()
            async def log_unhandled_updates(handler, event: Update, data):
                result = await handler(event, data)
                if result is UNHANDLED:
                    try:
                        logger.warning(
                            "UNHANDLED_UPDATE type=%s payload=%s",
                            event.event_type,
                            event.model_dump_json(exclude_none=True),
                        )
                    except Exception as e:
                        logger.warning("UNHANDLED_UPDATE logging failed: %s", e)
                return result

            dp.include_router(start_router)
            dp.include_router(admin_router)
            dp.include_router(router)
            dp.include_router(premium_posting_router)
            dp.include_router(premium_admin_router)
            dp.include_router(section_catalog_router)
            dp.include_router(restaurants_schema_router)
            dp.include_router(posting_router)
            dp.include_router(my_postings_router)

            logger.info("Work in Portugal Bot started successfully")

            await start_scheduler(bot)
            logger.info("Cleanup scheduler started")

            await dp.start_polling(bot, skip_updates=True)

    except ValueError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        sys.exit(1)
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Fatal error: %s", e)
        sys.exit(1)
