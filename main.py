"""Main entry point."""

import asyncio
import logging
import sys
import os
import signal
import fcntl
from calendar import monthrange
from aiogram import Bot, Dispatcher, Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import ExceptionTypeFilter, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ErrorEvent, Update, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.dispatcher.event.bases import UNHANDLED

from config import Config
from services.directory_links import directory_message_url
from database import db
from handlers.start import router as start_router
from handlers.posting import router as posting_router
from handlers.my_postings import router as my_postings_router
from handlers.fallback import router as fallback_router
from handlers.admin import router as admin_router
from handlers.premium_admin import router as premium_admin_router
from handlers.housing_schema_flow import router as housing_schema_flow_router
from handlers.generic_schema_flow import router as generic_schema_flow_router
from handlers.section_catalog import router as section_catalog_router
from handlers.reviews_schema_flow import router as reviews_schema_flow_router
from services.scheduler import start_scheduler
from services.auto_repost import start_auto_repost_scheduler
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



@router.chat_member()
async def sync_catalog_ban_to_bot(event: ChatMemberUpdated):
    """Mirror bans from the catalog supergroup into the bot ban table."""
    if event.chat.id != Config.CHANNEL_ID:
        return

    member = event.new_chat_member
    user = member.user
    status = getattr(member, "status", None)

    if status != "kicked":
        return

    if getattr(user, "is_bot", False):
        return

    admin_id = event.from_user.id if event.from_user else Config.ADMIN_IDS[0]

    db.create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    db.ban_user(
        user_id=user.id,
        banned_by=admin_id,
        reason="Автоматический бан: пользователь забанен в Справочнике",
        ban_type="permanent",
        expires_at=None,
    )

    logger.warning(
        "Catalog ban mirrored to bot ban table: user_id=%s username=%s by=%s chat_id=%s",
        user.id,
        user.username,
        admin_id,
        event.chat.id,
    )

def _job_mode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Ищу работу", callback_data="mode:seeking"))
    builder.add(InlineKeyboardButton(text="Предлагаю работу", callback_data="mode:offering"))
    builder.add(InlineKeyboardButton(text="← Назад", callback_data="catalog:group:housing_work"))
    builder.adjust(1)
    return builder.as_markup()


def _job_cities_keyboard() -> InlineKeyboardMarkup:
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
        ("Другие города", "city:custom"),
    ]
    for text, callback_data in cities:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
    builder.add(InlineKeyboardButton(text="← Назад", callback_data="back_to_mode"))
    builder.adjust(3)
    return builder.as_markup()


def _job_cities_prompt(mode: str) -> str:
    if mode == "seeking":
        return "Отлично, давайте найдём вам работу.\nГде вы её ищите?"
    return "Отлично, давайте закроем вашу вакансию.\nГде вы ищите сотрудников?"


def _job_description_prompt(mode: str, cities_text: str) -> str:
    if mode == "seeking":
        return (
            f"Города: {cities_text}\n\n"
            "Теперь отправьте описание работы, которую вы ищите, начинающееся например с фразы:\n\n"
            "- Ищу подработку в сфере услуг\n"
            "- Ищу парт-тайм официантом\n"
            "- Ищу работу на стройке...\n\n"
            "...дальше опишите свои навыки и опыт.\n\n"
            "Контактов и ссылок в описании быть не должно, они вводятся на следующих шагах."
        )
    return (
        f"Города: {cities_text}\n\n"
        "Теперь отправьте описание вашей вакансии.\n"
        "Если вакансий несколько, сформируйте описание так, чтобы это было понятно.\n"
        "Начните с ключевых слов, например:\n\n"
        "- Предлагаю работу водителю с личным авто\n"
        "- Требуется официант в кафе-ресторан\n"
        "- Нужны разнорабочие на стройку\n"
        "- Ищем уборщицу на парт-тайм...\n\n"
        "Контактов и ссылок в описании быть не должно, они вводятся в отдельные поля. "
        "Публикация одной и той же вакансии допускается не чаще раза в месяц. "
        "При наличии нескольких вакансий рекомендуется объединить их в одно объявление."
    )


