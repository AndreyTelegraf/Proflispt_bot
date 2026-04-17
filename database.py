"""Database module for Work in Portugal Bot."""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from config import Config

logger = logging.getLogger(__name__)


class Database:
    """Database manager for the bot."""

    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_database(self):
        """Initialize database tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Job postings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_postings (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    cities TEXT NOT NULL,
                    description TEXT NOT NULL,
                    social_media TEXT,
                    telegram_username TEXT NOT NULL,
                    phone_main TEXT NOT NULL,
                    phone_whatsapp TEXT,
                    name TEXT NOT NULL,
                    message_id INTEGER,
                    chat_id INTEGER,
                    topic_id INTEGER,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Drafts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    mode TEXT,
                    cities TEXT,
                    description TEXT,
                    social_media TEXT,
                    telegram_username TEXT,
                    phone_main TEXT,
                    phone_whatsapp TEXT,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # User bans table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_bans (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    banned_by INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    ban_type TEXT NOT NULL CHECK (ban_type IN ('temporary', 'permanent')),
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (banned_by) REFERENCES users (id)
                )
            """)

            # Premium posts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS premium_posts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    cities TEXT NOT NULL,
                    description TEXT NOT NULL,
                    social_media TEXT,
                    telegram_username TEXT NOT NULL,
                    phone_main TEXT NOT NULL,
                    phone_whatsapp TEXT,
                    name TEXT NOT NULL,
                    media_file_id TEXT,
                    media_type TEXT CHECK (media_type IN ('photo', 'video')),
                    media_list TEXT,  -- JSON array of media objects
                    payment_status TEXT DEFAULT 'pending' CHECK (payment_status IN ('pending', 'approved', 'rejected')),
                    payment_amount DECIMAL(10,2) DEFAULT 50.00,
                    admin_notes TEXT,
                    message_id INTEGER,
                    chat_id INTEGER,
                    topic_id INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Add media_list column if it doesn't exist (migration)
            try:
                cursor.execute("ALTER TABLE premium_posts ADD COLUMN media_list TEXT")
                logger.info("Added media_list column to premium_posts table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    logger.info("media_list column already exists")
                else:
                    logger.warning(f"Could not add media_list column: {e}")

            # Payments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY,
                    premium_post_id INTEGER NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    payment_method TEXT,
                    payment_proof TEXT,
                    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
                    approved_by INTEGER,
                    approved_at TIMESTAMP,
                    admin_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (premium_post_id) REFERENCES premium_posts (id),
                    FOREIGN KEY (approved_by) REFERENCES users (id)
                )
            """)

            conn.commit()
            logger.info("Database initialized successfully")

    def create_user(self, telegram_id: int, username: Optional[str] = None, 
                   first_name: Optional[str] = None, last_name: Optional[str] = None) -> int:
        """Create or update user. Uses ON CONFLICT to preserve user id when updating."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (telegram_id, username, first_name, last_name, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    updated_at = excluded.updated_at
            """, (telegram_id, username, first_name, last_name, datetime.now()))
            
            conn.commit()
            
            # Get user ID
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
            result = cursor.fetchone()
            return result['id'] if result else None

    def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user by telegram ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            result = cursor.fetchone()
            return dict(result) if result else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by internal database ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            return dict(result) if result else None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Убираем @ если есть
            username_clean = username.lstrip('@')
            cursor.execute("SELECT * FROM users WHERE username = ?", (username_clean,))
            result = cursor.fetchone()
            return dict(result) if result else None

    def create_job_posting(self, user_id: int, mode: str, cities: List[str], 
                          description: str, social_media: Optional[str], 
                          telegram_username: str, phone_main: str, 
                          phone_whatsapp: Optional[str], name: str) -> int:
        """Create job posting with links (websites, social media, portfolio, etc.)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO job_postings 
                (user_id, mode, cities, description, social_media, telegram_username, 
                 phone_main, phone_whatsapp, name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, mode, json.dumps(cities), description, social_media,
                telegram_username, phone_main, phone_whatsapp, name,
                datetime.now(), datetime.now()
            ))
            
            conn.commit()
            return cursor.lastrowid

    def get_user_postings(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all postings for user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM job_postings 
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at DESC
            """, (user_id,))
            
            results = cursor.fetchall()
            return [dict(row) for row in results]

    def get_posting_by_id(self, posting_id: int) -> Optional[Dict[str, Any]]:
        """Get posting by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_postings WHERE id = ?", (posting_id,))
            result = cursor.fetchone()
            return dict(result) if result else None

    def update_posting(self, posting_id: int, **kwargs) -> bool:
        """Update posting."""
        if not kwargs:
            return False
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build update query
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            set_clause += ", updated_at = ?"
            
            values = list(kwargs.values()) + [datetime.now()]
            
            cursor.execute(f"UPDATE job_postings SET {set_clause} WHERE id = ?", 
                         values + [posting_id])
            
            conn.commit()
            return cursor.rowcount > 0

    def delete_posting(self, posting_id: int) -> bool:
        """Delete posting (soft delete)."""
        return self.update_posting(posting_id, status='deleted')

    def get_user_active_postings(self, user_id: int) -> list[dict]:
        """Get all active postings for user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, mode, cities, description, name, created_at, message_id, chat_id, topic_id
                FROM job_postings 
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at DESC
            """, (user_id,))
            
            results = cursor.fetchall()
            return [dict(row) for row in results]

    def get_all_active_postings_with_messages(self) -> list[dict]:
        """Get all active postings that have message_id and chat_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, mode, cities, description, name, created_at, message_id, chat_id, topic_id
                FROM job_postings 
                WHERE status = 'active' AND message_id IS NOT NULL AND chat_id IS NOT NULL
                ORDER BY created_at DESC
            """)
            
            results = cursor.fetchall()
            return [dict(row) for row in results]

    def get_posting_statistics(self, user_id: int) -> dict:
        """
        Получает статистику публикаций пользователя.
        
        Returns:
            dict: статистика с информацией о лимитах и датах публикаций
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем все активные объявления за последние 30 дней
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            cursor.execute("""
                SELECT id, mode, cities, name, created_at
                FROM job_postings 
                WHERE user_id = ? AND status = 'active' 
                AND created_at > ?
                ORDER BY created_at ASC
            """, (user_id, thirty_days_ago))
            
            recent_postings = cursor.fetchall()
            
            # Получаем все активные объявления (для отображения)
            cursor.execute("""
                SELECT id, mode, cities, name, created_at
                FROM job_postings 
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at DESC
            """, (user_id,))
            
            all_active_postings = cursor.fetchall()
            
            # Вычисляем статистику
            current_count = len(recent_postings)
            can_post = current_count < 3
            
            earliest_next_post_date = None
            if current_count == 3:
                oldest_posting_date_str = recent_postings[0]['created_at']
                if isinstance(oldest_posting_date_str, str):
                    oldest_posting_date = datetime.fromisoformat(oldest_posting_date_str.replace('Z', '+00:00'))
                else:
                    oldest_posting_date = oldest_posting_date_str
                earliest_next_post_date = oldest_posting_date + timedelta(days=30)
            
            return {
                'current_count': current_count,
                'max_count': 3,
                'can_post': can_post,
                'earliest_next_post_date': earliest_next_post_date,
                'recent_postings': [dict(p) for p in recent_postings],
                'all_active_postings': [dict(p) for p in all_active_postings]
            }

    def check_posting_cooldown(self, user_id: int, mode: str) -> bool:
        """Check if user can post (cooldown period)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check for recent postings in the same mode
            cooldown_date = datetime.now() - timedelta(days=Config.POSTING_COOLDOWN_DAYS)
            
            cursor.execute("""
                SELECT COUNT(*) as count FROM job_postings 
                WHERE user_id = ? AND mode = ? AND status = 'active' 
                AND created_at > ?
            """, (user_id, mode, cooldown_date))
            
            result = cursor.fetchone()
            return result['count'] == 0

    def get_user_active_postings_count(self, user_id: int) -> int:
        """Get count of active postings for user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count FROM job_postings 
                WHERE user_id = ? AND status = 'active'
            """, (user_id,))
            
            result = cursor.fetchone()
            return result['count']

    def check_user_posting_limit(self, user_id: int) -> tuple[bool, Optional[datetime]]:
        """
        Проверяет лимит публикаций пользователя за последние 30 дней.
        
        Returns:
            tuple[bool, Optional[datetime]]: 
                - can_post: можно ли публиковать
                - earliest_next_post_date: дата следующей возможной публикации (если лимит превышен)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем все активные объявления за последние 30 дней
            thirty_days_ago = datetime.now() - timedelta(days=30)
            # Конвертируем в строку для SQLite
            thirty_days_ago_str = thirty_days_ago.isoformat()
            
            cursor.execute("""
                SELECT created_at FROM job_postings 
                WHERE user_id = ? AND status = 'active' 
                AND datetime(created_at) > datetime(?)
                ORDER BY created_at ASC
            """, (user_id, thirty_days_ago_str))
            
            recent_postings = cursor.fetchall()
            
            if len(recent_postings) < 3:
                # Меньше 3 объявлений - можно публиковать
                return True, None
            
            # Ровно 3 объявления - проверяем дату самого старого
            oldest_posting_date_str = recent_postings[0]['created_at']
            
            # Convert string to datetime if needed
            if isinstance(oldest_posting_date_str, str):
                oldest_posting_date = datetime.fromisoformat(oldest_posting_date_str.replace('Z', '+00:00'))
            else:
                oldest_posting_date = oldest_posting_date_str
                
            earliest_next_post = oldest_posting_date + timedelta(days=30)
            
            # Если 30 дней еще не прошли с самого старого объявления
            if earliest_next_post > datetime.now():
                return False, earliest_next_post
            
            # Если 30 дней прошли - можно публиковать
            return True, None

    def check_phone_posting_limit(self, phone_main: str, phone_whatsapp: Optional[str] = None) -> tuple[bool, Optional[datetime]]:
        """
        Проверяет лимит публикаций по номеру телефона за последние 30 дней.
        Это предотвращает создание нескольких объявлений с одного номера через разные аккаунты.
        
        Args:
            phone_main: Основной номер телефона
            phone_whatsapp: Номер WhatsApp (опционально)
        
        Returns:
            tuple[bool, Optional[datetime]]: 
                - can_post: можно ли публиковать
                - earliest_next_post_date: дата следующей возможной публикации (если лимит превышен)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем все активные объявления за последние 30 дней по номеру телефона
            thirty_days_ago = datetime.now() - timedelta(days=30)
            # Конвертируем в строку для SQLite
            thirty_days_ago_str = thirty_days_ago.isoformat()
            
            # Проверяем объявления с таким же основным номером или WhatsApp номером
            # Учитываем случаи, когда phone_whatsapp может совпадать с phone_main
            if phone_whatsapp and phone_whatsapp.lower() not in ['нет', 'no', 'none', ''] and phone_whatsapp != phone_main:
                cursor.execute("""
                    SELECT created_at FROM job_postings 
                    WHERE status = 'active' 
                    AND datetime(created_at) > datetime(?)
                    AND (phone_main = ? OR phone_whatsapp = ? OR phone_main = ? OR phone_whatsapp = ?)
                    ORDER BY created_at ASC
                """, (thirty_days_ago_str, phone_main, phone_main, phone_whatsapp, phone_whatsapp))
            else:
                # Если WhatsApp номер не указан или совпадает с основным, проверяем только по основному номеру
                cursor.execute("""
                    SELECT created_at FROM job_postings 
                    WHERE status = 'active' 
                    AND datetime(created_at) > datetime(?)
                    AND (phone_main = ? OR phone_whatsapp = ?)
                    ORDER BY created_at ASC
                """, (thirty_days_ago_str, phone_main, phone_main))
            
            recent_postings = cursor.fetchall()
            
            if len(recent_postings) < 3:
                # Меньше 3 объявлений - можно публиковать
                return True, None
            
            # Ровно 3 объявления - проверяем дату самого старого
            oldest_posting_date_str = recent_postings[0]['created_at']
            
            # Convert string to datetime if needed
            if isinstance(oldest_posting_date_str, str):
                oldest_posting_date = datetime.fromisoformat(oldest_posting_date_str.replace('Z', '+00:00'))
            else:
                oldest_posting_date = oldest_posting_date_str
                
            earliest_next_post = oldest_posting_date + timedelta(days=30)
            
            # Если 30 дней еще не прошли с самого старого объявления
            if earliest_next_post > datetime.now():
                return False, earliest_next_post
            
            # Если 30 дней прошли - можно публиковать
            return True, None

    def check_duplicate_posting(self, user_id: int, mode: str, description: str) -> bool:
        """
        Проверяет, есть ли уже похожее объявление у пользователя.
        
        Args:
            user_id: ID пользователя
            mode: Режим объявления (seeking/offering)
            description: Описание объявления
            
        Returns:
            bool: True если найдено дублирующее объявление
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем все активные объявления пользователя в том же режиме
            cursor.execute("""
                SELECT description FROM job_postings 
                WHERE user_id = ? AND mode = ? AND status = 'active'
                ORDER BY created_at DESC
            """, (user_id, mode))
            
            existing_postings = cursor.fetchall()
            
            # Проверяем на похожесть описаний (первые 100 символов)
            description_start = description[:100].lower().strip()
            
            for posting in existing_postings:
                existing_desc = posting['description'][:100].lower().strip()
                
                # Если описания очень похожи (80% совпадение или больше)
                if self._similarity_check(description_start, existing_desc) > 0.8:
                    return True
            
            return False
    
    def _similarity_check(self, text1: str, text2: str) -> float:
        """
        Простая проверка схожести текстов.
        
        Returns:
            float: Коэффициент схожести от 0 до 1
        """
        if not text1 or not text2:
            return 0.0
        
        # Убираем лишние пробелы и приводим к нижнему регистру
        text1 = ' '.join(text1.split())
        text2 = ' '.join(text2.split())
        
        if text1 == text2:
            return 1.0
        
        # Простая проверка по словам
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)

    def ban_user(self, user_id: int, banned_by: int, reason: str, ban_type: str = 'permanent', expires_at: Optional[datetime] = None) -> bool:
        """
        Банит пользователя.
        
        Args:
            user_id: ID пользователя для бана (может быть как telegram_id, так и id из базы)
            banned_by: ID администратора, который банит (может быть как telegram_id, так и id из базы)
            reason: Причина бана
            ban_type: Тип бана ('temporary' или 'permanent')
            expires_at: Дата окончания бана (для временного бана)
            
        Returns:
            bool: True если бан успешно создан
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем ID пользователя из базы
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
            user_result = cursor.fetchone()
            if user_result:
                db_user_id = user_result['id']
            else:
                # Создаем пользователя, если его нет в базе
                cursor.execute("""
                    INSERT INTO users (telegram_id, username, first_name, last_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, None, None, None, datetime.now(), datetime.now()))
                conn.commit()
                db_user_id = cursor.lastrowid
            
            # Получаем ID администратора из базы
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (banned_by,))
            admin_result = cursor.fetchone()
            if admin_result:
                db_banned_by = admin_result['id']
            else:
                # Создаем администратора, если его нет в базе
                cursor.execute("""
                    INSERT INTO users (telegram_id, username, first_name, last_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (banned_by, 'admin', 'Admin', None, datetime.now(), datetime.now()))
                conn.commit()
                db_banned_by = cursor.lastrowid
            
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
            """, (db_user_id, db_banned_by, reason, ban_type, expires_at, datetime.now()))
            
            conn.commit()
            return True

    def unban_user(self, user_id: int, unbanned_by: int) -> bool:
        """
        Разбанивает пользователя.
        
        Args:
            user_id: ID пользователя для разбана (может быть как telegram_id, так и id из базы)
            unbanned_by: ID администратора, который разбанивает (может быть как telegram_id, так и id из базы)
            
        Returns:
            bool: True если разбан успешен
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем ID пользователя из базы
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
            user_result = cursor.fetchone()
            if user_result:
                db_user_id = user_result['id']
            else:
                db_user_id = user_id
            
            cursor.execute("""
                UPDATE user_bans 
                SET is_active = FALSE 
                WHERE user_id = ? AND is_active = TRUE
            """, (db_user_id,))
            
            conn.commit()
            return True

    def is_user_banned(self, user_id: int) -> tuple[bool, Optional[dict]]:
        """
        Проверяет, забанен ли пользователь.
        
        Args:
            user_id: ID пользователя (может быть как telegram_id, так и id из базы)
            
        Returns:
            tuple[bool, Optional[dict]]: (забанен ли, информация о бане)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Сначала проверяем, является ли user_id telegram_id
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                # Это telegram_id, получаем id из базы
                db_user_id = user_result['id']
            else:
                # Это уже id из базы
                db_user_id = user_id
            
            cursor.execute("""
                SELECT ub.*, u.telegram_id, u.username, u.first_name, u.last_name,
                       admin.telegram_id as admin_telegram_id, admin.username as admin_username
                FROM user_bans ub
                JOIN users u ON ub.user_id = u.id
                JOIN users admin ON ub.banned_by = admin.id
                WHERE ub.user_id = ? AND ub.is_active = TRUE
                ORDER BY ub.created_at DESC
                LIMIT 1
            """, (db_user_id,))
            
            ban_info = cursor.fetchone()
            
            if not ban_info:
                return False, None
            
            # Проверяем, не истек ли временный бан
            if ban_info['ban_type'] == 'temporary' and ban_info['expires_at']:
                expires_at = ban_info['expires_at']
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                
                if expires_at < datetime.now():
                    # Бан истек, деактивируем его
                    cursor.execute("""
                        UPDATE user_bans 
                        SET is_active = FALSE 
                        WHERE id = ?
                    """, (ban_info['id'],))
                    conn.commit()
                    return False, None
            
            return True, dict(ban_info)

    def get_user_bans(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает историю банов пользователя.
        
        Args:
            user_id: ID пользователя (может быть как telegram_id, так и id из базы)
            
        Returns:
            List[Dict[str, Any]]: Список банов
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Сначала проверяем, является ли user_id telegram_id
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                # Это telegram_id, получаем id из базы
                db_user_id = user_result['id']
            else:
                # Это уже id из базы
                db_user_id = user_id
            
            cursor.execute("""
                SELECT ub.*, admin.telegram_id as admin_telegram_id, admin.username as admin_username
                FROM user_bans ub
                JOIN users admin ON ub.banned_by = admin.id
                WHERE ub.user_id = ?
                ORDER BY ub.created_at DESC
            """, (db_user_id,))
            
            results = cursor.fetchall()
            return [dict(row) for row in results]

    def get_all_bans(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Получает все баны.
        
        Args:
            active_only: Только активные баны
            
        Returns:
            List[Dict[str, Any]]: Список банов
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if active_only:
                cursor.execute("""
                    SELECT ub.*, u.telegram_id, u.username, u.first_name, u.last_name,
                           admin.telegram_id as admin_telegram_id, admin.username as admin_username
                    FROM user_bans ub
                    JOIN users u ON ub.user_id = u.id
                    JOIN users admin ON ub.banned_by = admin.id
                    WHERE ub.is_active = TRUE
                    ORDER BY ub.created_at DESC
                """)
            else:
                cursor.execute("""
                    SELECT ub.*, u.telegram_id, u.username, u.first_name, u.last_name,
                           admin.telegram_id as admin_telegram_id, admin.username as admin_username
                    FROM user_bans ub
                    JOIN users u ON ub.user_id = u.id
                    JOIN users admin ON ub.banned_by = admin.id
                    ORDER BY ub.created_at DESC
                """)
            
            results = cursor.fetchall()
            return [dict(row) for row in results]

    def cleanup_expired_bans(self) -> int:
        """
        Очищает истекшие временные баны.
        
        Returns:
            int: Количество деактивированных банов
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE user_bans 
                SET is_active = FALSE 
                WHERE ban_type = 'temporary' 
                AND expires_at IS NOT NULL 
                AND expires_at < ? 
                AND is_active = TRUE
            """, (datetime.now(),))
            
            deactivated_count = cursor.rowcount
            conn.commit()
            return deactivated_count

    def create_premium_post(self, user_id: int, **data) -> int:
        """
        Создает премиум-пост.
        
        Args:
            user_id: ID пользователя
            **data: Данные поста
            
        Returns:
            int: ID созданного поста
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO premium_posts (
                    user_id, mode, cities, description, social_media, 
                    telegram_username, phone_main, phone_whatsapp, name,
                    media_file_id, media_type, media_list, payment_status, payment_amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, data.get('mode'), data.get('cities'), data.get('description'),
                data.get('social_media'), data.get('telegram_username'), data.get('phone_main'),
                data.get('phone_whatsapp'), data.get('name'), data.get('media_file_id'),
                data.get('media_type'), json.dumps(data.get('media_list', [])), 'pending', 50.00
            ))
            
            post_id = cursor.lastrowid
            conn.commit()
            return post_id

    def get_premium_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает премиум-пост по ID.
        
        Args:
            post_id: ID поста
            
        Returns:
            Optional[Dict[str, Any]]: Данные поста или None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT pp.*, u.telegram_id, u.username, u.first_name, u.last_name
                FROM premium_posts pp
                JOIN users u ON pp.user_id = u.id
                WHERE pp.id = ?
            """, (post_id,))
            
            result = cursor.fetchone()
            if result:
                post_data = dict(result)
                # Parse media_list from JSON
                if post_data.get('media_list'):
                    try:
                        post_data['media_list'] = json.loads(post_data['media_list'])
                    except (json.JSONDecodeError, TypeError):
                        post_data['media_list'] = []
                else:
                    post_data['media_list'] = []
                
                # Parse cities from JSON
                if post_data.get('cities'):
                    try:
                        post_data['cities'] = json.loads(post_data['cities'])
                    except (json.JSONDecodeError, TypeError):
                        post_data['cities'] = ['online']
                else:
                    post_data['cities'] = ['online']
                return post_data
            return None

    def get_pending_premium_posts(self) -> List[Dict[str, Any]]:
        """
        Получает все ожидающие подтверждения премиум-посты.
        
        Returns:
            List[Dict[str, Any]]: Список постов
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT pp.*, u.telegram_id, u.username, u.first_name, u.last_name
                FROM premium_posts pp
                JOIN users u ON pp.user_id = u.id
                WHERE pp.payment_status = 'pending'
                ORDER BY pp.created_at DESC
            """)
            
            results = cursor.fetchall()
            return [dict(row) for row in results]

    def approve_premium_post(self, post_id: int, admin_id: int, admin_notes: str = None) -> bool:
        """
        Подтверждает оплату премиум-поста.
        
        Args:
            post_id: ID поста
            admin_id: ID администратора
            admin_notes: Заметки администратора
            
        Returns:
            bool: True если успешно
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE premium_posts 
                SET payment_status = 'approved', admin_notes = ?, updated_at = ?
                WHERE id = ?
            """, (admin_notes, datetime.now(), post_id))
            
            conn.commit()
            return cursor.rowcount > 0

    def reject_premium_post(self, post_id: int, admin_id: int, admin_notes: str) -> bool:
        """
        Отклоняет оплату премиум-поста.
        
        Args:
            post_id: ID поста
            admin_id: ID администратора
            admin_notes: Причина отклонения
            
        Returns:
            bool: True если успешно
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE premium_posts 
                SET payment_status = 'rejected', admin_notes = ?, updated_at = ?
                WHERE id = ?
            """, (admin_notes, datetime.now(), post_id))
            
            conn.commit()
            return cursor.rowcount > 0

    def update_premium_post_publication(self, post_id: int, message_id: int, chat_id: int, topic_id: int = None) -> bool:
        """
        Обновляет информацию о публикации премиум-поста.
        
        Args:
            post_id: ID поста
            message_id: ID сообщения в канале
            chat_id: ID чата
            topic_id: ID топика (опционально)
            
        Returns:
            bool: True если успешно
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE premium_posts 
                SET message_id = ?, chat_id = ?, topic_id = ?, status = 'published', updated_at = ?
                WHERE id = ?
            """, (message_id, chat_id, topic_id, datetime.now(), post_id))
            
            conn.commit()
            return cursor.rowcount > 0

    def check_phone_number_exists(self, phone_main: str, user_id: int = None) -> bool:
        """
        Проверяет, используется ли номер телефона в другом активном объявлении.
        
        Args:
            phone_main: Основной номер телефона
            user_id: ID пользователя, объявления которого нужно исключить из проверки
            
        Returns:
            bool: True если номер уже используется в другом объявлении
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Нормализуем номер телефона (убираем пробелы, дефисы и т.д.)
            normalized_phone = ''.join(filter(str.isdigit, phone_main))
            
            # Подготавливаем условие для исключения пользователя
            user_condition = "AND user_id != ?" if user_id is not None else ""
            params = [phone_main]
            if user_id is not None:
                params.append(user_id)
            
            # Проверяем основной номер телефона
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM job_postings 
                WHERE phone_main = ? AND status = 'active' {user_condition}
            """, params)
            
            result = cursor.fetchone()
            if result['count'] > 0:
                return True
            
            # Проверяем WhatsApp номер телефона
            params_whatsapp = [phone_main]
            if user_id is not None:
                params_whatsapp.append(user_id)
            
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM job_postings 
                WHERE phone_whatsapp = ? AND status = 'active' {user_condition}
            """, params_whatsapp)
            
            result = cursor.fetchone()
            if result['count'] > 0:
                return True
            
            # Также проверяем нормализованную версию для основного номера
            params_normalized = [normalized_phone]
            if user_id is not None:
                params_normalized.append(user_id)
            
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM job_postings 
                WHERE REPLACE(REPLACE(REPLACE(phone_main, ' ', ''), '-', ''), '+', '') = ? 
                AND status = 'active' {user_condition}
            """, params_normalized)
            
            result = cursor.fetchone()
            if result['count'] > 0:
                return True
            
            # И для WhatsApp номера
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM job_postings 
                WHERE REPLACE(REPLACE(REPLACE(phone_whatsapp, ' ', ''), '-', ''), '+', '') = ? 
                AND status = 'active' {user_condition}
            """, params_normalized)
            
            result = cursor.fetchone()
            if result['count'] > 0:
                return True
            
            return False

    def save_draft(self, user_id: int, **data) -> int:
        """Save draft."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Delete existing draft for user
            cursor.execute("DELETE FROM drafts WHERE user_id = ?", (user_id,))
            
            # Insert new draft
            fields = ['user_id'] + list(data.keys())
            placeholders = ['?'] * len(fields)
            values = [user_id] + list(data.values())
            
            cursor.execute(f"""
                INSERT INTO drafts ({', '.join(fields)}, created_at, updated_at)
                VALUES ({', '.join(placeholders)}, ?, ?)
            """, values + [datetime.now(), datetime.now()])
            
            conn.commit()
            return cursor.lastrowid

    def get_draft(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get draft for user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM drafts WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return dict(result) if result else None

    def delete_draft(self, user_id: int) -> bool:
        """Delete draft for user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM drafts WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    def cleanup_expired_postings(self) -> tuple[int, list[dict]]:
        """
        Удаляет объявления старше 30 дней.
        
        Returns:
            tuple[int, list[dict]]: 
                - count: количество удаленных объявлений
                - deleted_postings: список удаленных объявлений с информацией
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Находим объявления старше 30 дней
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            # Получаем информацию об объявлениях для удаления
            cursor.execute("""
                SELECT id, user_id, mode, cities, name, message_id, chat_id, topic_id, created_at
                FROM job_postings 
                WHERE status = 'active' AND created_at < ?
            """, (thirty_days_ago,))
            
            expired_postings = cursor.fetchall()
            deleted_count = 0
            deleted_info = []
            
            for posting in expired_postings:
                # Сохраняем информацию для логирования
                posting_info = {
                    'id': posting['id'],
                    'user_id': posting['user_id'],
                    'mode': posting['mode'],
                    'cities': posting['cities'],
                    'name': posting['name'],
                    'message_id': posting['message_id'],
                    'chat_id': posting['chat_id'],
                    'topic_id': posting['topic_id'],
                    'created_at': posting['created_at']
                }
                deleted_info.append(posting_info)
                
                # Удаляем объявление (soft delete)
                cursor.execute("""
                    UPDATE job_postings 
                    SET status = 'expired', updated_at = ? 
                    WHERE id = ?
                """, (datetime.now(), posting['id']))
                
                deleted_count += 1
            
            conn.commit()
            return deleted_count, deleted_info


# Global database instance
db = Database()
