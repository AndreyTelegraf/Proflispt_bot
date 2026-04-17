#!/usr/bin/env python3
"""Script to fix Telegram bot conflicts."""

import subprocess
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8405113240:AAEksoQZrlJIyj-0vWYnShP3GcgcWyVQX48"

def fix_telegram_conflict():
    """Fix Telegram bot conflict by clearing updates."""
    
    logger.info("🔧 Начинаем исправление конфликта Telegram...")
    
    # 1. Остановить все процессы бота
    logger.info("1️⃣ Останавливаем процессы бота...")
    try:
        subprocess.run(["pkill", "-f", "python3 main.py"], check=False)
        time.sleep(2)
        logger.info("✅ Процессы остановлены")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при остановке процессов: {e}")
    
    # 2. Удалить webhook
    logger.info("2️⃣ Удаляем webhook...")
    try:
        result = subprocess.run([
            "curl", "-s", 
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        ], capture_output=True, text=True)
        logger.info(f"✅ Webhook удален: {result.stdout.strip()}")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при удалении webhook: {e}")
    
    # 3. Очистить обновления с offset
    logger.info("3️⃣ Очищаем обновления...")
    try:
        result = subprocess.run([
            "curl", "-s", 
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=999999999"
        ], capture_output=True, text=True)
        logger.info(f"✅ Обновления очищены: {result.stdout.strip()}")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при очистке обновлений: {e}")
    
    # 4. Проверить статус
    logger.info("4️⃣ Проверяем статус...")
    try:
        result = subprocess.run([
            "curl", "-s", 
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        ], capture_output=True, text=True)
        
        if '"ok":true' in result.stdout:
            logger.info("✅ Конфликт разрешен! Бот готов к запуску")
            return True
        else:
            logger.error(f"❌ Конфликт не разрешен: {result.stdout.strip()}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке статуса: {e}")
        return False

if __name__ == "__main__":
    success = fix_telegram_conflict()
    if success:
        print("\n🎉 Конфликт успешно разрешен! Теперь можно запускать бота.")
    else:
        print("\n💥 Не удалось разрешить конфликт. Попробуйте перезагрузить систему.")