@router.callback_query(F.data.in_(["mode:seeking", "mode:offering"]))
async def check_posting_limits(callback: CallbackQuery, state: FSMContext):
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
            "Лимит публикаций превышен\n\n"
            "У вас уже есть 3 активных объявления за последние 30 дней.\n\n"
            f"Чтобы опубликовать ещё одно объявление, удалите минимум одно старое или подождите до {date_str}\n\n"
            "Управляйте своими объявлениями в разделе 'Мои объявления'."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Мои объявления", callback_data="my_postings")],
                [InlineKeyboardButton(text="← Назад", callback_data="catalog:group:housing_work")],
            ]
        )

        await callback.message.edit_text(limit_message, reply_markup=keyboard)
        await callback.answer()
        return

    await state.clear()
    await state.update_data(mode=mode)
    await callback.message.edit_text(_job_cities_prompt(mode), reply_markup=_job_cities_keyboard())
    await callback.answer()


@router.callback_query(F.data == "back_to_mode")
async def back_to_job_mode(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Выберите раздел:",
        reply_markup=_job_mode_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("city:"))
async def handle_job_city(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mode = data.get("mode")
    if mode not in {"seeking", "offering"}:
        await callback.answer("Сессия публикации не найдена.", show_alert=True)
        return

    city = callback.data.split(":", 1)[1]

    if city == "custom":
        await callback.message.edit_text(
            "Введите город или несколько городов через запятую:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="back_to_cities")]]
            ),
        )
        await state.set_state("waiting_for_custom_city")
        await callback.answer()
        return

    await state.update_data(cities=[city])
    cities_text = Config.CITIES.get(city, city)
    await callback.message.edit_text(
        _job_description_prompt(mode, cities_text),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="back_to_cities")]]
        ),
    )
    await state.set_state("waiting_for_description")
    await callback.answer()


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    """Handle /ban command by @username, +351 phone, or numeric Telegram id."""
    admin_ids = Config.ADMIN_IDS
    if message.from_user.id not in admin_ids:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) < 2:
        await message.answer("Использование: /ban <@username|+351xxxxxxxxx|user_id> <причина>")
        return

    target = args[0].strip()
    reason = " ".join(args[1:]).strip()

    if target.startswith("@"):
        ok = db.ban_identity("username", target, message.from_user.id, reason)
        await message.answer(f"Username {target} забанен.\n\nПричина: {reason}" if ok else "Ошибка при бане username.")
        return

    if target.startswith("+"):
        ok = db.ban_identity("phone", target, message.from_user.id, reason)
        await message.answer(f"Телефон {target} забанен.\n\nПричина: {reason}" if ok else "Ошибка при бане телефона.")
        return

    try:
        target_user_id = int(target)
    except ValueError:
        await message.answer("Неверный target. Используйте @username, +351xxxxxxxxx или user_id.")
        return

    target_user = db.get_user(target_user_id)
    if not target_user:
        await message.answer(f"Пользователь с ID {target_user_id} не найден в базе данных.")
        return

    is_banned, _ = db.is_user_banned(target_user_id)
    if is_banned:
        await message.answer(f"Пользователь {target_user_id} уже забанен.")
        return

    admin_user = db.get_user(message.from_user.id)
    admin_user_id = admin_user["id"] if admin_user else db.create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    success = db.ban_user(target_user_id, admin_user_id, reason)
    await message.answer(f"Пользователь {target_user_id} забанен.\n\nПричина: {reason}" if success else "Ошибка при бане пользователя.")


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    """Handle /unban command by @username, +351 phone, or numeric Telegram id."""
    admin_ids = Config.ADMIN_IDS
    if message.from_user.id not in admin_ids:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) != 1:
        await message.answer("Использование: /unban <@username|+351xxxxxxxxx|user_id>")
        return

    target = args[0].strip()

    if target.startswith("@"):
        ok = db.unban_identity("username", target)
        await message.answer(f"Username {target} разбанен." if ok else f"Активный бан для {target} не найден.")
        return

    if target.startswith("+"):
        ok = db.unban_identity("phone", target)
        await message.answer(f"Телефон {target} разбанен." if ok else f"Активный бан для {target} не найден.")
        return

    try:
        target_user_id = int(target)
    except ValueError:
        await message.answer("Неверный target. Используйте @username, +351xxxxxxxxx или user_id.")
        return

    target_user = db.get_user(target_user_id)
    if not target_user:
        await message.answer(f"Пользователь с ID {target_user_id} не найден в базе данных.")
        return

    is_banned, _ = db.is_user_banned(target_user_id)
    if not is_banned:
        await message.answer(f"Пользователь {target_user_id} не забанен.")
        return

    admin_user = db.get_user(message.from_user.id)
    admin_user_id = admin_user["id"] if admin_user else db.create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    success = db.unban_user(target_user_id, admin_user_id)
    await message.answer(f"Пользователь {target_user_id} разбанен." if success else "Ошибка при разбане пользователя.")


