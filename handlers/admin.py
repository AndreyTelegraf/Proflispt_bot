"""Admin handlers for Work in Portugal Bot."""

import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from database import db

logger = logging.getLogger(__name__)

router = Router()

# Список администраторов (Telegram ID)
ADMIN_IDS = [
    336224597,   # AndreyTelegraf
    8405113240,  # Основной админ
    # Добавьте других администраторов здесь
]

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id in ADMIN_IDS

@router.message(Command("ban"))
async def ban_user_command(message: Message, state: FSMContext):
    """Команда для бана пользователя."""
    try:
        logger.info(f"[ADMIN] Команда /ban получена от пользователя {message.from_user.id}: {message.text}")
        logger.info(f"[ADMIN] Проверка прав администратора для {message.from_user.id}")
        
        if not is_admin(message.from_user.id):
            logger.warning(f"[ADMIN] Пользователь {message.from_user.id} не является администратором. ADMIN_IDS: {ADMIN_IDS}")
            await message.answer("🚫 У вас нет прав для выполнения этой команды.")
            return
        
        logger.info(f"[ADMIN] Пользователь {message.from_user.id} является администратором, продолжаем обработку")
        
        # Формат: /ban <user_id или @username> <reason> [duration]
        args = message.text.split()[1:]
        logger.info(f"[ADMIN] Аргументы команды: {args}")
    
        if len(args) < 2:
            await message.answer(
                "📝 Использование: /ban <user_id или @username> <причина> [длительность]\n\n"
                "Примеры:\n"
                "/ban 123456789 Спам\n"
                "/ban @username Спам\n"
                "/ban 123456789 Нарушение правил 7d\n"
                "/ban 123456789 Временный бан 24h"
            )
            return
        
        # Проверяем, является ли первый аргумент username (начинается с @)
        target_identifier = args[0]
        target_user = None
        target_user_id = None
        
        if target_identifier.startswith('@'):
            # Ищем по username
            logger.info(f"[ADMIN] Поиск пользователя по username: {target_identifier}")
            target_user = db.get_user_by_username(target_identifier)
            if not target_user:
                logger.warning(f"[ADMIN] Пользователь {target_identifier} не найден в базе данных")
                await message.answer(
                    f"🚫 Пользователь {target_identifier} не найден в базе данных.\n\n"
                    f"💡 Пользователь должен был хотя бы раз взаимодействовать с ботом, "
                    f"чтобы его можно было забанить по username.\n\n"
                    f"Используйте команду с Telegram ID пользователя: /ban <telegram_id> <причина>"
                )
                return
            logger.info(f"[ADMIN] Пользователь найден: {target_user}")
            target_user_id = target_user['telegram_id']
        else:
            # Ищем по telegram_id
            try:
                target_user_id = int(target_identifier)
            except ValueError:
                await message.answer("🚫 Неверный формат user_id. Используйте число или @username.")
                return
            
            target_user = db.get_user(target_user_id)
            # Если пользователя нет в базе, создаем его для бана
            if not target_user:
                # Создаем пользователя с минимальной информацией
                db.create_user(
                    telegram_id=target_user_id,
                    username=None,
                    first_name=None,
                    last_name=None
                )
                target_user = db.get_user(target_user_id)
                if not target_user:
                    await message.answer(f"🚫 Ошибка при создании записи пользователя {target_user_id}.")
                    return
        
        # Определяем причину и длительность
        try:
            if len(args) > 2:
                # Проверяем, является ли последний аргумент длительностью
                last_arg = args[-1]
                if last_arg.endswith(('h', 'd')):
                    duration = last_arg
                    reason = " ".join(args[1:-1])
                else:
                    duration = None
                    reason = " ".join(args[1:])
            else:
                duration = None
                reason = args[1] if len(args) > 1 else "Нарушение правил"
        except (IndexError, ValueError) as e:
            await message.answer("🚫 Ошибка при обработке аргументов команды.")
            return
        
        # Определяем тип бана и длительность
        if duration:
            ban_type = 'temporary'
            if duration.endswith('h'):
                hours = int(duration[:-1])
                expires_at = datetime.now() + timedelta(hours=hours)
            elif duration.endswith('d'):
                days = int(duration[:-1])
                expires_at = datetime.now() + timedelta(days=days)
            else:
                await message.answer("🚫 Неверный формат длительности. Используйте 'h' для часов или 'd' для дней.")
                return
        else:
            ban_type = 'permanent'
            expires_at = None
        
        # Баним пользователя
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
        
        success = db.ban_user(
            user_id=target_user['id'],
            banned_by=admin_user_id,
            reason=reason,
            ban_type=ban_type,
            expires_at=expires_at
        )
        
        if success:
            duration_text = f" до {expires_at.strftime('%d.%m.%Y %H:%M')}" if expires_at else " навсегда"
            await message.answer(
                f"✅ Пользователь {target_user_id} забанен{duration_text}\n\n"
                f"Причина: {reason}"
            )
        else:
            await message.answer("🚫 Ошибка при бане пользователя.")
    except Exception as e:
        logger.error(f"[ADMIN] Ошибка при выполнении команды /ban: {e}", exc_info=True)
        await message.answer(f"🚫 Произошла ошибка при выполнении команды: {str(e)}")

