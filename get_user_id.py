#!/usr/bin/env python3
"""Скрипт для получения ID пользователей Telegram по username."""

import sys
import sqlite3

def get_user_id_by_username(username: str):
    """
    Пытается получить ID пользователя по username.
    Примечание: Bot API не позволяет получить ID пользователя напрямую по username,
    если пользователь не взаимодействовал с ботом. Этот скрипт проверяет базу данных.
    """
    # Убираем @ если есть
    username = username.lstrip('@')
    
    print(f"Поиск пользователя @{username}...")
    
    # Проверяем базу данных
    import sqlite3
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT telegram_id, username, first_name, last_name FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    
    if user:
        print(f"\n✅ Пользователь найден в базе данных:")
        print(f"   Telegram ID: {user['telegram_id']}")
        print(f"   Username: @{user['username']}")
        print(f"   Имя: {user['first_name']} {user['last_name'] or ''}")
        conn.close()
        return user['telegram_id']
    else:
        print(f"\n❌ Пользователь @{username} не найден в базе данных.")
        print(f"\n💡 Для получения ID пользователя:")
        print(f"   1. Пользователь должен начать диалог с ботом")
        print(f"   2. Или вы можете использовать ID напрямую, если знаете его")
        print(f"\n📝 Для бана используйте команду:")
        print(f"   /ban <telegram_id> Причина")
        conn.close()
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python3 get_user_id.py <username>")
        print("Пример: python3 get_user_id.py Admamc")
        sys.exit(1)
    
    username = sys.argv[1]
    user_id = get_user_id_by_username(username)
    
    if user_id:
        print(f"\n🔑 Telegram ID для бана: {user_id}")
        sys.exit(0)
    else:
        sys.exit(1)