def _billing_is_allowed(message: Message) -> bool:
    allowed_usernames = {"andreytelegraf", "kak_odin", "kak_budto"}
    username = (message.from_user.username or "").lower()
    return username in allowed_usernames


def _parse_billing_period(message: Message):
    args = (message.text or "").split()[1:]

    if not args:
        return {
            "since": "2026-04-01 00:00:00",
            "until": None,
            "label": "с 01.04.2026 включительно",
        }

    raw = args[0].strip()
    parts = raw.split(".")
    if len(parts) != 2:
        return None

    month_raw, year_raw = parts
    if not (month_raw.isdigit() and year_raw.isdigit()):
        return None

    month = int(month_raw)
    year = int(year_raw)

    if month < 1 or month > 12 or year < 2000 or year > 2100:
        return None

    next_month = 1 if month == 12 else month + 1
    next_year = year + 1 if month == 12 else year
    last_day = monthrange(year, month)[1]

    return {
        "since": f"{year:04d}-{month:02d}-01 00:00:00",
        "until": f"{next_year:04d}-{next_month:02d}-01 00:00:00",
        "label": f"с 01.{month:02d}.{year:04d} по {last_day:02d}.{month:02d}.{year:04d} включительно",
    }


def _fetch_billing_report(period):
    where_parts = [
        "pp.payment_status = 'approved'",
        "CAST(COALESCE(pp.payment_amount, 0) AS REAL) > 0",
        "datetime(pp.created_at) >= datetime(?)",
    ]
    params = [period["since"]]

    if period["until"]:
        where_parts.append("datetime(pp.created_at) < datetime(?)")
        params.append(period["until"])

    base_where = "\n        AND ".join(where_parts)

    fields = """
        pp.id,
        pp.user_id,
        pp.mode,
        pp.action_type,
        pp.payment_amount,
        pp.status,
        pp.created_at,
        pp.updated_at,
        pp.message_id,
        pp.topic_id,
        pp.telegram_username,
        pp.phone_main,
        pp.name,
        u.telegram_id,
        u.username AS user_username
    """

    with db.get_connection() as conn:
        cursor = conn.cursor()

        def fetch_rows(extra_where: str):
            cursor.execute(f"""
                SELECT {fields}
                FROM premium_posts pp
                LEFT JOIN users u ON pp.user_id = u.id
                WHERE {base_where}
                  AND {extra_where}
                ORDER BY datetime(pp.created_at) ASC, pp.id ASC
            """, params)
            return [dict(row) for row in cursor.fetchall()]

        published_posts = fetch_rows("pp.status = 'published' AND pp.action_type = 'post'")
        removed_posts = fetch_rows("pp.status IN ('deleted', 'superseded') AND pp.action_type = 'post'")
        published_reposts = fetch_rows("pp.status = 'published' AND pp.action_type = 'repost'")
        removed_reposts = fetch_rows("pp.status IN ('deleted', 'superseded') AND pp.action_type = 'repost'")
        published_pins = fetch_rows("pp.status = 'published' AND pp.action_type = 'pin'")

        accounting_posts = fetch_rows("""
            pp.action_type = 'post'
            AND pp.mode != 'reviews'
            AND pp.message_id IS NOT NULL
            AND pp.status IN ('published', 'deleted', 'superseded')
        """)
        accounting_reposts = fetch_rows("""
            pp.action_type = 'repost'
            AND pp.mode != 'reviews'
            AND pp.message_id IS NOT NULL
            AND pp.status IN ('published', 'deleted', 'superseded')
        """)
        accounting_pins = fetch_rows("""
            pp.action_type = 'pin'
            AND pp.mode != 'reviews'
            AND pp.message_id IS NOT NULL
            AND pp.status IN ('published', 'deleted', 'superseded')
        """)

        cursor.execute(f"""
            SELECT
                pp.status,
                pp.action_type,
                pp.mode,
                COUNT(*) AS cnt,
                SUM(CAST(COALESCE(pp.payment_amount, 0) AS REAL)) AS total
            FROM premium_posts pp
            WHERE {base_where}
            GROUP BY pp.status, pp.action_type, pp.mode
            ORDER BY pp.status, pp.action_type, pp.mode
        """, params)
        audit_groups = [dict(row) for row in cursor.fetchall()]

    return {
        "published_posts": published_posts,
        "removed_posts": removed_posts,
        "published_reposts": published_reposts,
        "removed_reposts": removed_reposts,
        "published_pins": published_pins,
        "accounting_posts": accounting_posts,
        "accounting_reposts": accounting_reposts,
        "accounting_pins": accounting_pins,
        "audit_groups": audit_groups,
    }