@router.message(Command("unban"))
async def unban_user_command(message: Message):
    """Команда для разбана пользователя."""
    if not is_admin(message.from_user.id):
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    
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
        is_banned, ban_info = db.is_user_banned(target_user['id'])
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
        
        success = db.unban_user(target_user['id'], admin_user_id)
        
        if success:
            await message.answer(f"✅ Пользователь {target_user_id} разбанен.")
        else:
            await message.answer("🚫 Ошибка при разбане пользователя.")
            
    except ValueError:
        await message.answer("🚫 Неверный формат user_id. Используйте число.")

@router.message(Command("bans"))
async def list_bans_command(message: Message):
    """Команда для просмотра списка банов."""
    if not is_admin(message.from_user.id):
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    
    args = message.text.split()[1:]
    active_only = True
    
    if args and args[0] == "all":
        active_only = False
    
    bans = db.get_all_bans(active_only=active_only)
    
    if not bans:
        status = "активных" if active_only else ""
        await message.answer(f"📋 Нет {status} банов.")
        return
    
    status = "активных" if active_only else "всех"
    response = f"📋 Список {status} банов ({len(bans)}):\n\n"
    
    for i, ban in enumerate(bans[:10], 1):  # Показываем первые 10
        user_info = f"{ban['telegram_id']} ({ban['username'] or 'без username'})"
        admin_info = f"{ban['admin_telegram_id']} ({ban['admin_username'] or 'без username'})"
        
        created_at = ban['created_at']
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        ban_type = "временный" if ban['ban_type'] == 'temporary' else "постоянный"
        
        response += f"{i}. {user_info}\n"
        response += f"   Тип: {ban_type}\n"
        response += f"   Причина: {ban['reason']}\n"
        response += f"   Забанен: {admin_info}\n"
        response += f"   Дата: {created_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        if ban['ban_type'] == 'temporary' and ban['expires_at']:
            expires_at = ban['expires_at']
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            response += f"   Истекает: {expires_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        response += "\n"
    
    if len(bans) > 10:
        response += f"... и еще {len(bans) - 10} банов"
    
    await message.answer(response)

@router.message(Command("userinfo"))
async def user_info_command(message: Message):
    """Команда для получения информации о пользователе."""
    if not is_admin(message.from_user.id):
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    
    args = message.text.split()[1:]
    
    if len(args) != 1:
        await message.answer("📝 Использование: /userinfo <user_id>")
        return
    
    try:
        target_user_id = int(args[0])
        
        # Получаем пользователя
        target_user = db.get_user(target_user_id)
        if not target_user:
            await message.answer(f"🚫 Пользователь с ID {target_user_id} не найден в базе данных.")
            return
        
        # Получаем объявления пользователя
        user_postings = db.get_user_postings(target_user['id'])
        
        # Получаем историю банов
        user_bans = db.get_user_bans(target_user['id'])
        
        # Проверяем текущий статус бана
        is_banned, current_ban = db.is_user_banned(target_user['id'])
        
        response = f"👤 Информация о пользователе {target_user_id}:\n\n"
        response += f"Имя: {target_user['first_name']} {target_user['last_name'] or ''}\n"
        response += f"Username: @{target_user['username'] or 'нет'}\n"
        response += f"Дата регистрации: {target_user['created_at']}\n"
        response += f"Активных объявлений: {len(user_postings)}\n"
        response += f"История банов: {len(user_bans)}\n"
        response += f"Статус: {'🚫 Забанен' if is_banned else '✅ Активен'}\n"
        
        if is_banned and current_ban:
            ban_type = "временный" if current_ban['ban_type'] == 'temporary' else "постоянный"
            response += f"Тип бана: {ban_type}\n"
            response += f"Причина: {current_ban['reason']}\n"
            if current_ban['ban_type'] == 'temporary' and current_ban['expires_at']:
                expires_at = current_ban['expires_at']
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                response += f"Истекает: {expires_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        await message.answer(response)
        
    except ValueError:
        await message.answer("🚫 Неверный формат user_id. Используйте число.")

@router.message(Command("cleanup_bans"))
async def cleanup_bans_command(message: Message):
    """Команда для очистки истекших банов."""
    if not is_admin(message.from_user.id):
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    
    cleaned_count = db.cleanup_expired_bans()
    await message.answer(f"🧹 Очищено {cleaned_count} истекших банов.")

@router.message(Command("getid"))
async def get_id_command(message: Message):
    """Команда для получения ID пользователя из пересланного сообщения."""
    if not is_admin(message.from_user.id):
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    
    # Проверяем, есть ли пересланное сообщение
    if message.forward_from:
        user = message.forward_from
        user_info = (
            f"👤 Информация о пользователе:\n\n"
            f"Telegram ID: `{user.id}`\n"
            f"Имя: {user.first_name} {user.last_name or ''}\n"
            f"Username: @{user.username or 'нет'}\n\n"
            f"Для бана используйте:\n"
            f"`/ban {user.id} Причина`"
        )
        await message.answer(user_info, parse_mode="Markdown")
    elif message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        user_info = (
            f"👤 Информация о пользователе:\n\n"
            f"Telegram ID: `{user.id}`\n"
            f"Имя: {user.first_name} {user.last_name or ''}\n"
            f"Username: @{user.username or 'нет'}\n\n"
            f"Для бана используйте:\n"
            f"`/ban {user.id} Причина`"
        )
        await message.answer(user_info, parse_mode="Markdown")
    else:
        await message.answer(
            "📝 Использование:\n\n"
            "1. Перешлите сообщение от пользователя и ответьте `/getid`\n"
            "2. Или ответьте `/getid` на сообщение пользователя\n\n"
            "Команда покажет Telegram ID пользователя для дальнейшего бана."
        )
