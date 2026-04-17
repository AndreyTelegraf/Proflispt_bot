#!/usr/bin/env python3
"""Скрипт для разбана пользователей по их Telegram ID."""

import sys
import sqlite3
from datetime import datetime

def unban_user_by_id(telegram_id: int):
    """Разбанивает пользователя по Telegram ID."""
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Получаем ID пользователя из базы
        cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        user_result = cursor.fetchone()
        
        if not user_result:
            print(f"❌ Пользователь с Telegram ID {telegram_id} не найден в базе данных.")
            return False
        
        db_user_id = user_result['id']
        
        # Проверяем, забанен ли пользователь
        cursor.execute("SELECT COUNT(*) as count FROM user_bans WHERE user_id = ? AND is_active = TRUE", (db_user_id,))
        ban_count = cursor.fetchone()['count']
        
        if ban_count == 0:
            print(f"ℹ️ Пользователь {telegram_id} не забанен.")
            return True
        
        # Деактивируем все активные баны
        cursor.execute("""
            UPDATE user_bans 
            SET is_active = FALSE 
            WHERE user_id = ? AND is_active = TRUE
        """, (db_user_id,))
        
        conn.commit()
        print(f"✅ Пользователь {telegram_id} успешно разбанен.")
        print(f"   Деактивировано банов: {ban_count}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при разбане пользователя: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python3 unban_user.py <telegram_id>")
        print("Пример: python3 unban_user.py 336224597")
        sys.exit(1)
    
    try:
        telegram_id = int(sys.argv[1])
        if unban_user_by_id(telegram_id):
            sys.exit(0)
        else:
            sys.exit(1)
    except ValueError:
        print("❌ Неверный формат Telegram ID. Используйте число.")
        sys.exit(1)