def _rows_sum(rows):
    return sum(float(row.get("payment_amount") or 0) for row in rows)


def _exclude_known_non_billable_rows(rows):
    """Exclude known historical technical/test duplicates from /pays accounting.

    The DB currently has no canonical accounting flag. These rows were approved
    and briefly published, but represent test/technical replacement attempts,
    not separate paid services.
    """
    non_billable_ids = {
        7,    # admin test job_offer
        158,  # admin test repost
        256,  # technical wrong-section duplicate before final Barbearia post
        259,  # technical duplicate before final Barbearia post
        356,  # technical duplicate before final Karga24.7 post
        359,  # technical duplicate before final Karga24.7 post
        361,  # technical duplicate before final Karga24.7 post
        440,  # admin test passenger_transport
        441,  # admin test catalog section
        653,  # technical duplicate before final Bee Gym post
    }
    return [row for row in rows if int(row.get("id") or 0) not in non_billable_ids]


def _append_billing_rows(lines, title, rows):
    if not rows:
        return

    lines.append("")
    lines.append(title)
    for row in rows:
        amount = float(row.get("payment_amount") or 0)
        created = str(row.get("created_at") or "")[:10]
        mode = row.get("mode") or "-"
        post_status = row.get("status") or "-"
        tg = row.get("telegram_username") or "-"
        phone = row.get("phone_main") or "-"
        name = row.get("name") or "-"
        post_id = row.get("id")
        msg = row.get("message_id")
        topic = row.get("topic_id")

        if msg:
            link = directory_message_url(msg, topic)
        else:
            link = "-"

        lines.append(
            f"- {created}; #{post_id}; {amount:.2f} €; {mode}; "
            f"status={post_status}; {tg}; {phone}; {name}; {link}"
        )


async def _send_long_text(message: Message, lines):
    text = "\n".join(lines)

    chunks = []
    while len(text) > 3900:
        cut = text.rfind("\n", 0, 3900)
        if cut <= 0:
            cut = 3900
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    chunks.append(text)

    for chunk in chunks:
        await message.answer(chunk, disable_web_page_preview=True)


@router.message(Command("pays"))
async def cmd_pays(message: Message):
    if not _billing_is_allowed(message):
        await message.answer("Нет доступа.")
        return

    period = _parse_billing_period(message)
    if not period:
        await message.answer("Использование: /pays или /pays MM.YYYY")
        return

    report = _fetch_billing_report(period)

    accounting_posts = _exclude_known_non_billable_rows(report["accounting_posts"])
    accounting_reposts = _exclude_known_non_billable_rows(report["accounting_reposts"])
    accounting_pins = _exclude_known_non_billable_rows(report["accounting_pins"])

    baraholka_modes = {"owner_real_estate", "housing_wanted"}
    directory_reposts = [
        row for row in accounting_reposts
        if (row.get("mode") or "") not in baraholka_modes
    ]
    baraholka_reposts = [
        row for row in accounting_reposts
        if (row.get("mode") or "") in baraholka_modes
    ]

    accounting_posts_total = _rows_sum(accounting_posts)
    directory_reposts_total = _rows_sum(directory_reposts)
    baraholka_reposts_total = _rows_sum(baraholka_reposts)
    accounting_pins_total = _rows_sum(accounting_pins)

    directory_count = len(accounting_posts) + len(directory_reposts) + len(accounting_pins)
    directory_total = accounting_posts_total + directory_reposts_total + accounting_pins_total

    lines = [
        "Платные услуги",
        f"Период: {period['label']}",
        "",
        "Посты с медиа за 20 €:",
        f"- оплаченные: {len(accounting_posts)}",
        f"- сумма: {accounting_posts_total:.2f} €",
        "",
        "Апы за 10 €:",
        f"- оплаченные: {len(directory_reposts)}",
        f"- сумма: {directory_reposts_total:.2f} €",
        "",
        "Закрепы:",
        f"- оплаченные: {len(accounting_pins)}",
        f"- сумма: {accounting_pins_total:.2f} €",
        "",
        "Итого по справочнику:",
        f"- всего оплат: {directory_count}",
        f"- сумма: {directory_total:.2f} €",
        "",
        "Перепосты в Барахолку:",
        f"- оплаченные: {len(baraholka_reposts)}",
        f"- сумма: {baraholka_reposts_total:.2f} €",
    ]

    await _send_long_text(message, lines)


