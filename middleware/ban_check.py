"""Ban check middleware for Work in Portugal Bot."""

import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database import db

logger = logging.getLogger(__name__)

# Список администраторов (Telegram ID)
ADMIN_IDS = [
    336224597,   # AndreyTelegraf
    8405113240,  # Основной админ
    # Добавьте других администраторов здесь
]

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id in ADMIN_IDS

class BanCheckMiddleware(BaseMiddleware):
    """Middleware для проверки бана пользователей."""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Проверяет, забанен ли пользователь."""
        
        # Получаем user_id из события
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)
        
        # Администраторы не проверяются на бан
        if is_admin(user_id):
            return await handler(event, data)
        
        # Проверяем, забанен ли пользователь
        is_banned, ban_info = db.is_user_banned(user_id)
        
        if is_banned and ban_info:
            ban_type = "временный" if ban_info['ban_type'] == 'temporary' else "постоянный"
            
            if ban_type == 'temporary' and ban_info['expires_at']:
                expires_at = ban_info['expires_at']
                if isinstance(expires_at, str):
                    expires_at = expires_at.replace('Z', '+00:00')
                ban_message = (
                    f"🚫 Вы забанены за нарушение правил публикации в Справочнике.\n\n"
                    f"Тип блокировки: {ban_type}\n"
                    f"Истекает: {expires_at}\n\n"
                    f"Для разбана поговорите с [Администратором](https://t.me/andreytelegraf)."
                )
            else:
                ban_message = (
                    f"🚫 Вы забанены за нарушение правил публикации в Справочнике.\n\n"
                    f"Для разбана поговорите с [Администратором](https://t.me/andreytelegraf)."
                )
            
            # Отправляем сообщение о бане
            if isinstance(event, Message):
                await event.answer(ban_message, parse_mode="Markdown")
            elif isinstance(event, CallbackQuery):
                await event.answer(ban_message, show_alert=True)
            
            logger.warning(f"Забаненный пользователь {user_id} попытался использовать бота")
            return
        
        # Пользователь не забанен, продолжаем обработку
        return await handler(event, data)
