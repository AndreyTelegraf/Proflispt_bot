#!/usr/bin/env python3
"""Скрипт для прямого бана пользователей по их Telegram ID."""

import sys
import sqlite3
from datetime import datetime

def ban_user_by_id(telegram_id: int, reason: str = "Нарушение правил", admin_id: int = 8405113240):
    """Банит пользователя по Telegram ID."""
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Создаем пользователя, если его нет
        cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        user_result = cursor.fetchone()
        if user_result:
            db_user_id = user_result['id']
        else:
            cursor.execute("""
                INSERT INTO users (telegram_id, username, first_name, last_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (telegram_id, None, None, None, datetime.now(), datetime.now()))
            conn.commit()
            db_user_id = cursor.lastrowid
        
        # Получаем или создаем админа
        cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (admin_id,))
        admin_result = cursor.fetchone()
        if admin_result:
            db_admin_id = admin_result['id']
        else:
            cursor.execute("""
                INSERT INTO users (telegram_id, username, first_name, last_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (admin_id, 'admin', 'Admin', None, datetime.now(), datetime.now()))
            conn.commit()
            db_admin_id = cursor.lastrowid
        
        # Деактивируем предыдущие активные баны
        cursor.execute("""
            UPDATE user_bans 
            SET is_active = FALSE 
            WHERE user_id = ? AND is_active = TRUE
        """, (db_user_id,))
        
        # Создаем новый бан
        cursor.execute("""
            INSERT INTO user_bans (user_id, banned_by, reason, ban_type, expires_at, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, TRUE)
        """, (db_user_id, db_admin_id, reason, 'permanent', None, datetime.now()))
        
        conn.commit()
        print(f"✅ Пользователь {telegram_id} успешно забанен.")
        print(f"   Причина: {reason}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при бане пользователя: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python3 ban_users.py <telegram_id1> [telegram_id2] ...")
        print("Пример: python3 ban_users.py 123456789 987654321")
        sys.exit(1)
    
    reason = "Нарушение правил"
    if len(sys.argv) > 2 and not sys.argv[-1].isdigit():
        reason = " ".join(sys.argv[2:])
        user_ids = [int(sys.argv[1])]
    else:
        user_ids = [int(arg) for arg in sys.argv[1:] if arg.isdigit()]
    
    if not user_ids:
        print("❌ Не указаны корректные Telegram ID пользователей.")
        sys.exit(1)
    
    print(f"Баним {len(user_ids)} пользователь(ей)...\n")
    success_count = 0
    
    for user_id in user_ids:
        if ban_user_by_id(user_id, reason):
            success_count += 1
    
    print(f"\n📊 Результат: {success_count}/{len(user_ids)} пользователей забанено.")