@router.message(Command("billing"))
async def cmd_billing(message: Message):
    if not _billing_is_allowed(message):
        await message.answer("Нет доступа.")
        return

    period = _parse_billing_period(message)
    if not period:
        await message.answer("Использование: /billing или /billing MM.YYYY")
        return

    report = _fetch_billing_report(period)

    lines = [
        "Биллинг: детализация платных услуг",
        f"Период: {period['label']}",
    ]

    if report["audit_groups"]:
        lines.append("")
        lines.append("Аудит по status / action_type / mode:")
        for group in report["audit_groups"]:
            status = group.get("status") or "-"
            action_type = group.get("action_type") or "-"
            mode = group.get("mode") or "-"
            cnt = int(group.get("cnt") or 0)
            subtotal = float(group.get("total") or 0)
            lines.append(f"- {status} / {action_type} / {mode}: {cnt} шт. — {subtotal:.2f} €")

    baraholka_modes = {"owner_real_estate", "housing_wanted"}
    published_directory_reposts = [
        row for row in report["published_reposts"]
        if (row.get("mode") or "") not in baraholka_modes
    ]
    published_baraholka_reposts = [
        row for row in report["published_reposts"]
        if (row.get("mode") or "") in baraholka_modes
    ]
    removed_directory_reposts = [
        row for row in report["removed_reposts"]
        if (row.get("mode") or "") not in baraholka_modes
    ]
    removed_baraholka_reposts = [
        row for row in report["removed_reposts"]
        if (row.get("mode") or "") in baraholka_modes
    ]

    _append_billing_rows(lines, "Детализация опубликованных постов:", report["published_posts"])
    _append_billing_rows(lines, "Детализация удалённых / заменённых постов:", report["removed_posts"])
    _append_billing_rows(lines, "Детализация закрепов:", report["published_pins"])
    _append_billing_rows(lines, "Детализация опубликованных апов в справочнике:", published_directory_reposts)
    _append_billing_rows(lines, "Детализация удалённых / заменённых апов в справочнике:", removed_directory_reposts)
    _append_billing_rows(lines, "Детализация опубликованных перепостов в Барахолку:", published_baraholka_reposts)
    _append_billing_rows(lines, "Детализация удалённых / заменённых перепостов в Барахолку:", removed_baraholka_reposts)

    await _send_long_text(message, lines)



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

            @dp.message.outer_middleware()
            async def ignore_non_private_messages(handler, event: Message, data):
                if event.chat.type != "private":
                    logger.info(
                        "Ignoring non-private message: chat_id=%s chat_type=%s from_user=%s text=%r",
                        event.chat.id,
                        event.chat.type,
                        event.from_user.id if event.from_user else None,
                        event.text,
                    )
                    return
                return await handler(event, data)

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
            dp.include_router(premium_admin_router)
            dp.include_router(reviews_schema_flow_router)
            dp.include_router(section_catalog_router)
            dp.include_router(housing_schema_flow_router)
            dp.include_router(generic_schema_flow_router)
            dp.include_router(posting_router)
            dp.include_router(my_postings_router)
            dp.include_router(fallback_router)

            logger.info("Bot started successfully")

            await start_scheduler(bot)
            logger.info("Cleanup scheduler started")

            await start_auto_repost_scheduler(bot, db)
            logger.info("Auto repost scheduler started")

            await dp.start_polling(bot, skip_updates=True, allowed_updates=["message", "callback_query", "chat_member"])

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
